"""Адаптери LLM з викликом інструментів. Нейтральний формат історії (його використовує agent.py):
  {"role":"user","text":...} | {"role":"model","text":...,"calls":[{"name","args"}],"raw":<внутрішнє>} |
  {"role":"tool","results":[{"name","response":{...}}]}
LLM.step(history, tools) -> {"text", "calls", "usage":{"prompt","output","total"}, "raw"}"""
from __future__ import annotations

import os
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


def inline_refs(schema: dict) -> dict:
    """Розгортає $ref/$defs і прибирає службові поля — Gemini надійніше приймає «плоску» JSON-схему."""
    defs = schema.get("$defs", {})

    def walk(n):
        if isinstance(n, dict):
            if "$ref" in n:
                return walk(defs[n["$ref"].split("/")[-1]])
            return {k: walk(v) for k, v in n.items() if k not in ("$defs", "title", "additionalProperties")}
        if isinstance(n, list):
            return [walk(x) for x in n]
        return n
    return walk(schema)


class GeminiLLM:
    """Gemini через google-genai (ключ GEMINI_API_KEY, модель GEMINI_MODEL у .env)."""

    def __init__(self, system: str, model: str | None = None, temperature: float = 0.0, seed: int = 42):
        from google import genai
        from google.genai import types
        self.types = types
        self.model = model or os.environ.get("GEMINI_MODEL")
        if not self.model or not os.environ.get("GEMINI_API_KEY"):
            raise RuntimeError("Задайте GEMINI_API_KEY і GEMINI_MODEL у .env")
        self.client = genai.Client()
        self.system, self.temperature, self.seed = system, temperature, seed
        self.params = {"temperature": temperature, "seed": seed}

    def _contents(self, history):
        t, out = self.types, []
        for m in history:
            if m["role"] == "user":
                out.append(t.Content(role="user", parts=[t.Part(text=m["text"])]))
            elif m["role"] == "model":
                if m.get("raw") is not None:      # зберігаємо оригінал (потрібен для thought signatures)
                    out.append(m["raw"])
                    continue
                parts = [t.Part(text=m["text"])] if m.get("text") else []
                parts += [t.Part(function_call=t.FunctionCall(name=c["name"], args=c["args"])) for c in m.get("calls", [])]
                out.append(t.Content(role="model", parts=parts))
            else:
                out.append(t.Content(role="user", parts=[
                    t.Part(function_response=t.FunctionResponse(name=r["name"], response=r["response"])) for r in m["results"]]))
        return out

    def step(self, history, tools):
        t = self.types
        decls = [t.FunctionDeclaration(name=x["name"], description=x["description"],
                                       parameters_json_schema=inline_refs(x["schema"])) for x in tools]
        cfg = t.GenerateContentConfig(
            system_instruction=self.system, temperature=self.temperature, seed=self.seed,
            tools=[t.Tool(function_declarations=decls)],
            automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True))
        last = None
        for attempt in range(4):
            try:
                r = self.client.models.generate_content(model=self.model, contents=self._contents(history), config=cfg)
                break
            except Exception as e:  # ліміти безкоштовного рівня
                last = e
                if any(s in str(e) for s in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")):
                    time.sleep(5 * (attempt + 1))
                    continue
                raise
        else:
            raise RuntimeError(f"Gemini недоступний після повторів: {last}")
        um = r.usage_metadata
        calls = [{"name": fc.name, "args": dict(fc.args or {})} for fc in (r.function_calls or [])]
        text = "".join(p.text for p in r.candidates[0].content.parts if getattr(p, "text", None) and not getattr(p, "thought", False)) if r.candidates else ""
        return {"text": text, "calls": calls, "raw": r.candidates[0].content if r.candidates else None,
                "usage": {"prompt": um.prompt_token_count or 0, "output": um.candidates_token_count or 0,
                          "total": um.total_token_count or 0}}


class FakeLLM:
    """Скриптований LLM для тестів без мережі: script = список відповідей {"text","calls"} по черзі."""

    model = "fake"
    params: dict = {}

    def __init__(self, script):
        self.script, self.i = list(script), 0

    def step(self, history, tools):
        r = self.script[min(self.i, len(self.script) - 1)]
        self.i += 1
        return {"text": r.get("text", ""), "calls": r.get("calls", []), "raw": None,
                "usage": {"prompt": 100, "output": 20, "total": 120}}
