"""Інтеграційний тест: справжній MCP-сервер по stdio + клієнт. Перевіряє C1/C2 Результату 2 (≥3 tools, read-only)."""
import asyncio
from agent.tools_client import McpTools


def test_server_tools_and_calls():
    async def go():
        async with McpTools(access_level="public") as t:
            specs = await t.list_tools()
            names = {s["name"] for s in specs}
            assert {"graph_lookup", "run_cypher", "vector_search", "list_metrics", "query_metric"} <= names
            assert all(s["read_only"] for s in specs), "усі інструменти мають бути readOnlyHint"
            g = await t.call("graph_lookup", {"entity": "Fog at Lviv"})
            assert g["found"] and g["edges"]
            v = await t.call("vector_search", {"query": "airport slot", "k": 2})
            assert v["results"]
            m = await t.call("query_metric", {"metrics": ["on_time_rate"], "group_by": ["season"]})
            assert m["row_count"] >= 1 and m["id"].startswith("sql:")
            bad = await t.call("run_cypher", {"query": "MATCH (n) DETACH DELETE n"})
            assert bad["ok"] is False and bad["blocked"]
    asyncio.run(go())
