"""Ліміти та політики агента (узгодь із docs/agent_spec.md; значення можна змінити через .env)."""
import os
from dataclasses import dataclass


@dataclass
class Limits:
    max_steps: int = int(os.getenv("AGENT_MAX_STEPS", 8))             # викликів LLM за запит
    max_tool_calls: int = int(os.getenv("AGENT_MAX_TOOL_CALLS", 10))
    max_tokens: int = int(os.getenv("AGENT_MAX_TOKENS", 40000))       # сумарно prompt+output за запит
    max_seconds: float = float(os.getenv("AGENT_MAX_SECONDS", 90))
    max_tool_result_chars: int = 16000                                 # довші результати інструментів обрізаються
    max_repeat_call: int = 2                                           # однаковий виклик >2 разів -> зациклення


PRICE_IN = float(os.getenv("GEMINI_PRICE_IN", 0))     # USD за 1 млн токенів (free tier = 0)
PRICE_OUT = float(os.getenv("GEMINI_PRICE_OUT", 0))
