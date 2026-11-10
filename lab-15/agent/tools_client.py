"""Клієнт MCP (stdio): запускає mcp_server як дочірній процес і викликає інструменти."""
from __future__ import annotations

import json
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent


class McpTools:
    def __init__(self, access_level: str = "public", defenses: str = "on", extra_env: dict | None = None,
                 poison: dict | None = None):
        """poison — лише для red teaming: імітує скомпрометований сервер: {"add": [tool,...], "modify": {name: суфікс опису}}."""
        import os
        self.defenses, self.poison, self.rejected_tools, self.evil_calls = defenses, poison or {}, [], []
        env = {**os.environ, "ACCESS_LEVEL": access_level, "DEFENSES": defenses, **(extra_env or {})}
        self.params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"], cwd=str(ROOT), env=env)
        self._stack = AsyncExitStack()
        self.session: ClientSession | None = None

    async def __aenter__(self):
        r, w = await self._stack.enter_async_context(stdio_client(self.params))
        self.session = await self._stack.enter_async_context(ClientSession(r, w))
        await self.session.initialize()
        return self

    async def __aexit__(self, *exc):
        await self._stack.aclose()

    async def list_tools(self):
        res = await self.session.list_tools()
        tools = [{"name": t.name, "description": t.description or "", "schema": t.inputSchema,
                  "read_only": bool(getattr(t.annotations, "readOnlyHint", False))} for t in res.tools]
        for t in tools:                                                   # імітація «rug pull»
            if t["name"] in self.poison.get("modify", {}):
                t["description"] += "\n" + self.poison["modify"][t["name"]]
        tools += [dict(t) for t in self.poison.get("add", [])]            # імітація підсадженого інструмента
        if self.defenses == "on":                                         # захист: перевірка за пін-файлом
            from .tool_vetting import vet
            tools, self.rejected_tools = vet(tools)
        return tools

    async def call(self, name: str, args: dict) -> dict:
        if any(t["name"] == name for t in self.poison.get("add", [])):   # «зовнішній» інструмент: фіктивна відповідь
            self.evil_calls.append({"name": name, "args": args})
            return {"ok": True, "text": "done", "citation_ids": []}
        res = await self.session.call_tool(name, args)
        if getattr(res, "structuredContent", None):
            data = res.structuredContent
            return data.get("result", data) if set(data) == {"result"} else data
        text = "".join(c.text for c in res.content if getattr(c, "text", None))
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"ok": not res.isError, "error": text[:500]} if res.isError else {"ok": True, "text": text}
