"""Єдине місце для налаштувань. SEED фіксуємо для відтворюваності."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
KB = ROOT / "kb"
INDEXES = ROOT / "indexes"
EVAL = ROOT / "eval"
LLM_LOG = ROOT / "llm_log"
CLAIMS = ROOT / "claims" / "claims.csv"

SEED = 42

# Дві моделі embeddings для Результату 3 (обидві багатомовні, працюють на CPU)
EMB_MODELS = {
    "e5": "intfloat/multilingual-e5-small",
    "minilm": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
}
# Для e5 потрібні префікси "query: " та "passage: "
E5_QUERY_PREFIX = "query: "
E5_PASSAGE_PREFIX = "passage: "

# Cross-encoder для reranking (багатомовний)
RERANKER = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

# HNSW
HNSW_M = 32
HNSW_EF_CONSTRUCTION = 200
HNSW_EF_SEARCH = 64

RRF_K = 60
