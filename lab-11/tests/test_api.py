"""Тести API з підробленим RAG (без моделей і Gemini). Запуск у контейнері: pytest tests/test_api.py"""
import types
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient
from api.main import create_app
from api.security import KeyStore, RateLimiter, hash_key
from src.graph_context import GraphContext, CsvBackend

KEYS = {"k-view": "viewer", "k-an": "analyst", "k-adm": "admin"}
H = lambda k: {"X-API-Key": k}


class FakeRAG:
    model = "fake-model"

    def __init__(self):
        self.vi = types.SimpleNamespace(chunks=[
            {"chunk_id": "pub#001", "doc_id": "pub", "title": "Public doc", "section": "S", "text": "t", "context": "public context"},
            {"chunk_id": "sec#001", "doc_id": "sec", "title": "Secret doc", "section": "S", "text": "t", "context": "restricted context"}])
        self.meta = {"pub": {"sensitivity": "public", "source_url": "u1"}, "sec": {"sensitivity": "restricted", "source_url": "u2"}}
        self.calls, self.fail = [], None

    def ask(self, query, max_level="public", extra_sources=None, top_k=5, tag=None):
        if self.fail:
            raise self.fail
        self.calls.append({"level": max_level, "extra": extra_sources, "tag": tag})
        src = [{"id": "pub#001", "doc_id": "pub", "rerank_score": 1.0}]
        if max_level == "restricted":
            src.append({"id": "sec#001", "doc_id": "sec", "rerank_score": 0.5})
        src += [{"id": s["id"], "doc_id": None, "rerank_score": None} for s in (extra_sources or [])]
        return {"request_id": "r1", "answer": "ok [pub#001]", "abstained": False, "sources": src,
                "citations": {"cited": ["pub#001"], "invalid": [], "ok": True},
                "tokens": {"prompt": 1, "output": 1, "thoughts": 0, "total": 2}, "latency_ms": {"total": 1.0}, "model": self.model}


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ASK_PER_MIN", "3")
    monkeypatch.setenv("RATE_LIMIT_READ_PER_MIN", "5")
    rag = FakeRAG()
    keys = KeyStore(",".join(f"{hash_key(k)}:{r}" for k, r in KEYS.items()))
    app = create_app(rag=rag, gc=GraphContext(CsvBackend()), keys=keys, limiter=RateLimiter())
    with TestClient(app) as c:
        yield c, rag


def test_health_open(env):
    c, _ = env
    r = c.get("/health")
    assert r.status_code == 200 and r.json()["rag_loaded"] is True


def test_auth_required(env):
    c, _ = env
    assert c.post("/ask", json={"question": "hello there"}).status_code == 401
    assert c.post("/ask", json={"question": "hello there"}, headers=H("bad")).status_code == 401
    assert c.get("/sources/pub%23001").status_code == 401


def test_two_roles_see_different_sources(env):
    c, rag = env
    v = c.post("/ask", json={"question": "What is a hub?"}, headers=H("k-view")).json()
    a = c.post("/ask", json={"question": "What is a hub?"}, headers=H("k-adm")).json()
    assert [s["id"] for s in v["sources"]] == ["pub#001"] and v["access_level"] == "public"
    assert [s["id"] for s in a["sources"]] == ["pub#001", "sec#001"] and a["access_level"] == "restricted"
    assert [x["level"] for x in rag.calls] == ["public", "restricted"]          # рівень береться з ролі, не з тіла запиту


def test_client_cannot_choose_level(env):
    c, _ = env
    r = c.post("/ask", json={"question": "What is a hub?", "max_level": "restricted"}, headers=H("k-view"))
    assert r.status_code == 422                                                 # extra=forbid


def test_sources_access(env):
    c, _ = env
    assert c.get("/sources/pub%23001", headers=H("k-view")).status_code == 200
    assert c.get("/sources/sec%23001", headers=H("k-view")).status_code == 403
    assert c.get("/sources/sec%23001", headers=H("k-adm")).json()["text"] == "restricted context"
    assert c.get("/sources/nope%23000", headers=H("k-adm")).status_code == 404


def test_graph_roles(env):
    c, rag = env
    body = {"question": "Which flights are affected by Fog at Lviv?", "use_graph": True}
    assert c.post("/ask", json=body, headers=H("k-view")).status_code == 403
    r = c.post("/ask", json=body, headers=H("k-an"))
    assert r.status_code == 200 and r.json()["graph_used"] and any(s["kind"] == "graph" for s in r.json()["sources"])
    assert c.get("/sources/graph:LWO", headers=H("k-view")).status_code == 403
    assert "Airport#LWO" in c.get("/sources/graph:LWO", headers=H("k-an")).json()["text"]
    assert c.get("/sources/graph:NOPE", headers=H("k-an")).status_code == 404


@pytest.mark.parametrize("body", [{}, {"question": ""}, {"question": "ab"}, {"question": "x" * 1001},
                                  {"question": "valid question", "top_k": 0}, {"question": "valid question", "top_k": 11},
                                  {"question": "bad \x00 char"}, {"question": 123}])
def test_validation_422(env, body):
    c, _ = env
    assert c.post("/ask", json=body, headers=H("k-adm")).status_code == 422


def test_rate_limit_429(env):
    c, _ = env
    codes = [c.post("/ask", json={"question": "What is a hub?"}, headers=H("k-adm")).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    r = c.post("/ask", json={"question": "What is a hub?"}, headers=H("k-adm"))
    assert int(r.headers["Retry-After"]) >= 1
    assert c.post("/ask", json={"question": "What is a hub?"}, headers=H("k-an")).status_code == 200   # ліміт на ключ


def test_upstream_errors(env):
    c, rag = env
    rag.fail = RuntimeError("secret internal detail")
    r = c.post("/ask", json={"question": "What is a hub?"}, headers=H("k-adm"))
    assert r.status_code == 502 and "secret" not in r.text                      # деталі не витікають
    e = RuntimeError("quota"); e.code = 429; rag.fail = e
    assert c.post("/ask", json={"question": "What is a hub?"}, headers=H("k-an")).status_code == 503
