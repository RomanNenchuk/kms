"""Обгортка над Gemini з обов'язковим логуванням (протокол «LLM-експерт»).

Кожен виклик пишеться в llm_log/YYYY-MM-DD.jsonl:
дата, модель, параметри, версія підказки, сирий вихід, рішення людини.
Поле human_decision спочатку 'pending' — заповнюєш вручну після перегляду.

Безкоштовний тариф має ліміт запитів на хвилину (429): робимо паузу між викликами
і повторюємо запит із очікуванням, яке просить сам Gemini.
"""
import json, os, re, time, datetime as dt
from dotenv import load_dotenv
from google import genai
from google.genai import types, errors
from .config import LLM_LOG, SEED

load_dotenv()
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
MIN_INTERVAL = float(os.getenv("GEMINI_MIN_INTERVAL", "4.5"))   # 15 запитів/хв => мінімум 4 с між викликами
MAX_RETRIES = 8
_client = None
_last_call = 0.0


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def ask(prompt: str, prompt_version: str, temperature: float = 0.3,
        system: str | None = None, json_mode: bool = False) -> str:
    global _last_call
    cfg = types.GenerateContentConfig(
        temperature=temperature, seed=SEED,
        system_instruction=system,
        response_mime_type="application/json" if json_mode else None,
    )
    for attempt in range(MAX_RETRIES):
        pause = MIN_INTERVAL - (time.time() - _last_call)
        if pause > 0:
            time.sleep(pause)
        _last_call = time.time()
        try:
            resp = _get_client().models.generate_content(model=MODEL, contents=prompt, config=cfg)
            break
        except errors.ClientError as e:
            msg = str(e)
            if "429" not in msg and getattr(e, "code", None) != 429:
                raise
            if "PerDay" in msg or "per day" in msg.lower():
                raise RuntimeError("Вичерпано ДОБОВИЙ ліміт Gemini; спробуй завтра або іншу модель (GEMINI_MODEL у .env).") from e
            m = re.search(r"retry in ([\d.]+)s", msg)
            delay = float(m.group(1)) + 2 if m else 15 * (attempt + 1)
            print(f"   [429] ліміт Gemini, чекаю {delay:.0f} с (спроба {attempt + 1}/{MAX_RETRIES})...", flush=True)
            time.sleep(delay)
        except errors.ServerError as e:          # 500/503/504: тимчасове перевантаження на боці Google
            delay = min(10 * (attempt + 1), 60)
            print(f"   [{getattr(e, 'code', '5xx')}] Gemini перевантажений, чекаю {delay} с (спроба {attempt + 1}/{MAX_RETRIES})...", flush=True)
            time.sleep(delay)
    else:
        raise RuntimeError("Gemini: перевищено кількість повторів (ліміт запитів або перевантаження сервера).")
    text = resp.text or ""
    _log(prompt, prompt_version, temperature, system, text)
    return text


def _log(prompt, version, temperature, system, raw):
    LLM_LOG.mkdir(exist_ok=True)
    now = dt.datetime.now()
    rec = {
        "timestamp": now.isoformat(timespec="seconds"),
        "model": MODEL,
        "params": {"temperature": temperature, "seed": SEED},
        "prompt_version": version,
        "system": system,
        "prompt": prompt,
        "raw_output": raw,
        "human_decision": "pending",
    }
    path = LLM_LOG / f"{now:%Y-%m-%d}.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
