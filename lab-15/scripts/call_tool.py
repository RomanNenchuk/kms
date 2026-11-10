"""Виклик MCP-інструмента з терміналу (замість Inspector, без Node.js).

  python scripts/call_tool.py --list
  python scripts/call_tool.py graph_lookup '{"entity": "Fog at Lviv"}'
  python scripts/call_tool.py query_metric '{"metrics": ["on_time_rate"], "group_by": ["season"]}'
  python scripts/call_tool.py run_cypher '{"query": "MATCH (n) DETACH DELETE n"}'     # має бути blocked
  python scripts/call_tool.py graph_lookup '{"entity": "CA101-20261102", "hops": 2}' --level restricted
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.tools_client import McpTools  # noqa: E402


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tool", nargs="?")
    ap.add_argument("args", nargs="?", default="{}")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--level", default="public", choices=["public", "internal", "restricted"])
    a = ap.parse_args()
    async with McpTools(access_level=a.level) as t:
        if a.list or not a.tool:
            for s in await t.list_tools():
                print(f"{s['name']:14} read_only={s['read_only']}\n    {s['description'].splitlines()[0]}")
            return
        print(json.dumps(await t.call(a.tool, json.loads(a.args)), ensure_ascii=False, indent=2))

asyncio.run(main())
