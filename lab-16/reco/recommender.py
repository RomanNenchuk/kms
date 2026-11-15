"""Єдина точка входу: Recommender.recommend(user_id, k, method=...). Навчається ЛИШЕ на train (ts < cutoff)."""
from __future__ import annotations
from . import config as C
from .data import Dataset, load
from .popularity import Popularity
from .graph_reco import GraphReco
from .embed_reco import EmbedReco
from .filters import apply_filters
from .hybrid import fuse

METHODS = ("pop", "graph", "embed", "hybrid")


class Recommender:
    def __init__(self, ds: Dataset | None = None, graph: C.GraphParams | None = None,
                 filters: C.FilterParams | None = None, hybrid: C.HybridParams | None = None):
        self.ds = ds or load()
        self.fp, self.hp = filters or C.FilterParams(), hybrid or C.HybridParams()
        train = self.ds.train
        self.models = {"pop": Popularity().fit(self.ds, train), "graph": GraphReco(graph).fit(self.ds, train),
                       "embed": EmbedReco().fit(self.ds, train)}
        self.seen = {u: {e["doc_id"] for e in ev} for u, ev in self.ds.positives(train).items()}

    def recommend(self, user_id, k=5, method="hybrid", as_of=None, use_filters=True, explain=True):
        """Повертає {"items": [...], "dropped": {doc: причина}}. as_of за замовчуванням = cutoff (стан на момент розбиття)."""
        if user_id not in self.ds.users:
            raise KeyError(user_id)
        user, as_of = self.ds.users[user_id], as_of or self.ds.cutoff[:10]
        if use_filters:
            cands, dropped = apply_filters(user, sorted(self.ds.items), self.ds, as_of, self.fp, self.seen.get(user_id, set()))
        else:
            cands, dropped = sorted(self.ds.items), {}
        scores = {m: mod.score(user_id) for m, mod in self.models.items()}
        if method == "hybrid":
            ranked = fuse({m: s for m, s in scores.items() if s}, cands, self.hp)
        elif method in self.models:
            s = scores[method]
            order = sorted(cands, key=lambda d: (-s.get(d, float("-inf")), d))
            ranked = [(d, s.get(d, 0.0), {}) for d in order if d in s]
        else:
            raise ValueError(f"method має бути одним із {METHODS}")
        items = []
        for pos, (d, sc, rk) in enumerate(ranked[:k], 1):
            row = {"rank": pos, "doc_id": d, "title": self.ds.items[d]["title"], "score": round(sc, 5), "ranks": rk}
            if explain:
                row["path"] = self.models["graph"].path(user_id, d) if method in ("graph", "hybrid") else \
                    self.models["embed"].path(user_id, d) if method == "embed" else None
            items.append(row)
        return {"user_id": user_id, "method": method, "as_of": as_of, "items": items, "dropped": dropped}
