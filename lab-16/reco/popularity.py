"""Baseline: популярність (зважена сума позитивних подій у train). Однакова для всіх користувачів."""
from collections import Counter
from . import config as C


class Popularity:
    name = "pop"

    def fit(self, ds, train):
        self.cnt = Counter()
        for e in train:
            self.cnt[e["doc_id"]] += C.EVENT_WEIGHT[e["event"]]
        self.docs = list(ds.items)
        return self

    def score(self, user_id, history=None):
        return {d: float(self.cnt.get(d, 0.0)) for d in self.docs}

    def path(self, user_id, doc_id):
        return None
