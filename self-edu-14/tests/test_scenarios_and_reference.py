import json
import pytest
from src import measure, store

CFG = measure.load_cfg()
REF = {v: json.load(open(store.ROOT / "reference" / "lab14" / f"metrics_{v}.json", encoding="utf-8")) for v in ("baseline", "clean", "lab11")}
RES = {v: measure.measure(v, CFG) for v in ("baseline", "clean", "lab11")}


def test_config_complete():
    assert len(CFG["metrics"]) == 8
    assert len({m["dimension"] for m in CFG["metrics"]}) >= 6
    for m in CFG["metrics"]:
        assert set(m["thresholds"]) == {"chat", "audit"} and set(m["why"]) == {"chat", "audit"} and "=" in m["formula"]
        assert all(0 < t <= 1 for t in m["thresholds"].values())


@pytest.mark.parametrize("variant", ["baseline", "clean", "lab11"])
def test_matches_lab14_measurements(variant):
    """Мої реалізації дають ті самі значення й обсяги перевірки, що quality/measure.py з ЛР 14 (еталонні JSON у reference/lab14)."""
    ref = {m["id"]: m for m in REF[variant]["metrics"]}
    for m in RES[variant]["metrics"]:
        r = ref[m["lab14"]]
        assert m["value"] == pytest.approx(r["value"], abs=1e-4), (variant, m["id"])
        assert (m["n_checked"], m["n_bad"]) == (r["n_checked"], r["n_bad"]), (variant, m["id"])


@pytest.mark.parametrize("scenario", ["chat", "audit"])
def test_reference_store_passes_both_scenarios(scenario):
    """Пороги не дають хибних тривог на чистому еталоні lab11."""
    assert all(m["status"][scenario] == "ok" for m in RES["lab11"]["metrics"])


@pytest.mark.parametrize("scenario", ["chat", "audit"])
def test_baseline_with_defects_is_flagged(scenario):
    assert RES["baseline"]["summary"][scenario]["fail"] >= 1


def test_cleaning_does_not_worsen_any_metric():
    b = {m["id"]: m["value"] for m in RES["baseline"]["metrics"]}
    assert all(m["value"] >= b[m["id"]] - 1e-9 for m in RES["clean"]["metrics"])
