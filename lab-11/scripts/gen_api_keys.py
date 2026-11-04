#!/usr/bin/env python3
"""Генерує API-ключі для ролей viewer / analyst / admin.
  - у .env пишеться лише SHA-256 хеш (рядок API_KEYS=...), відкритий ключ там не зберігається;
  - відкриті ключі друкуються і пишуться в .demo_keys (chmod 600, у .gitignore) для демо-скрипта.
Запуск:  python scripts/gen_api_keys.py            (лише показати)
         python scripts/gen_api_keys.py --write    (оновити .env і .demo_keys)"""
import hashlib, os, pathlib, secrets, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROLES = ["viewer", "analyst", "admin"]
keys = {r: "ak_" + secrets.token_urlsafe(24) for r in ROLES}
line = "API_KEYS=" + ",".join(f"{hashlib.sha256(k.encode()).hexdigest()}:{r}" for r, k in keys.items())
exports = "\n".join(f"export {r.upper()}_KEY={k}" for r, k in keys.items())
print(line + "\n\n" + exports)
if "--write" in sys.argv:
    env = ROOT / ".env"
    lines = [l for l in env.read_text().splitlines() if not l.startswith("API_KEYS=")] if env.exists() else []
    env.write_text("\n".join(lines + [line]) + "\n")
    demo = ROOT / ".demo_keys"
    demo.write_text(exports + "\n")
    os.chmod(demo, 0o600)
    print("\nОновлено .env (хеші) і .demo_keys (відкриті ключі, не комітити). Перезапусти сервер, щоб підхопити нові ключі.")
