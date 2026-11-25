"""Параметри СР16. Усе, що настроюється, — тут."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INTER = ROOT / "data" / "interactions"
GRAPH = ROOT / "data" / "graph"
KB_CORPUS = ROOT / "data" / "kb" / "corpus.jsonl"
E5_JSON = ROOT / "data" / "indexes" / "e5_hierarchical.json"
E5_NPY = ROOT / "data" / "indexes" / "e5_hierarchical.npy"
RESULTS = ROOT / "results"

SEED = 42
BOOTSTRAP_B = 2000
K_P, K_NDCG, K_COV = 5, 10, 5            # precision@5, nDCG@10, coverage@5 (як у завданні)

# view — лише перегляд (не сигнал інтересу); open/save/helpful — позитивні події
EVENT_WEIGHT = {"view": 0.0, "open": 1.0, "save": 2.0, "helpful": 2.0}
POSITIVE = tuple(e for e, w in EVENT_WEIGHT.items() if w > 0)
ACCESS_RANK = {"public": 0, "internal": 1, "restricted": 2}

MMR_LAMBDA = 0.7                          # для заходу «різноманіття» в ethics.py
