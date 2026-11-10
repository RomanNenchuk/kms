import os, sys
from pathlib import Path

os.environ.setdefault("EMBED_BACKEND", "bm25")        # тести не завантажують модель embeddings
os.environ.setdefault("ACCESS_LEVEL", "public")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
