import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "semantic"))
from check_consistency import CHECKS  # noqa: E402
from metrics import load_config, metric_sql  # noqa: E402

REQUIRED = {"name", "definition", "formula", "unit", "owner", "sources", "constraints", "status", "reviewed_at"}


def test_metrics_have_all_fields():
    ms = load_config()["metrics"]
    assert len(ms) >= 5
    for m in ms:
        assert REQUIRED <= set(m), f"{m['name']}: не вистачає {REQUIRED - set(m)}"


def test_unknown_metric_rejected():
    with pytest.raises(KeyError):
        metric_sql("no_such_metric")


def test_filter_operator_whitelist():
    with pytest.raises(ValueError):
        metric_sql("flights_count", filters=[("season", "; DROP TABLE x; --", "Winter")])


@pytest.mark.skipif(not (ROOT / "data" / "hub.duckdb").exists(), reason="спочатку make load")
@pytest.mark.parametrize("name,fn", CHECKS)
def test_consistency(name, fn):
    assert fn(), name
