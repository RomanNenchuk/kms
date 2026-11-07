"""Клієнти LLM: Gemini (Google AI Studio) і ReplayClient (офлайн-тести без мережі/ключа)."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

try:  # .env з ключем (не комітити)
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


@dataclass
class LLMResponse:
    text: str
    model: str
    params: dict = field(default_factory=dict)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_s: float = 0.0


class GeminiClient:
    """Виклик Gemini через пакет google-genai. Ключ: GEMINI_API_KEY; модель: GEMINI_MODEL."""

    def __init__(self, model: str | None = None, temperature: float = 0.0, seed: int = 42):
        from google import genai  # імпорт тут, щоб офлайн-тести не вимагали пакета
        from google.genai import types

        self._types = types
        self.model = model or os.environ.get("GEMINI_MODEL")
        if not self.model:
            raise RuntimeError("Задайте GEMINI_MODEL у .env (назва актуальної Flash-моделі з Google AI Studio).")
        if not os.environ.get("GEMINI_API_KEY"):
            raise RuntimeError("Задайте GEMINI_API_KEY у .env (ключ із Google AI Studio).")
        self.client = genai.Client()  # бере GEMINI_API_KEY зі середовища
        self.temperature, self.seed = temperature, seed

    def generate(self, system: str, user: str, key: str | None = None) -> LLMResponse:
        cfg = self._types.GenerateContentConfig(system_instruction=system, temperature=self.temperature, seed=self.seed)
        last_err = None
        for attempt in range(4):  # безкоштовний рівень має ліміти запитів: повтор з паузою
            t0 = time.time()
            try:
                r = self.client.models.generate_content(model=self.model, contents=user, config=cfg)
                um = getattr(r, "usage_metadata", None)
                return LLMResponse(
                    text=r.text or "", model=self.model,
                    params={"temperature": self.temperature, "seed": self.seed},
                    prompt_tokens=getattr(um, "prompt_token_count", None),
                    completion_tokens=getattr(um, "candidates_token_count", None),
                    latency_s=round(time.time() - t0, 3),
                )
            except Exception as e:  # noqa: BLE001
                last_err = e
                if any(s in str(e) for s in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")):
                    time.sleep(5 * (attempt + 1))
                    continue
                raise
        raise RuntimeError(f"Gemini недоступний після повторів: {last_err}")


class ReplayClient:
    """Повертає заздалегідь записані відповіді за id питання. Лише для тестів конвеєра."""

    def __init__(self, path: str | Path):
        self.answers = json.loads(Path(path).read_text(encoding="utf-8"))
        self.model = "replay"

    def generate(self, system: str, user: str, key: str | None = None) -> LLMResponse:
        return LLMResponse(text=self.answers[key], model="replay", params={}, prompt_tokens=0, completion_tokens=0)
