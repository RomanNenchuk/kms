"""Завантаження даних ЛР 16: користувачі, документи, взаємодії, часове розбиття."""
from __future__ import annotations
import csv, json
from dataclasses import dataclass
from collections import defaultdict
from . import config as C


def _read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@dataclass
class Dataset:
    users: dict          # user_id -> row
    items: dict          # doc_id -> row (topics -> list)
    events: list         # усі події, відсортовані за ts
    split: dict
    cutoff: str
    end: str

    @property
    def train(self):     # лише події ДО cutoff: усе, що вчиться, бачить тільки це
        return [e for e in self.events if e["ts"] < self.cutoff]

    @property
    def test(self):
        return [e for e in self.events if e["ts"] >= self.cutoff]

    def positives(self, events):
        by = defaultdict(list)
        for e in events:
            if e["event"] in C.POSITIVE_EVENTS:
                by[e["user_id"]].append(e)
        return by


def load() -> Dataset:
    users = {r["user_id"]: r for r in _read(C.INTER_DIR / "users.csv")}
    items = {}
    for r in _read(C.INTER_DIR / "items.csv"):
        r["topics"] = r["topics"].split("|")
        r["verified"] = r["verified"] == "true"
        items[r["doc_id"]] = r
    events = sorted(_read(C.INTER_DIR / "interactions.csv"), key=lambda e: (e["ts"], e["event_id"]))
    split = json.loads((C.INTER_DIR / "split.json").read_text(encoding="utf-8"))
    return Dataset(users, items, events, split, split["cutoff"], split["end"])


def graph_rows(name):
    return _read(C.GRAPH_DIR / name)
