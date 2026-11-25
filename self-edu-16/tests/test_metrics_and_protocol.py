import math
from src import config as C
from src.data import load
from src.metrics import precision_at_k, recall_at_k, ndcg_at_k, coverage, novelty_at_k, ild, gini
from src.models import build, rank
from src.protocol import seen_map, relevant_sets, next_day


def test_precision_recall_ndcg_by_hand():
    recs, rel = ["a", "b", "c", "d", "e"], {"a", "c", "z"}
    assert precision_at_k(recs, rel, 5) == 2 / 5
    assert recall_at_k(recs, rel, 5) == 2 / 3
    dcg = 1 / math.log2(2) + 1 / math.log2(4)
    idcg = 1 / math.log2(2) + 1 / math.log2(3) + 1 / math.log2(4)
    assert abs(ndcg_at_k(recs, rel, 10) - dcg / idcg) < 1e-12
    assert ndcg_at_k(["x"], set(), 10) == 0.0


def test_coverage_novelty_diversity_gini():
    assert coverage([["a", "b"], ["b", "c"]], {"a": 1, "b": 1, "c": 1, "d": 1}, 5) == 3 / 4
    assert novelty_at_k(["a"], {"a": 0.25}, 5) == 2.0
    assert ild(["a", "b"], {"a": ["t1"], "b": ["t1"]}, 2) == 0.0
    assert ild(["a", "b"], {"a": ["t1"], "b": ["t2"]}, 2) == 1.0
    assert gini([1, 1, 1, 1]) == 0.0 and gini([0, 0, 0, 4]) > 0.7


def test_temporal_split_has_no_overlap():
    ds = load()
    assert max(e["ts"] for e in ds.train) < ds.cutoff <= min(e["ts"] for e in ds.test)
    assert len(ds.train) + len(ds.test) == len(ds.events)


def test_candidates_exclude_future_seen_and_forbidden():
    ds = load(); seen = seen_map(ds); as_of = ds.cutoff[:10]
    for u in ds.split["warm_eval_users"]:
        c = ds.candidates(u, as_of, seen.get(u, set()))
        for d in c:
            it = ds.items[d]
            assert it["published_at"] <= as_of and d not in seen.get(u, set())
            assert C.ACCESS_RANK[it["sensitivity"]] <= C.ACCESS_RANK[ds.users[u]["access_level"]]


def test_models_trained_only_on_train_and_deterministic():
    ds = load(); m1, m2 = build(ds, ds.train), build(ds, ds.train)
    u = "U001"; cands = ds.candidates(u, ds.cutoff[:10], seen_map(ds).get(u, set()))
    for n in ("pop", "content", "graph", "embed", "random"):
        assert rank(m1[n], u, cands, 10) == rank(m2[n], u, cands, 10)
    # популярність справді рахується лише по train: документ, якого немає в train, має 0
    train_docs = {e["doc_id"] for e in ds.train if e["event"] in C.POSITIVE}
    assert all(v == 0 for d, v in m1["pop"].cnt.items() if d not in train_docs)


def test_cold_user_gets_empty_list_from_history_models():
    ds = load(); m = build(ds, ds.train); u = ds.split["cold_users"][0]
    assert m["content"].score(u) == {} and m["embed"].score(u) == {}
    assert m["graph"].score(u) != {}                      # граф має роль користувача
    assert m["role_pop"].score(u) != {}


def test_relevant_pairs_only_from_test_window():
    ds = load(); end = next_day(ds.end)
    rel, cands, _ = relevant_sets(ds, sorted(ds.split["warm_eval_users"]), ds.cutoff, end, ds.cutoff[:10], seen_map(ds))
    test_pos = ds.positives(ds.test)
    for u, r in rel.items():
        assert r <= test_pos[u] and r <= set(cands[u])
