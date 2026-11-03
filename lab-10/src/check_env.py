"""Перевірка середовища: python -m src.check_env"""
import importlib, sys, time

print("Python", sys.version.split()[0])
for m in ["sentence_transformers", "faiss", "chromadb", "rank_bm25",
          "numpy", "pandas", "sklearn", "dotenv", "google.genai"]:
    try:
        importlib.import_module(m)
        print(f"  OK  {m}")
    except Exception as e:
        print(f"  ERR {m}: {e}")

from .config import EMB_MODELS, RERANKER
from sentence_transformers import SentenceTransformer, CrossEncoder

for name, mid in EMB_MODELS.items():
    t = time.time()
    m = SentenceTransformer(mid)
    v = m.encode(["query: рейс затримано через погоду"])
    print(f"  OK  {name} ({mid}) dim={v.shape[1]} {time.time()-t:.1f}s")

t = time.time()
ce = CrossEncoder(RERANKER)
s = ce.predict([("затримка рейсу", "Рейс затримано через туман")])
print(f"  OK  reranker score={float(s[0]):.3f} {time.time()-t:.1f}s")

import os
from dotenv import load_dotenv
load_dotenv()
print("  GEMINI_API_KEY:", "задано" if os.getenv("GEMINI_API_KEY", "your_key_here") != "your_key_here" else "НЕ задано (.env)")
