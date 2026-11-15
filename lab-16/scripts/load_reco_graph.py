#!/usr/bin/env python3
"""Додає до графа Neo4j вузли/зв'язки рекомендацій: User, Role, Topic, Doc, ABOUT, FOCUSES_ON, RELEVANT_TO, HAS_ROLE, WORKS_AT, OPENED.
Запускати ПІСЛЯ scripts/load_graph.py (воно очищає базу). Ідемпотентно (MERGE). OPENED містить лише train (ts < cutoff)."""
import os, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
try:
    from dotenv import load_dotenv; load_dotenv(pathlib.Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass
from neo4j import GraphDatabase
from reco import config as C
from reco.data import load, graph_rows
from reco.taxonomy import ROLE_TOPICS, RISK_KIND_TOPICS

ds = load()
auth = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", ""))
risks = {r["riskId"]: r["kind"] for r in graph_rows("risks.csv")}
with GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://localhost:7687"), auth=auth) as drv, drv.session() as s:
    for lab, key in [("User", "userId"), ("Role", "name"), ("Topic", "name"), ("Doc", "docId")]:
        s.run(f"CREATE CONSTRAINT {lab.lower()}_{key} IF NOT EXISTS FOR (n:{lab}) REQUIRE n.{key} IS UNIQUE")
    s.run("UNWIND $rows AS r MERGE (d:Doc {docId: r.doc_id}) SET d.title=r.title, d.sensitivity=r.sensitivity, "
          "d.verified=(r.verified='true' OR r.verified=true), d.lastReviewed=date(r.last_reviewed), d.publishedAt=date(r.published_at)",
          rows=[{**v, "verified": v["verified"]} for v in ds.items.values()])
    s.run("UNWIND $rows AS r MATCH (d:Doc {docId: r.doc_id}) UNWIND r.topics AS t MERGE (x:Topic {name: t}) MERGE (d)-[:ABOUT]->(x)",
          rows=[{"doc_id": k, "topics": v["topics"]} for k, v in ds.items.items()])
    s.run("UNWIND $rows AS r MERGE (u:User {userId: r.user_id}) SET u.role=r.role, u.accessLevel=r.access_level "
          "MERGE (ro:Role {name: r.role}) MERGE (u)-[:HAS_ROLE]->(ro) WITH u, r MATCH (a:Airline {code: r.airline}) MERGE (u)-[:WORKS_AT]->(a)",
          rows=list(ds.users.values()))
    s.run("UNWIND $rows AS r MATCH (ro:Role {name: r.role}) UNWIND r.topics AS t MERGE (x:Topic {name: t}) MERGE (ro)-[:FOCUSES_ON]->(x)",
          rows=[{"role": k, "topics": v} for k, v in ROLE_TOPICS.items()])
    s.run("UNWIND $rows AS r MATCH (k:Risk {riskId: r.risk}) UNWIND r.topics AS t MERGE (x:Topic {name: t}) MERGE (k)-[:RELEVANT_TO]->(x)",
          rows=[{"risk": k, "topics": RISK_KIND_TOPICS[kind]} for k, kind in risks.items()])
    w = {}
    for e in ds.train:
        if C.EVENT_WEIGHT[e["event"]] > 0:
            w[(e["user_id"], e["doc_id"])] = w.get((e["user_id"], e["doc_id"]), 0.0) + C.EVENT_WEIGHT[e["event"]]
    s.run("MATCH (:User)-[o:OPENED]->(:Doc) DELETE o")
    s.run("UNWIND $rows AS r MATCH (u:User {userId: r.u}) MATCH (d:Doc {docId: r.d}) MERGE (u)-[o:OPENED]->(d) SET o.weight=r.w",
          rows=[{"u": u, "d": d, "w": x} for (u, d), x in w.items()])
    n = s.run("MATCH (n:User) RETURN count(n) AS c").single()["c"]
    print(f"Готово: {n} користувачів, {len(ds.items)} документів, {len(w)} зв'язків OPENED")
