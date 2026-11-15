#!/usr/bin/env python3
"""Генератор СИНТЕТИЧНИХ взаємодій користувачів з документами Hub (ЛР 16, seed=42).
Запуск: python scripts/gen_interactions.py
Вихід: data/interactions/{users,items,interactions}.csv, split.json, README.md
Модель: вподобання користувача = роль + «експозиція» його авіакомпанії до ризиків із графа ЛР 9 + індивідуальний шум;
вибір документа ~ відповідність темам × популярність (Zipf) + 10 % випадкових кліків. Дані НЕ реальні."""
import csv, json, sys, pathlib, datetime as dt
from collections import Counter, defaultdict
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from reco.taxonomy import TOPICS, DOC_TOPICS, ROLES, ROLE_TOPICS, RISK_KIND_TOPICS  # noqa: E402

SEED = 42
rng = np.random.default_rng(SEED)
OUT = ROOT / "data" / "interactions"
OUT.mkdir(parents=True, exist_ok=True)
START, CUTOFF, END = dt.date(2026, 9, 1), dt.date(2026, 10, 26), dt.date(2026, 11, 14)  # train < CUTOFF <= test
N_WARM, N_COLD = 56, 8
NEW_DOCS = ["en_airport_slot", "en_air_traffic_flow_management", "en_montreal_convention", "en_overselling"]  # з'являються лише після CUTOFF
STALE_DOCS = ["en_warsaw_convention", "en_icao_airport_code", "en_global_distribution_system"]            # застарілі (last_reviewed > 540 днів)
UNVERIFIED = ["en_airline_alliance", "en_codeshare_agreement", "en_air_cargo"]                            # verified=false

def read(p): return list(csv.DictReader(open(ROOT / "data" / "graph" / p, encoding="utf-8")))
airlines = [r["code"] for r in read("airlines.csv")]
airports = [r["iata"] for r in read("airports.csv")]
risk_kind = {r["riskId"]: r["kind"] for r in read("risks.csv")}
flight_airline = {r["startId"]: r["endId"] for r in read("rel_operated_by.csv")}
expo = {a: np.zeros(len(TOPICS)) for a in airlines}   # експозиція авіакомпанії до тем через ризики її рейсів
for r in read("rel_affected_by.csv"):
    a = flight_airline[r["startId"]]
    for t in RISK_KIND_TOPICS[risk_kind[r["endId"]]]:
        expo[a][TOPICS.index(t)] += 1
for a in expo:
    if expo[a].sum(): expo[a] /= expo[a].max()

# ---- items ----
overrides = {k: v for k, v in json.load(open(ROOT / "data/kb/sensitivity_overrides.json")).items() if not k.startswith("_")}
chunks = Counter(); titles = {}; types = {}
for l in open(ROOT / "data/kb/corpus.jsonl", encoding="utf-8"):
    r = json.loads(l); chunks[r["doc_id"]] += 1; titles[r["doc_id"]] = r["title"]; types[r["doc_id"]] = r["type"]
docs = sorted(chunks)
assert set(docs) == set(DOC_TOPICS), set(docs) ^ set(DOC_TOPICS)
items = []
for d in docs:
    if d in NEW_DOCS: pub = CUTOFF + dt.timedelta(days=int(rng.integers(0, 8)))
    else: pub = START - dt.timedelta(days=int(rng.integers(30, 400)))
    rev = dt.date(2024, 11, 1) + dt.timedelta(days=int(rng.integers(0, 60))) if d in STALE_DOCS else \
          max(pub, dt.date(2026, 3, 1)) + dt.timedelta(days=int(rng.integers(0, 60)))
    items.append(dict(doc_id=d, title=titles[d], type=types[d], topics="|".join(DOC_TOPICS[d]),
                      sensitivity=overrides.get(d, "public"), verified=str(d not in UNVERIFIED).lower(),
                      published_at=pub.isoformat(), last_reviewed=min(rev, END).isoformat(), n_chunks=chunks[d]))
pop = rng.permutation(np.arange(1, len(docs) + 1)) ** -0.8  # Zipf-подібна популярність
pop = dict(zip(docs, pop / pop.sum()))

# ---- users ----
users = []
for i in range(N_WARM + N_COLD):
    cold = i >= N_WARM
    role = ROLES[i % len(ROLES)]
    users.append(dict(user_id=f"U{i+1:03d}", role=role, airline=str(rng.choice(airlines)), home_airport=str(rng.choice(airports)),
                      access_level=str(rng.choice(["public", "internal", "restricted"], p=[.4, .4, .2])),
                      joined_at=(CUTOFF + dt.timedelta(days=int(rng.integers(0, 14)))).isoformat() if cold else
                                (START + dt.timedelta(days=int(rng.integers(0, 14)))).isoformat(), cohort="cold" if cold else "warm"))

# ---- interactions ----
rows = []
for u in users:
    pref = np.zeros(len(TOPICS))
    for t in ROLE_TOPICS[u["role"]]: pref[TOPICS.index(t)] += 1.0
    pref += 1.2 * expo[u["airline"]] + rng.gamma(1.0, 0.25, len(TOPICS))
    t0 = dt.date.fromisoformat(u["joined_at"])
    n = int(rng.integers(3, 9)) if u["cohort"] == "cold" else int(rng.integers(30, 90))
    for _ in range(n):
        day = t0 + dt.timedelta(days=int(rng.integers(0, max(1, (END - t0).days + 1))))
        while day.weekday() >= 5: day += dt.timedelta(days=1)
        day = min(day, END)
        avail = [it for it in items if dt.date.fromisoformat(it["published_at"]) <= day]
        w = np.array([np.mean([pref[TOPICS.index(t)] for t in it["topics"].split("|")]) ** 2 * pop[it["doc_id"]] for it in avail])
        random_click = rng.random() < 0.10
        it = avail[int(rng.integers(len(avail)))] if random_click else avail[int(rng.choice(len(avail), p=w / w.sum()))]
        match = np.mean([pref[TOPICS.index(t)] for t in it["topics"].split("|")]) / pref.max()
        p_pos = 0.15 + 0.6 * match if not random_click else 0.1
        ev = "view"
        if rng.random() < p_pos: ev = str(rng.choice(["open", "save", "helpful"], p=[.55, .25, .2]))
        ts = dt.datetime.combine(day, dt.time(int(rng.integers(8, 19)), int(rng.integers(0, 60)), int(rng.integers(0, 60))))
        rows.append(dict(user_id=u["user_id"], doc_id=it["doc_id"], event=ev, ts=ts.isoformat()))
rows.sort(key=lambda r: (r["ts"], r["user_id"]))
for i, r in enumerate(rows): r["event_id"] = f"E{i+1:05d}"

def dump(name, data, cols):
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(data)
dump("users.csv", users, ["user_id", "role", "airline", "home_airport", "access_level", "joined_at", "cohort"])
dump("items.csv", items, ["doc_id", "title", "type", "topics", "sensitivity", "verified", "published_at", "last_reviewed", "n_chunks"])
dump("interactions.csv", rows, ["event_id", "user_id", "doc_id", "event", "ts"])

cut = CUTOFF.isoformat()
train = [r for r in rows if r["ts"] < cut]; test = [r for r in rows if r["ts"] >= cut]
train_users = {r["user_id"] for r in train}
pos = lambda rs: [r for r in rs if r["event"] != "view"]
test_users = {r["user_id"] for r in pos(test)}
split = dict(seed=SEED, start=START.isoformat(), cutoff=cut, end=END.isoformat(), rule="train: ts < cutoff; test: ts >= cutoff; relevant = event in {open,save,helpful}",
             n_users=len(users), n_items=len(items), n_events=len(rows), n_train=len(train), n_test=len(test),
             warm_eval_users=sorted(u for u in test_users if u in train_users), cold_users=sorted(test_users - train_users),
             new_items=NEW_DOCS, stale_items=STALE_DOCS, unverified_items=UNVERIFIED)
json.dump(split, open(OUT / "split.json", "w"), ensure_ascii=False, indent=2)
(OUT / "README.md").write_text(f"""# Синтетичні взаємодії (ЛР 16)
Згенеровано `scripts/gen_interactions.py`, seed={SEED}. **Дані синтетичні, персональних даних немає.**
- Період {START}..{END}; часове розбиття: train < {cut} ≤ test. Події `view` — негативні/нейтральні; релевантні: `open`, `save`, `helpful`.
- Користувачі: {N_WARM} «теплих» (є історія в train) і {N_COLD} «холодних» (приєдналися після cutoff). Документи: {len(items)}, з них {len(NEW_DOCS)} нових (з'являються після cutoff).
- Модель вподобань: роль + експозиція авіакомпанії до ризиків графа (rel_affected_by × rel_operated_by) + шум; 10 % випадкових кліків; популярність Zipf.
- Метадані `verified`, `last_reviewed`, `published_at`, рівні доступу користувачів — синтетичні (для демонстрації фільтрів). `sensitivity` документів — з `data/kb/sensitivity_overrides.json`.
- Зв'язок документ—тема і роль—тема — вручну в `reco/taxonomy.py` (V1).
""", encoding="utf-8")
print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in split.items()}, ensure_ascii=False))
print("event mix:", Counter(r["event"] for r in rows)); print("train/test positives:", len(pos(train)), len(pos(test)))
