#!/usr/bin/env python3
"""Паритет: Cypher-оцінки (Neo4j) == Python-оцінки графового підходу. Запуск: python scripts/check_cypher.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
try:
    from dotenv import load_dotenv; load_dotenv(pathlib.Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass
from reco.recommender import Recommender
from reco.cypher import graph_scores

r = Recommender(); bad = 0
for u in sorted(r.ds.users)[:10] + r.ds.split["cold_users"][:2]:
    py, cy = r.models["graph"].score(u), graph_scores(u)
    diff = max(abs(py[d] - cy.get(d, 0.0)) for d in py)
    ok = diff < 1e-6; bad += not ok
    print(f"{'OK ' if ok else 'ERR'} {u}  max|Δ|={diff:.2e}")
sys.exit(1 if bad else 0)
