"""Захист від «отруєних» описів інструментів (malicious tool description / rug pull).
Опис інструмента потрапляє в контекст моделі, тож зловмисний або змінений сервер може вставити туди інструкції.
Перевірка на боці КЛІЄНТА (агента): а) інструмент має бути в allowlist; б) sha256 опису й схеми збігається з «пін-файлом»,
знятим із довіреної збірки сервера (scripts/pin_tools.py); в) опис не містить ознак ін'єкції."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mcp_server import guards

PINS = Path(__file__).resolve().parent.parent / "docs" / "tool_pins.json"


def fingerprint(tool: dict) -> str:
    blob = json.dumps({"d": tool["description"], "s": tool["schema"]}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def vet(tools: list[dict], pins_path: Path = PINS) -> tuple[list[dict], list[dict]]:
    """Повертає (дозволені, відхилені з причиною)."""
    pins = json.loads(pins_path.read_text(encoding="utf-8"))
    ok, rejected = [], []
    for t in tools:
        if t["name"] not in pins:
            rejected.append({"name": t["name"], "reason": "not_in_allowlist"})
        elif fingerprint(t) != pins[t["name"]]:
            rejected.append({"name": t["name"], "reason": "description_or_schema_changed"})
        elif guards.scan_untrusted(t["description"]):
            rejected.append({"name": t["name"], "reason": "injection_in_description"})
        else:
            ok.append(t)
    return ok, rejected
