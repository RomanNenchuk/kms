"""Метрики top-k для бінарної релевантності. recs — впорядкований список doc_id, rel — множина релевантних."""
import math
import numpy as np


def precision_at_k(recs, rel, k=5):
    return sum(d in rel for d in recs[:k]) / k


def recall_at_k(recs, rel, k=5):
    return sum(d in rel for d in recs[:k]) / len(rel) if rel else 0.0


def ndcg_at_k(recs, rel, k=10):
    dcg = sum(1.0 / math.log2(i + 2) for i, d in enumerate(recs[:k]) if d in rel)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(rel), k)))
    return dcg / idcg if idcg else 0.0


def novelty_at_k(recs, p_item, k=5):
    """Середня самоінформація -log2 p(d): вище = менш популярні документи."""
    r = recs[:k]
    return float(np.mean([-math.log2(p_item[d]) for d in r])) if r else 0.0


def coverage(rec_lists, catalog, k=5):
    """Частка каталогу, що потрапила хоча б одному користувачу в top-k."""
    return len({d for r in rec_lists for d in r[:k]}) / len(catalog)


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 0.0


def ild(recs, topics, k=5):
    """Intra-list diversity: 1 - середня парна схожість Жаккара за темами (вище = різноманітніше)."""
    r = recs[:k]
    pairs = [(i, j) for i in range(len(r)) for j in range(i + 1, len(r))]
    return float(np.mean([1 - jaccard(topics[r[i]], topics[r[j]]) for i, j in pairs])) if pairs else 0.0


def gini(counts):
    x = np.sort(np.asarray(counts, float))
    if x.sum() == 0:
        return 0.0
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum()))


def bootstrap_ci(values, B=2000, seed=42, alpha=0.05):
    """Перцентильний 95 % інтервал середнього (ресемплінг користувачів)."""
    v = np.asarray(values, float)
    if len(v) == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, len(v), (B, len(v)))].mean(axis=1)
    return float(v.mean()), float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def paired_diff_ci(a, b, B=2000, seed=42, alpha=0.05):
    return bootstrap_ci(np.asarray(a, float) - np.asarray(b, float), B, seed, alpha)
