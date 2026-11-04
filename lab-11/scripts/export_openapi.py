#!/usr/bin/env python3
"""Зберігає специфікацію OpenAPI у docs/openapi.json (сервер і моделі для цього не потрібні)."""
import json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from api.main import app
out = ROOT / "docs" / "openapi.json"
out.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
print("saved", out, "paths:", list(app.openapi()["paths"]))
