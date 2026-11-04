#!/usr/bin/env python3
"""Перевірка середовища ЛР 11: бібліотеки, .env, корпус, Neo4j, моделі, Gemini.
Запуск: docker compose exec app python scripts/check_env.py [--llm] [--models]
  --models  завантажує/перевіряє embeddings і reranker (перший запуск качає ~0.5 ГБ)
  --llm     робить 1 мінімальний запит до Gemini (витрачає кілька токенів)
"""
import os, sys, json, pathlib, importlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ok_all = True


def check(name, fn):
    global ok_all
    try:
        print(f"[ OK ] {name}: {fn()}")
    except Exception as e:
        ok_all = False
        print(f"[FAIL] {name}: {type(e).__name__}: {e}")


def libs():
    out = []
    for m in ["fastapi", "uvicorn", "pydantic", "neo4j", "faiss", "sentence_transformers",
              "rank_bm25", "numpy", "pandas", "google.genai"]:
        mod = importlib.import_module(m)
        out.append(f"{m} {getattr(mod, '__version__', '')}".strip())
    return ", ".join(out)


def env():
    need = ["GEMINI_API_KEY", "GEMINI_MODEL", "NEO4J_PASSWORD"]
    miss = [k for k in need if not os.getenv(k)]
    if miss:
        raise RuntimeError(f"не задано в .env: {miss}")
    return f"модель {os.getenv('GEMINI_MODEL')}, суддя {os.getenv('JUDGE_MODEL') or '(не задано)'}"


def corpus():
    n = sum(1 for _ in open(ROOT / "data" / "corpus.jsonl", encoding="utf-8"))
    return f"{n} фрагментів"


def neo4j():
    from neo4j import GraphDatabase
    with GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
                              auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD"))) as d:
        d.verify_connectivity()
        with d.session() as s:
            n = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
    return f"підключено, вузлів у графі: {n}" + ("  <- порожній: запусти scripts/load_graph.py" if n == 0 else "")


def models():
    from sentence_transformers import SentenceTransformer, CrossEncoder
    SentenceTransformer("intfloat/multilingual-e5-small")
    CrossEncoder("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
    return "e5-small і reranker завантажуються"


def llm():
    from google import genai
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))  # тримаємо клієнт у змінній
    r = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL"), contents="Reply with the single word: OK")
    return f"відповідь моделі: {r.text.strip()[:40]!r}"


check("бібліотеки", libs)
check(".env", env)
check("корпус", corpus)
check("Neo4j", neo4j)
if "--models" in sys.argv:
    check("моделі", models)
if "--llm" in sys.argv:
    check("Gemini", llm)
sys.exit(0 if ok_all else 1)
