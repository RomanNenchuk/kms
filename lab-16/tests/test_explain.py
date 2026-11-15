import random
import pytest
from reco.explain import Explainer
from reco.recommender import Recommender


@pytest.fixture(scope="module")
def env():
    rec = Recommender()
    return rec, Explainer(rec.ds)


def _paths(rec, method):
    out = []
    for u in sorted(rec.ds.split["warm_eval_users"])[:15]:
        for it in rec.recommend(u, 5, method, as_of=rec.ds.end[:10])["items"]:
            if it.get("path"):
                out.append((it["doc_id"], it["path"]))
    return out


@pytest.mark.parametrize("method", ["hybrid", "embed"])
def test_template_always_passes_check(env, method):
    rec, ex = env
    paths = _paths(rec, method)
    assert paths and all(ex.check(ex.template(p, d), p, d)["ok"] for d, p in paths)


def test_all_path_components_covered(env):
    rec, ex = env
    comps = {p["component"] for m in ("hybrid", "embed") for _, p in _paths(rec, m)}
    assert {"role", "exposure", "history", "embed"} <= comps


def test_check_detects_foreign_quoted_entity(env):
    rec, ex = env
    d, p = _paths(rec, "hybrid")[0]
    bad = ex.template(p, d).replace("«" + ex.surface("Topic", p["topic"]) + "»", "«Fog at Lviv»")
    chk = ex.check(bad, p, d)
    assert not chk["ok"] and "Fog at Lviv" in chk["unknown_quoted"]


def test_check_detects_unquoted_foreign_entity_and_number(env):
    rec, ex = env
    d, p = _paths(rec, "hybrid")[0]
    base = ex.template(p, d)
    assert ex.check(base + " Також варто прочитати Airport slot.", p, d)["foreign"] == ["Airport slot"]
    assert ex.check(base + " Це стосується 3 рейсів.", p, d)["foreign_numbers"] == ["3"]
    assert "target_doc" in ex.check("Рекомендовано без назви.", p, d)["missing"]


def test_mutations_are_detected(env):
    rec, ex = env
    rng = random.Random(42)
    for d, p in _paths(rec, "hybrid")[:30]:
        assert not ex.check(ex.mutate(ex.template(p, d), p, d, rng), p, d)["ok"]


def test_fallback_when_paraphraser_hallucinates(env):
    rec, ex = env
    d, p = _paths(rec, "hybrid")[0]
    good = lambda base, ents: base.replace("Рекомендовано", "Ми радимо")
    bad = lambda base, ents: base + " Також «Montreal Convention» дуже важлива."
    assert ex.explain(p, d, good)["source"] == "llm"
    r = ex.explain(p, d, bad)
    assert r["source"] == "template_fallback" and r["text"] == ex.template(p, d)


def test_norm_handles_typographic_variants(env):
    from reco.explain import norm
    rec, ex = env
    d, p = _paths(rec, "hybrid")[0]
    base = ex.template(p, d)
    title = ex.ds.items[d]["title"]
    for variant in (title.replace(" ", " "), title.replace(" ", " "), title.replace(" ", " ​")):
        assert ex.check(base.replace(title, variant), p, d)["ok"], repr(variant)
    assert norm("operator’s") == "operator's"


def test_retry_and_throttle_helpers():
    from reco.explain import call_with_retry
    calls, slept = [], []
    def flaky():
        calls.append(1)
        if len(calls) < 3: raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return "ok"
    assert call_with_retry(flaky, sleep=slept.append) == "ok" and slept == [5, 10]
    with pytest.raises(ValueError):
        call_with_retry(lambda: (_ for _ in ()).throw(ValueError("x")), sleep=slept.append)
