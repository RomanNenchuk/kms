"""Експорт JSON-схем MCP-інструментів у docs/tool_schemas.json (матеріал для docs/agent_spec.md, Результат 1 C1)."""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent.tools_client import McpTools  # noqa: E402


async def main():
    async with McpTools() as t:
        specs = await t.list_tools()
    out = ROOT / "docs" / "tool_schemas.json"
    out.write_text(json.dumps(specs, ensure_ascii=False, indent=2), encoding="utf-8")
    for s in specs:
        print(f"{s['name']:14} read_only={s['read_only']}")
    print("->", out)


asyncio.run(main())
