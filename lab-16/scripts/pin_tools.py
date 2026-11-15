"""Зняти «відбитки» опису й схеми кожного інструмента з ДОВІРЕНОГО сервера -> docs/tool_pins.json.
Запускати після кожної свідомої зміни інструментів (make pin) і комітити файл."""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent.tools_client import McpTools          # noqa: E402
from agent.tool_vetting import fingerprint, PINS  # noqa: E402


async def main():
    async with McpTools(defenses="off") as t:      # defenses=off: щоб не фільтрувати власний список
        specs = await t.list_tools()
    pins = {s["name"]: fingerprint(s) for s in specs}
    PINS.write_text(json.dumps(pins, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"записано {len(pins)} відбитків -> {PINS}")

asyncio.run(main())
