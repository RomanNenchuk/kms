import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import build_db  # noqa: E402


@pytest.fixture(scope="session")
def con(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "t.duckdb"
    c = build_db.build(path)
    yield c
    c.close()


@pytest.fixture(scope="session")
def frames():
    import pandas as pd
    d = ROOT / "data"
    return {t: pd.read_parquet(d / f"{t}.parquet") for t in build_db.LOAD_ORDER}
