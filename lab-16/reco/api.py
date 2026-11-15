"""FastAPI-шар Hub для демонстратора (ЛР 16): рекомендації з поясненнями, питання до бази знань, граф, захищений Cypher.
Права визначаються рівнем доступу користувача (users.csv), а не параметрами запиту."""
from functools import lru_cache
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Query
from mcp_server import graph as hub_graph, neo4j_cypher
from .recommender import Recommender, METHODS
from .explain import Explainer
from .qa import ask as qa_ask

app = FastAPI(title="Aviation Knowledge Hub: recommender", version="0.3")


@lru_cache(maxsize=1)
def rec() -> Recommender:
    return Recommender()


@lru_cache(maxsize=1)
def explainer() -> Explainer:
    return Explainer(rec().ds)


@lru_cache(maxsize=1)
def paraphraser():
    try:
        from .explain import GeminiParaphraser
        return GeminiParaphraser()
    except Exception:  # немає ключа / пакета: працюємо без LLM
        return None


def level_of(user_id: str | None) -> str:
    if not user_id:
        return "public"
    u = rec().ds.users.get(user_id)
    if not u:
        raise HTTPException(404, "невідомий користувач")
    return u["access_level"]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/users")
def users() -> list[dict]:
    return [{k: u[k] for k in ("user_id", "role", "airline", "home_airport", "access_level", "cohort")}
            for u in sorted(rec().ds.users.values(), key=lambda x: x["user_id"])]


@app.get("/recommend/{user_id}")
def recommend(user_id: str, k: int = Query(5, ge=1, le=20), method: str = "hybrid", filters: bool = True,
              explain: bool = True, llm: bool = False):
    if method not in METHODS:
        raise HTTPException(400, f"method має бути одним із {METHODS}")
    r = rec()
    try:
        out = r.recommend(user_id, k, method, as_of=r.ds.end[:10], use_filters=filters, explain=explain)
    except KeyError:
        raise HTTPException(404, "невідомий користувач")
    out["access_level"] = r.ds.users[user_id]["access_level"]
    out["cohort"] = r.ds.users[user_id]["cohort"]
    out["has_history"] = user_id in r.seen
    if explain:
        para = paraphraser() if llm else None
        out["llm_available"] = paraphraser() is not None
        for it in out["items"]:
            if it.get("path"):
                e = explainer().explain(it["path"], it["doc_id"], para)
                it["explanation"] = {"text": e["text"], "source": e["source"], "check_ok": e["check"]["ok"]}
    return out


@app.get("/ask")
def ask(q: str = Query(..., min_length=2, max_length=500), user_id: str | None = None):
    return qa_ask(q, level_of(user_id))


@app.get("/graph")
def graph(entity: str = Query(..., min_length=1, max_length=100), hops: int = Query(1, ge=1, le=2), user_id: str | None = None):
    return hub_graph.lookup(entity, hops, level_of(user_id))


class CypherIn(BaseModel):
    query: str
    user_id: str | None = None


@app.post("/cypher")
def cypher(body: CypherIn):
    return neo4j_cypher.run(body.query, level_of(body.user_id))
