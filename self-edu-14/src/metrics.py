"""Реалізація 8 метрик якості (Q1–Q8). Формули — у config/metrics.yml.
Адаптовано з quality/measure.py ЛР 14 (ті самі правила), але самостійно й без ground truth: метрики його не читають.
Кожна функція повертає (value, n_checked, n_bad, examples, note); value = частка «добрих» елементів."""
from __future__ import annotations
import datetime as dt, re, unicodedata
import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process
from .store import RELS


def share(good, total):
    return good / total if total else 1.0


def fold(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9' ]+", " ", s).replace("'", "")


class UF:
    def __init__(self, n):
        self.p = list(range(n))
    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)
    def redundant(self):
        roots = {}
        for i in range(len(self.p)):
            roots.setdefault(self.find(i), []).append(i)
        return sum(len(v) - 1 for v in roots.values())


class Ctx:
    def __init__(self, tables, corpus, cfg):
        self.t, self.corpus, self.cfg = tables, corpus, cfg
        self.ref = dt.date.fromisoformat(cfg["reference_date"])


def q1(c, d):
    total = bad = 0; miss = []
    for tb in ["flights", "aircraft", "pilots", "passengers", "airports", "delays", "risks"]:
        df = c.t[tb]; empty = (df == "").to_numpy()
        total += empty.size; bad += int(empty.sum())
        miss += [f"{tb}.{df.columns[col]}[{df.iloc[r, 0]}]" for r, col in zip(*np.where(empty))]
    return share(total - bad, total), total, bad, miss, "порожні комірки"


def q2(c, d):
    total = bad = 0; miss = []
    for rel in RELS:
        df = c.t[rel]; ok = (df[["source", "confidence", "validFrom"]] != "").all(axis=1)
        total += len(df); bad += int((~ok).sum())
        miss += [f"{rel}:{a}->{b}" for a, b in zip(df.startId[~ok], df.endId[~ok])]
    return share(total - bad, total), total, bad, miss, "зв'язки без source/confidence/validFrom"


FUNCTIONAL = ["rel_operated_by", "rel_uses_aircraft", "rel_departs_from", "rel_arrives_at", "rel_owned_by", "rel_located_in", "rel_in_country"]


def q3(c, d):
    total = bad = 0; exs = []
    for rel in FUNCTIONAL:
        g = c.t[rel].groupby("startId").endId.nunique(); multi = g[g > 1]
        total += len(g); bad += len(multi); exs += [f"{rel}:{k} ({v} значень)" for k, v in multi.items()]
    return share(total - bad, total), total, bad, exs, "вузли з кількома різними значеннями функціонального зв'язку"


def q4(c, d):
    cut = c.ref - dt.timedelta(days=d["max_age_days"])
    old = [r for r in c.corpus if dt.date.fromisoformat(r["date"]) < cut]
    docs = sorted({r["doc_id"] for r in old})
    return share(len(c.corpus) - len(old), len(c.corpus)), len(c.corpus), len(old), docs, f"застарілі фрагменти (старші за {d['max_age_days']} днів), документів: {len(docs)}"


def person_pairs(names, thr=90):
    keys = list(names); norm = [" ".join(sorted(fold(names[k]).split())) for k in keys]
    sim = process.cdist(norm, norm, scorer=fuzz.token_sort_ratio, dtype=np.uint8)
    toks = [fold(names[k]).split() for k in keys]; pairs = set()
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            ok = sim[i, j] >= thr
            if not ok:                                   # ініціал + те саме прізвище
                a, b = toks[i], toks[j]
                short = [x for x in a if len(x) == 1] and a or ([x for x in b if len(x) == 1] and b) or None
                if short is not None:
                    other = b if short is a else a
                    ini = [x for x in short if len(x) == 1][0]; rest = [x for x in short if len(x) > 1]
                    ok = bool(rest) and rest[0] in other and any(x.startswith(ini) and len(x) > 1 for x in other)
            if ok:
                pairs.add(frozenset((keys[i], keys[j])))
    return pairs


def airport_pairs(names, thr=90):
    stop = {"international", "airport"}; keys = list(names)
    norm = [" ".join(sorted(w for w in fold(names[k]).split() if w not in stop)) for k in keys]
    sim = process.cdist(norm, norm, scorer=fuzz.token_sort_ratio, dtype=np.uint8)
    return {frozenset((keys[i], keys[j])) for i in range(len(keys)) for j in range(i + 1, len(keys)) if sim[i, j] >= thr}


def aircraft_pairs(regs):
    key = {}
    for r in regs:
        key.setdefault(re.sub(r"[^A-Z0-9]", "", r.upper()), []).append(r)
    return {frozenset((a, b)) for v in key.values() for i, a in enumerate(v) for b in v[i + 1:]}


def q5(c, d):
    t = c.t
    pairs = {"passenger": person_pairs(dict(zip(t["passengers"].passengerId, t["passengers"].name))),
             "pilot": person_pairs(dict(zip(t["pilots"].pilotId, t["pilots"].name))),
             "airport": airport_pairs(dict(zip(t["airports"].iata, t["airports"].name))),
             "aircraft": aircraft_pairs(list(t["aircraft"].registration))}
    n = sum(len(t[x]) for x in ("passengers", "pilots", "airports", "aircraft"))
    ids = sorted({x for ps in pairs.values() for p in ps for x in p}); idx = {x: i for i, x in enumerate(ids)}
    uf = UF(len(ids))
    for ps in pairs.values():
        for p in ps:
            a, b = tuple(p); uf.union(idx[a], idx[b])
    red = uf.redundant()
    exs = [f"{a} ~ {b}" for ps in pairs.values() for a, b in (sorted(p) for p in ps)]
    return share(n - red, n), n, red, sorted(exs), f"кандидатних пар за типами: { {k: len(v) for k, v in pairs.items()} }"


def q6(c, d):
    tx = [r["text"] for r in c.corpus]
    sim = process.cdist(tx, tx, scorer=fuzz.token_set_ratio, dtype=np.uint8, workers=-1)
    np.fill_diagonal(sim, 0)
    i, j = np.where(np.triu(sim) >= 90)
    docs = [r["doc_id"] for r in c.corpus]
    pairs = [(a, b) for a, b in zip(i, j) if docs[a] != docs[b]]
    uf = UF(len(c.corpus))
    for a, b in pairs:
        uf.union(a, b)
    red = uf.redundant()
    dp = sorted({tuple(sorted((docs[a], docs[b]))) for a, b in pairs})
    return share(len(c.corpus) - red, len(c.corpus)), len(c.corpus), red, [f"{a} ~ {b}" for a, b in dp], f"кандидатних пар фрагментів: {len(pairs)}, пар документів: {len(dp)}"


def q7(c, d):
    def rng(tb, col, lo, hi):
        s = c.t[tb][col]; s = s[s != ""]; v = pd.to_numeric(s, errors="coerce")
        bad = s[(v.isna()) | (v < lo) | (v > hi)]
        return len(s), [f"{tb}.{col}[{c.t[tb].iloc[i, 0]}]={x}" for i, x in bad.items()]
    def seats():
        df = c.t["aircraft"]; df = df[df.seatCapacity != ""]; v = pd.to_numeric(df.seatCapacity, errors="coerce")
        cargo = df.model.str.contains(r"\d[A-Z]*F$|freighter", case=False, regex=True)     # вантажні (…F): 0 місць допустимо
        ok = (v >= 1) & (v <= 900) | (cargo & (v == 0))
        return len(df), [f"aircraft.seatCapacity[{r}]={x}" for r, x in zip(df.registration[~ok], df.seatCapacity[~ok])]
    def iso(tb, col):
        s = c.t[tb][col]; s = s[s != ""]
        bad = s[~s.str.match(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?$")]
        return len(s), [f"{tb}.{col}[{c.t[tb].iloc[i, 0]}]={x}" for i, x in bad.items()]
    parts = [rng("pilots", "flightHours", 0, 40000), rng("delays", "minutes", 0, 720), rng("risks", "level", 1, 5), seats(),
             iso("flights", "date"), iso("flights", "scheduledDeparture")] + [iso(rel, "validFrom") for rel in RELS]
    total = sum(p[0] for p in parts); bad = [x for p in parts for x in p[1]]
    return share(total - len(bad), total), total, len(bad), bad, "значення поза межами або форматом"


def q8(c, d):
    ok_s = {"public", "internal", "restricted"}
    bad = [r["chunk_id"] for r in c.corpus if r["sensitivity"] not in ok_s or not re.match(r"^https?://", r["source_url"]) or not r["text"].strip()]
    return share(len(c.corpus) - len(bad), len(c.corpus)), len(c.corpus), len(bad), bad, "фрагменти без коректних sensitivity/source_url/тексту"


FUNCS = {"Q1": q1, "Q2": q2, "Q3": q3, "Q4": q4, "Q5": q5, "Q6": q6, "Q7": q7, "Q8": q8}
