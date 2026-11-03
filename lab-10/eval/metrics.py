"""Метрики для Результату 5: recall@k, MRR, nDCG@k, Cohen's kappa."""
import math


def recall_at_k(ranked, relevant, k):
    if not relevant:
        return None  # запити без відповіді рахуємо окремо
    return len(set(ranked[:k]) & set(relevant)) / len(set(relevant))


def mrr(ranked, relevant):
    if not relevant:
        return None
    for i, d in enumerate(ranked, 1):
        if d in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked, relevant, k):
    if not relevant:
        return None
    dcg = sum(1 / math.log2(i + 1) for i, d in enumerate(ranked[:k], 1) if d in relevant)
    idcg = sum(1 / math.log2(i + 1) for i in range(1, min(len(relevant), k) + 1))
    return dcg / idcg


def cohen_kappa(a, b):
    from sklearn.metrics import cohen_kappa_score
    return cohen_kappa_score(a, b)
