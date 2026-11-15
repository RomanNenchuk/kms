"""Єдине місце налаштувань MCP-сервера. Усе, що впливає на безпеку, задається тут або в .env,
а НЕ параметрами інструментів: модель не може сама підвищити собі права."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # dotenv не обов'язковий для тестів
    pass

ROOT = Path(__file__).resolve().parent.parent
GRAPH_DIR = ROOT / "data" / "graph"
KB_CORPUS = ROOT / "data" / "kb" / "corpus.jsonl"
KB_OVERRIDES = ROOT / "data" / "kb" / "sensitivity_overrides.json"
KB_INDEX_JSON = ROOT / "data" / "indexes" / "e5_hierarchical.json"
KB_INDEX_NPY = ROOT / "data" / "indexes" / "e5_hierarchical.npy"
DUCKDB_PATH = ROOT / "data" / "warehouse" / "hub.duckdb"
METRICS_YML = ROOT / "semantic" / "metrics.yml"
LOG_DIR = ROOT / "logs"

SEED = 42

# --- права ------------------------------------------------------------------
LEVELS = {"public": 0, "internal": 1, "restricted": 2}
ACCESS_LEVEL = os.getenv("ACCESS_LEVEL", "public")          # рівень, з яким запущено сервер
if ACCESS_LEVEL not in LEVELS:
    raise ValueError(f"ACCESS_LEVEL має бути одним із {list(LEVELS)}")
# мінімальний рівень, потрібний для доступу до мітки вузла графа
LABEL_LEVEL = {"Passenger": "restricted", "Pilot": "internal"}
# ті самі обмеження для типів зв'язків і ключів властивостей (щоб не обійти через MATCH (n)-[:HAS_PASSENGER]->(p) RETURN p)
REL_LEVEL = {"HAS_PASSENGER": "restricted", "HAS_PILOT": "internal"}
PROP_LEVEL = {"passengerId": "restricted", "pilotId": "internal"}

# --- захисти (для Результату 4: порівняння «до/після») --------------------------
DEFENSES = os.getenv("DEFENSES", "on").lower() != "off"
# Тестовий корпус з «отруєними» фрагментами (лише для red teaming, див. tests/fixtures/); у проді не задається
KB_EXTRA = os.getenv("KB_EXTRA", "")


def effective_level(level: str | None = None) -> str:
    """Рівень доступу, з яким реально виконується запит. Коли захисти вимкнено (DEFENSES=off, лише для
    виміру «до»), контроль доступу не діє, тобто рівень ефективно «restricted»."""
    lvl = level or ACCESS_LEVEL
    return lvl if DEFENSES else "restricted"

# --- ліміти ---------------------------------------------------------------
MAX_ROWS = 50            # рядків з SQL / Cypher
MAX_EDGES = 40           # ребер підграфа
MAX_HOPS = 2
MAX_CHUNK_CHARS = 1500   # символів одного фрагмента KB у відповіді
MAX_K = 8

# --- Neo4j (необов'язково: потрібен лише для run_cypher) ----------------------
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
CYPHER_TIMEOUT_S = 10

# --- embeddings ---------------------------------------------------------------
EMBED_BACKEND = os.getenv("EMBED_BACKEND", "auto")   # auto | bm25
EMBED_MODEL = "intfloat/multilingual-e5-small"
E5_QUERY_PREFIX = "query: "
