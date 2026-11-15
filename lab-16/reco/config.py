"""Параметри рекомендаційного модуля (ЛР 16). Усе, що настроюється, — тут, а не в коді підходів."""
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH_DIR = ROOT / "data" / "graph"
INTER_DIR = ROOT / "data" / "interactions"
KB_INDEX_JSON = ROOT / "data" / "indexes" / "e5_hierarchical.json"
KB_INDEX_NPY = ROOT / "data" / "indexes" / "e5_hierarchical.npy"
SEED = 42

# вага події для профілю користувача й популярності; view — лише перегляд, не сигнал інтересу
EVENT_WEIGHT = {"view": 0.0, "open": 1.0, "save": 2.0, "helpful": 2.0}
POSITIVE_EVENTS = tuple(e for e, w in EVENT_WEIGHT.items() if w > 0)
ACCESS_RANK = {"public": 0, "internal": 1, "restricted": 2}   # як у mcp_server/config.py LEVELS


@dataclass
class GraphParams:
    alpha: float = 1.0   # вага теми з ролі користувача
    beta: float = 1.0    # вага теми з експозиції авіакомпанії до ризиків (шляхи через рейси)
    gamma: float = 1.0   # вага теми з власної історії (train)


@dataclass
class FilterParams:
    require_verified: bool = True    # лише документи verified=true
    max_age_days: int = 540          # свіжість: last_reviewed не старше N днів від as_of
    enforce_access: bool = True      # sensitivity документа <= access_level користувача
    exclude_seen: bool = True        # не рекомендувати документи, де вже були позитивні події в train


@dataclass
class HybridParams:
    method: str = "rrf"              # "rrf" | "weighted"
    weights: dict = field(default_factory=lambda: {"graph": 1.0, "embed": 1.0, "pop": 0.5})
    rrf_k: int = 60                  # константа RRF
