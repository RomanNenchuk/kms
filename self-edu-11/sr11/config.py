"""Шляхи й налаштування. Усі шляхи беруться з цього модуля під час виклику (не через `from .config import X`),
щоб `selftest` міг підмінити каталог результатів."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAB11 = Path(os.getenv("LAB11_DIR", ROOT.parent / "lab-11")).resolve()
LAB10 = (ROOT.parent / "lab-10").resolve()

DATA = ROOT / "data"
QUERIES = DATA / "queries.jsonl"
CORPUS = LAB11 / "data" / "corpus.jsonl"
LLM_LOG = ROOT / "llm_log"

SEED = 42
CATEGORIES = ("simple", "multistep", "unanswerable", "conflict", "harmful")
CATEGORY_UK = {"simple": "прості", "multistep": "багатокрокові", "unanswerable": "без відповіді",
               "conflict": "суперечливі", "harmful": "шкідливі/атаки"}
VERDICTS = ("правильно", "частково", "ні")
CAUSES = ("пошук", "контекст", "генерація", "політика")

# каталог результатів можна підмінити (selftest, тести)
RESULTS = ROOT / "results"


def set_results_dir(path):
    global RESULTS
    RESULTS = Path(path)
    RESULTS.mkdir(parents=True, exist_ok=True)


def p(name):
    """Файл у каталозі результатів."""
    return RESULTS / name


def index_dir():
    """Каталог індексів: lab-11/indexes (якщо є), потім self-edu-11/indexes (symlink), потім lab-10/indexes (корпус ідентичний)."""
    for d in (LAB11 / "indexes", ROOT / "indexes", LAB10 / "indexes"):
        if (d / "e5_hierarchical.faiss").exists():
            return d.resolve()
    raise FileNotFoundError("Не знайдено e5_hierarchical.faiss ні в self-edu-11/indexes, ні в lab-11/indexes, ні в lab-10/indexes")


def load_env():
    """Підвантажує .env: спочатку self-edu-11/.env, потім lab-11/.env (лише відсутні змінні). Без залежності від dotenv."""
    for f in (ROOT / ".env", LAB11 / ".env"):
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
