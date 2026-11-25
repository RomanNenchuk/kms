"""Спільний протокол оцінки (використовують evaluate, cold_start, ethics).

  * часове розбиття: train = ts < cutoff, test = [cutoff, end]; моделі навчаються лише на train;
  * кандидати користувача: документи, опубліковані до as_of, доступні за рівнем доступу, ще не позитивно бачені в train;
  * релевантні = позитивні події (open/save/helpful) користувача в test на кандидатах;
  * користувач оцінюється, якщо має ≥ 1 релевантний документ; набір користувачів однаковий для всіх підходів."""
from __future__ import annotations
import datetime as dt
from collections import defaultdict
import numpy as np
from . import config as C
from .metrics import precision_at_k, recall_at_k, ndcg_at_k, novelty_at_k, ild, coverage, bootstrap_ci
from .models import rank


def next_day(d):
    return (dt.date.fromisoformat(d) + dt.timedelta(days=1)).isoformat()


def seen_map(ds):
    return {u: set(v) for u, v in ds.positives(ds.train).items()}


def relevant_sets(ds, users, start, end, as_of, seen, respect_access=True):
    pos = defaultdict(set)
    for e in ds.events:
        if start <= e["ts"] < end and e["event"] in C.POSITIVE:
            pos[e["user_id"]].add(e["doc_id"])
    rel, cands, why = {}, {}, defaultdict(int)
    for u in users:
        cands[u] = ds.candidates(u, as_of, seen.get(u, frozenset()), respect_access)
        r = pos.get(u, set()) & set(cands[u])
        for d in pos.get(u, set()) - r:      # чому позитивна подія в test не стала «релевантним кандидатом»
            it = ds.items[d]
            why["not_published_yet" if it["published_at"] > as_of else
                "access_denied" if respect_access and C.ACCESS_RANK[it["sensitivity"]] > C.ACCESS_RANK[ds.users[u]["access_level"]] else
                "already_seen_in_train"] += 1
        if r:
            rel[u] = r
    return rel, cands, {"relevant_pairs": sum(map(len, rel.values())), "dropped_pairs": dict(why), "n_users": len(rel)}


def run(model, users, rel, cands, p_item, topics, fallback=None, k=10):
    per, lists = {}, {}
    for u in users:
        recs = rank(model, u, cands[u], k, fallback)
        lists[u] = recs
        per[u] = {"p5": precision_at_k(recs, rel[u], C.K_P), "r5": recall_at_k(recs, rel[u], C.K_P),
                  "ndcg10": ndcg_at_k(recs, rel[u], C.K_NDCG), "novelty5": novelty_at_k(recs, p_item, C.K_COV) if recs else 0.0,
                  "ild5": ild(recs, topics, C.K_COV), "empty": float(len(recs) == 0)}
    return per, lists


def summarize(per, lists, catalog):
    users = sorted(per)
    row = {m: dict(zip(("mean", "lo", "hi"), bootstrap_ci([per[u][m] for u in users], C.BOOTSTRAP_B, C.SEED)))
           for m in ("p5", "r5", "ndcg10", "novelty5", "ild5")}
    row["coverage5"] = {"mean": coverage([lists[u] for u in users], catalog, C.K_COV)}
    row["empty_rate"] = {"mean": float(np.mean([per[u]["empty"] for u in users]))}
    return row


def fmt(r):
    return f"{r['mean']:.3f} [{r['lo']:.3f}; {r['hi']:.3f}]" if "lo" in r else f"{r['mean']:.3f}"
