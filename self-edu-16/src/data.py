"""Дані та часове розбиття. Усе, що вчиться, бачить лише train (ts < cutoff)."""
from __future__ import annotations
import csv, json
from dataclasses import dataclass
from collections import defaultdict
from . import config as C


def _read(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@dataclass
class Dataset:
    users: dict
    items: dict
    events: list
    split: dict

    @property
    def cutoff(self): return self.split["cutoff"]
    @property
    def end(self): return self.split["end"]
    @property
    def train(self): return [e for e in self.events if e["ts"] < self.cutoff]
    @property
    def test(self): return [e for e in self.events if e["ts"] >= self.cutoff]

    def positives(self, events):
        out = defaultdict(set)
        for e in events:
            if e["event"] in C.POSITIVE:
                out[e["user_id"]].add(e["doc_id"])
        return out

    def candidates(self, user_id, as_of, seen=frozenset(), respect_access=True):
        """Документи, які можна показати: опубліковані до as_of, доступні за рівнем, ще не бачені."""
        u, out = self.users[user_id], []
        for d, it in sorted(self.items.items()):
            if it["published_at"] > as_of or d in seen:
                continue
            if respect_access and C.ACCESS_RANK[it["sensitivity"]] > C.ACCESS_RANK[u["access_level"]]:
                continue
            out.append(d)
        return out


def load() -> Dataset:
    users = {r["user_id"]: r for r in _read(C.INTER / "users.csv")}
    items = {}
    for r in _read(C.INTER / "items.csv"):
        r["topics"] = r["topics"].split("|")
        items[r["doc_id"]] = r
    events = sorted(_read(C.INTER / "interactions.csv"), key=lambda e: (e["ts"], e["event_id"]))
    split = json.loads((C.INTER / "split.json").read_text(encoding="utf-8"))
    return Dataset(users, items, events, split)


def graph_rows(name):
    return _read(C.GRAPH / name)
