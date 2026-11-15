import math
from reco.metrics import precision_at_k, recall_at_k, ndcg_at_k, novelty_at_k, coverage, bootstrap_ci, paired_diff_ci


def test_precision_recall():
    recs, rel = ["a", "b", "c", "d", "e"], {"a", "c", "z"}
    assert precision_at_k(recs, rel, 5) == 2 / 5
    assert recall_at_k(recs, rel, 5) == 2 / 3
    assert recall_at_k(recs, set(), 5) == 0.0


def test_ndcg_perfect_and_worst():
    assert ndcg_at_k(["a", "b"], {"a", "b"}, 10) == 1.0
    assert ndcg_at_k(["x", "y"], {"a"}, 10) == 0.0
    assert math.isclose(ndcg_at_k(["x", "a"], {"a"}, 10), 1 / math.log2(3))


def test_novelty_and_coverage():
    assert novelty_at_k(["a"], {"a": 0.5}, 1) == 1.0
    assert coverage([["a", "b"], ["b", "c"]], ["a", "b", "c", "d"], 2) == 0.75


def test_bootstrap_deterministic_and_contains_mean():
    v = [0.0, 1.0, 0.0, 1.0, 1.0]
    m, lo, hi = bootstrap_ci(v)
    assert (m, lo, hi) == bootstrap_ci(v) and lo <= m <= hi
    d, lo, hi = paired_diff_ci([1, 1, 1, 1], [0, 0, 0, 0])
    assert d == lo == hi == 1.0
