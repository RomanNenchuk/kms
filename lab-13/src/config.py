"""Спільна конфігурація: шляхи, seed, параметри LLM. Ключ береться лише з .env."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

RAW_DIR = ROOT / "data" / "raw"
GOLD_PATH = ROOT / "data" / "gold.jsonl"
LLM_LOG_DIR = ROOT / "llm_log"
SEED = int(os.getenv("SEED", "42"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
SPACY_MODEL = "en_core_web_sm"


def gemini_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError("GEMINI_API_KEY не задано: скопіюй .env.example у .env і встав ключ.")
    return key
