#!/usr/bin/env python3
"""Демо Результату 1, C2: фільтри якості й прав працюють. Запуск: python scripts/demo_filters.py | tee reports/filters_demo.txt"""
import sys, pathlib
from collections import Counter
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from reco.recommender import Recommender

r = Recommender(); ds = r.ds; end = ds.end[:10]
print(f"as_of={end}; відомі «погані» документи: unverified={ds.split['unverified_items']} stale={ds.split['stale_items']} (нові після cutoff: {ds.split['new_items']})\n")
for access in ("public", "internal", "restricted"):
    u = next(x for x, row in sorted(ds.users.items()) if row["access_level"] == access and row["cohort"] == "warm")
    on, off = r.recommend(u, 36, "hybrid", as_of=end, use_filters=True, explain=False), r.recommend(u, 36, "hybrid", as_of=end, use_filters=False, explain=False)
    print(f"{u} ({access}): без фільтрів {len(off['items'])} док., з фільтрами {len(on['items'])}; відсіяно за причинами: {dict(Counter(on['dropped'].values()))}")
    shown = {d: why for d, why in on["dropped"].items() if why != "seen"}
    for d, why in sorted(shown.items()):
        print(f"    - {d}: {why} (sensitivity={ds.items[d]['sensitivity']}, verified={ds.items[d]['verified']}, last_reviewed={ds.items[d]['last_reviewed']})")
    assert not set(on["dropped"]) & {i["doc_id"] for i in on["items"]}, "відфільтрований документ потрапив у видачу"
    assert all(ds.items[i["doc_id"]]["verified"] for i in on["items"])
print("\nOK: жоден відфільтрований документ не потрапив у видачу")
