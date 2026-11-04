"""Результат 3: REST API над RAG + граф.

  POST /ask               питання -> відповідь + джерела (потрібен ключ; ролі viewer/analyst/admin)
  GET  /sources/{id}      текст джерела за id із відповіді (з перевіркою прав)
  GET  /health            стан сервісу (без автентифікації)

Запуск:  uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload      Документація: /docs (Swagger), /openapi.json
"""
import logging
import os
import pathlib
import re
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Path, Request, Response
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .security import KeyStore, Principal, RateLimiter

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _api_keys_spec() -> str:
    """API_KEYS зі змінних середовища, а якщо їх немає або вони порожні (контейнер створено до генерації ключів) — із .env на диску."""
    spec = os.getenv("API_KEYS", "")
    if not spec and (ROOT / ".env").exists():
        from dotenv import dotenv_values
        spec = dotenv_values(ROOT / ".env").get("API_KEYS") or ""
    return spec

log = logging.getLogger("api")
VERSION = "1.0.0"
SOURCE_ID_PATTERN = r"^[A-Za-z0-9_.:#-]{1,100}$"
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, scheme_name="ApiKeyAuth",
                              description="API-ключ. Роль ключа (viewer / analyst / admin) визначає доступні документи.")

COMMON_ERRORS = {
    401: {"description": "Немає або неправильний X-API-Key"},
    429: {"description": "Перевищено ліміт запитів (заголовок Retry-After)"},
}


# ---------------------------------------------------------------- схеми
class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=1000, description="Питання користувача",
                          examples=["What is an airline hub?"])
    top_k: int = Field(5, ge=1, le=10, description="Скільки контекстів із тексту передати в LLM")
    use_graph: bool = Field(False, description="Додати підграф із графа знань (лише ролі analyst, admin)")

    @field_validator("question", mode="before")
    @classmethod
    def clean(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if CONTROL_CHARS.search(v):
                raise ValueError("питання містить керівні символи")
        return v


class SourceOut(BaseModel):
    id: str
    kind: str = Field(description="text | graph")
    doc_id: str | None = None
    title: str | None = None
    rerank_score: float | None = None


class AskResponse(BaseModel):
    request_id: str
    answer: str
    abstained: bool = Field(description="true, якщо модель відповіла «не знаю» (answer тоді містить пояснення)")
    sources: list[SourceOut]
    citations: dict = Field(description="cited — цитовані id; invalid — цитати поза наданим контекстом; ok — чи валідні")
    tokens: dict
    latency_ms: dict
    model: str
    access_level: str
    graph_used: bool


class SourceDetail(BaseModel):
    id: str
    kind: str
    title: str | None = None
    section: str | None = None
    sensitivity: str | None = None
    source_url: str | None = None
    license: str | None = None
    text: str


class Health(BaseModel):
    status: str
    version: str
    rag_loaded: bool
    graph_backend: str | None = None


# ---------------------------------------------------------------- застосунок
def create_app(rag=None, gc=None, keys: KeyStore | None = None, limiter: RateLimiter | None = None) -> FastAPI:
    """rag / gc можна підставити (тести); інакше вони вантажаться при старті."""
    limits = {"ask": int(os.getenv("RATE_LIMIT_ASK_PER_MIN", "10")),
              "read": int(os.getenv("RATE_LIMIT_READ_PER_MIN", "60")),
              "authfail": int(os.getenv("RATE_LIMIT_AUTHFAIL_PER_MIN", "20"))}
    gate = threading.Semaphore(int(os.getenv("RAG_CONCURRENCY", "2")))     # обмежуємо одночасні виклики LLM/reranker

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.keys = keys or KeyStore(_api_keys_spec())       # без ключів сервіс не стартує
        app.state.limiter = limiter or RateLimiter()
        app.state.rag, app.state.gc = rag, gc
        if app.state.rag is None:
            from src.rag import RAG                                          # важкі імпорти лише тут
            app.state.rag = RAG()
        if app.state.gc is None:
            try:
                from src.graph_context import GraphContext
                app.state.gc = GraphContext()
            except Exception:
                log.exception("граф недоступний: use_graph буде повертати 503")
        app.state.chunks = {c["chunk_id"]: c for c in app.state.rag.vi.chunks}
        yield

    app = FastAPI(title="Aviation Knowledge Hub API", version=VERSION, lifespan=lifespan,
                  description="RAG-чат-бот з цитуванням, політикою «не знаю» та підграфом із графа знань (ЛР 11). "
                              "Автентифікація: заголовок `X-API-Key`. Ролі: **viewer** (public), **analyst** (public+internal, граф), "
                              "**admin** (усе).")

    # ---- залежності
    def get_principal(request: Request, api_key: str | None = Depends(api_key_header)) -> Principal:
        p = request.app.state.keys.authenticate(api_key)
        if p is None:
            ip = request.client.host if request.client else "?"
            ok, _, retry = request.app.state.limiter.hit(f"authfail:{ip}", limits["authfail"])
            if not ok:
                raise HTTPException(429, "Забагато невдалих спроб автентифікації", headers={"Retry-After": str(retry)})
            raise HTTPException(401, "Потрібен дійсний X-API-Key", headers={"WWW-Authenticate": "ApiKey"})
        return p

    def limited(scope: str):
        def dep(request: Request, response: Response, p: Principal = Depends(get_principal)) -> Principal:
            ok, remaining, retry = request.app.state.limiter.hit(f"{scope}:{p.key_id}", limits[scope])
            response.headers["X-RateLimit-Limit"] = str(limits[scope])
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            if not ok:
                raise HTTPException(429, f"Ліміт {limits[scope]} запитів/хв вичерпано", headers={"Retry-After": str(retry)})
            return p
        return dep

    # ---- ендпоінти
    @app.get("/health", response_model=Health, tags=["service"], summary="Стан сервісу")
    def health(request: Request):
        s = request.app.state
        return Health(status="ok" if getattr(s, "rag", None) is not None else "loading", version=VERSION,
                      rag_loaded=getattr(s, "rag", None) is not None,
                      graph_backend=getattr(getattr(getattr(s, "gc", None), "b", None), "name", None))

    @app.post("/ask", response_model=AskResponse, tags=["rag"], summary="Запитати базу знань",
              responses={**COMMON_ERRORS, 403: {"description": "use_graph для ролі viewer"},
                         502: {"description": "Помилка LLM-провайдера"}, 503: {"description": "Граф або LLM тимчасово недоступні"}})
    def ask(body: AskRequest, request: Request, p: Principal = Depends(limited("ask"))):
        s = request.app.state
        extra = None
        if body.use_graph:
            if not p.can_graph:
                raise HTTPException(403, "Підграф доступний ролям analyst і admin")
            if s.gc is None:
                raise HTTPException(503, "Граф знань недоступний")
            try:
                extra, _ = s.gc.context_for(body.question)
            except Exception:
                log.exception("помилка витягу підграфа")
                raise HTTPException(503, "Граф знань недоступний")
        try:
            with gate:
                res = s.rag.ask(body.question, max_level=p.level, extra_sources=extra or None,
                                top_k=body.top_k, tag=f"api:{p.role}:{p.key_id}")
        except Exception as e:
            log.exception("помилка RAG/LLM")
            code = getattr(e, "code", None)
            if code == 429:
                raise HTTPException(503, "LLM тимчасово обмежує запити, повторіть пізніше", headers={"Retry-After": "30"})
            raise HTTPException(502, "Помилка LLM-провайдера")           # деталі лише в журналі сервера
        out = []
        for src in res["sources"]:
            if src["id"].startswith("graph:"):
                out.append(SourceOut(id=src["id"], kind="graph", title=f"Knowledge graph: {src['id'][6:]}"))
            else:
                c = s.chunks.get(src["id"], {})
                out.append(SourceOut(id=src["id"], kind="text", doc_id=src.get("doc_id"), title=c.get("title"),
                                     rerank_score=src.get("rerank_score")))
        return AskResponse(request_id=res["request_id"], answer=res["answer"], abstained=res["abstained"], sources=out,
                           citations=res["citations"], tokens=res["tokens"], latency_ms=res["latency_ms"], model=res["model"],
                           access_level=p.level, graph_used=bool(extra))

    @app.get("/sources/{source_id}", response_model=SourceDetail, tags=["rag"], summary="Текст джерела за id",
             description="Ідентифікатори містять `#` (наприклад `en_aircrewc#018`): у URL його кодують як `%23`.",
             responses={**COMMON_ERRORS, 403: {"description": "Рівень доступу ролі нижчий за чутливість документа"},
                        404: {"description": "Джерело не знайдено"}})
    def get_source(request: Request, source_id: str = Path(pattern=SOURCE_ID_PATTERN, description="id із поля sources"),
                   p: Principal = Depends(limited("read"))):
        s = request.app.state
        if source_id.startswith("graph:"):
            if not p.can_graph:
                raise HTTPException(403, "Підграф доступний ролям analyst і admin")
            return _graph_source(s, source_id)
        c = s.chunks.get(source_id)
        if c is None:
            raise HTTPException(404, "Джерело не знайдено")
        meta = s.rag.meta.get(c["doc_id"], {})
        sens = meta.get("sensitivity", "restricted")
        if not p.may_read(sens):
            raise HTTPException(403, f"Документ має рівень {sens}; ваш рівень — {p.level}")
        return SourceDetail(id=source_id, kind="text", title=c.get("title"), section=c.get("section"), sensitivity=sens,
                            source_url=meta.get("source_url"), license=meta.get("license"), text=c.get("context") or c["text"])

    return app


def _graph_source(s, source_id: str) -> SourceDetail:
    """graph:<key> -> лінеаризований підграф навколо вузла (пасажири виключені, як і в Результаті 2)."""
    from src.graph_context import KEYS, SKIP_LABELS, ref, node_name
    if s.gc is None:
        raise HTTPException(503, "Граф знань недоступний")
    key = source_id[6:]
    seed = next(((l, key) for l in KEYS if l not in SKIP_LABELS and s.gc.b.node(l, key)), None)
    if seed is None:
        raise HTTPException(404, "Вузол не знайдено")
    edges, notes = s.gc._expand(seed, 15, set())
    return SourceDetail(id=source_id, kind="graph", title=f"Knowledge graph: {ref(*seed)} {node_name(seed[0], s.gc.b.node(*seed))}".strip(),
                        text=s.gc.linearize(seed, edges, notes))


app = create_app()
