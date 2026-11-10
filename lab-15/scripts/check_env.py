"""Перевірка середовища: пакети, дані, MCP-сервер, ключ Gemini, Neo4j. Запуск: python scripts/check_env.py"""
import asyncio, importlib, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ok = True


def line(name, good, note=""):
    global ok
    ok &= bool(good)
    print(f"[{'OK ' if good else 'ERR'}] {name} {note}")


for m in ("mcp", "duckdb", "yaml", "numpy", "pandas", "rank_bm25", "neo4j", "google.genai", "pyshacl"):
    try:
        importlib.import_module(m); line(f"пакет {m}", True)
    except ImportError as e:
        line(f"пакет {m}", False, str(e))
try:
    importlib.import_module("sentence_transformers"); line("sentence-transformers (dense)", True)
except ImportError:
    print("[--  ] sentence-transformers не встановлено: vector_search працюватиме як BM25 (make embeddings)")

from mcp_server import config, graph, vector, warehouse  # noqa: E402
line("граф (CSV)", graph.lookup("Lviv")["found"])
line("база знань", vector.search("airport slot", 3)["results"] != [], f"(режим: {vector.search('airport slot', 1)['mode']})")
line("DuckDB-метрика", warehouse.query_metric(["flights_count"])["rows"][0]["flights_count"] > 0)
line("GEMINI_API_KEY у .env", bool(os.getenv("GEMINI_API_KEY")), "(потрібен лише для агента)")
line("GEMINI_MODEL у .env", bool(os.getenv("GEMINI_MODEL")))
if config.NEO4J_PASSWORD:
    try:
        from neo4j import GraphDatabase
        with GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)) as d:
            d.verify_connectivity()
        line("Neo4j", True)
    except Exception as e:
        line("Neo4j", False, f"{type(e).__name__}")
else:
    print("[--  ] NEO4J_PASSWORD не задано: run_cypher повертатиме neo4j_not_configured")
sys.exit(0 if ok else 1)
