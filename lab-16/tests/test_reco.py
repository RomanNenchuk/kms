import datetime as dt
import pytest
from reco import config as C
from reco.recommender import Recommender
from reco.hybrid import fuse
from reco.filters import apply_filters


@pytest.fixture(scope="module")
def rec():
    return Recommender()


def test_train_has_no_future(rec):
    assert all(e["ts"] < rec.ds.cutoff for e in rec.ds.train)
    assert all(e["ts"] >= rec.ds.cutoff for e in rec.ds.test)
    # популярність не бачить test: нові документи мають нульову популярність
    pop = rec.models["pop"].score("U001")
    assert all(pop[d] == 0 for d in rec.ds.split["new_items"])


@pytest.mark.parametrize("method", ["pop", "graph", "embed", "hybrid"])
def test_all_methods_return_k(rec, method):
    out = rec.recommend("U001", 5, method)
    assert len(out["items"]) == 5 and out["items"][0]["rank"] == 1


def test_deterministic(rec):
    assert rec.recommend("U002", 5, "hybrid") == rec.recommend("U002", 5, "hybrid")


def test_filters_remove_bad_docs(rec):
    ds = rec.ds
    cands, dropped = apply_filters({"access_level": "public"}, sorted(ds.items), ds, ds.end[:10], C.FilterParams())
    for d in ds.split["unverified_items"]:
        assert dropped[d] == "not_verified"
    for d in ds.split["stale_items"]:
        assert dropped[d] in ("stale", "access_denied", "not_verified")
    assert dropped["en_montreal_convention"] in ("access_denied", "not_published_yet")
    assert not set(cands) & set(dropped)


def test_access_levels(rec):
    ds = rec.ds
    pub = next(u for u, r in ds.users.items() if r["access_level"] == "public")
    ids = {i["doc_id"] for i in rec.recommend(pub, 36, "hybrid", as_of=ds.end[:10])["items"]}
    assert all(ds.items[d]["sensitivity"] == "public" for d in ids)


def test_exclude_seen(rec):
    seen = rec.seen["U001"]
    assert not seen & {i["doc_id"] for i in rec.recommend("U001", 36, "hybrid")["items"]}


def test_hybrid_params_change_ranking():
    a, b = C.HybridParams(weights={"graph": 1, "embed": 0.01, "pop": 0.01}), C.HybridParams(weights={"graph": 0.01, "embed": 1, "pop": 0.01})
    m = {"graph": {"a": 3, "b": 2, "c": 1}, "embed": {"a": 1, "b": 2, "c": 3}, "pop": {"a": 1, "b": 1, "c": 1}}
    assert fuse(m, "abc", a)[0][0] == "a" and fuse(m, "abc", b)[0][0] == "c"
    for method in ("rrf", "weighted"):
        assert fuse(m, "abc", C.HybridParams(method=method))


def test_graph_path_is_a_real_path(rec):
    it = rec.recommend("U003", 3, "graph")["items"][0]
    steps = it["path"]["steps"]
    assert steps[0][0] == "User:U003" and steps[-1][2] == f"Doc:{it['doc_id']}"
    assert all(steps[i][2] == steps[i + 1][0] for i in range(len(steps) - 1))


def test_cold_user_has_no_embed_profile(rec):
    cold = rec.ds.split["cold_users"][0]
    assert rec.models["embed"].score(cold) == {}
    assert rec.recommend(cold, 5, "hybrid")["items"]   # graph (роль) + pop працюють без історії
