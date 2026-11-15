"""Гібридне ранжування: зважена сума min-max нормованих оцінок або RRF (Reciprocal Rank Fusion)."""


def _ranks(scores: dict, cands):
    order = sorted(cands, key=lambda d: (-scores.get(d, float("-inf")), d))
    return {d: i + 1 for i, d in enumerate(order)}


def fuse(per_method: dict, cands, params):
    """per_method: {name: {doc: score}}; повертає [(doc, fused_score, {name: rank})] за спаданням."""
    cands = list(cands)
    w = {m: params.weights.get(m, 1.0) for m in per_method if per_method[m]}
    ranks = {m: _ranks(per_method[m], cands) for m in w}
    fused = {}
    if params.method == "rrf":
        for d in cands:
            fused[d] = sum(w[m] / (params.rrf_k + ranks[m][d]) for m in w)
    elif params.method == "weighted":
        norm = {}
        for m in w:
            vals = [per_method[m].get(d, 0.0) for d in cands]
            lo, hi = min(vals), max(vals)
            norm[m] = {d: (per_method[m].get(d, 0.0) - lo) / (hi - lo) if hi > lo else 0.0 for d in cands}
        for d in cands:
            fused[d] = sum(w[m] * norm[m][d] for m in w)
    else:
        raise ValueError(params.method)
    order = sorted(cands, key=lambda d: (-fused[d], d))
    return [(d, fused[d], {m: ranks[m][d] for m in w}) for d in order]
