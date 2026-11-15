"""Той самий графовий підхід на Cypher (Neo4j). Потрібен завантажений граф: scripts/load_graph.py + scripts/load_reco_graph.py.
Оцінки мають збігатися з reco/graph_reco.py (перевірка: python scripts/check_cypher.py)."""
import os
from . import config as C

# компоненти нормуються на максимум (=1) і зважуються alpha/beta/gamma; оцінка документа = сума ваг його тем / к-сть тем
RECO_CYPHER = """
MATCH (u:User {userId: $uid})
CALL {
  WITH u MATCH (u)-[:HAS_ROLE]->(:Role)-[:FOCUSES_ON]->(t:Topic) RETURN t, 'role' AS comp, 1.0 AS raw
  UNION
  WITH u MATCH (u)-[:WORKS_AT]->(:Airline)<-[:OPERATED_BY]-(:Flight)-[:AFFECTED_BY]->(:Risk)-[:RELEVANT_TO]->(t:Topic)
  RETURN t, 'exposure' AS comp, count(*) * 1.0 AS raw
  UNION
  WITH u MATCH (u)-[o:OPENED]->(:Doc)-[:ABOUT]->(t:Topic) RETURN t, 'history' AS comp, sum(o.weight) AS raw
}
WITH comp, collect({t: t, raw: raw}) AS xs, max(raw) AS mx
UNWIND xs AS x
WITH x.t AS t, sum(CASE comp WHEN 'role' THEN $alpha WHEN 'exposure' THEN $beta ELSE $gamma END * x.raw / mx) AS tw
MATCH (d:Doc)-[:ABOUT]->(t)
WITH d, sum(tw) AS s
RETURN d.docId AS doc_id, s / COUNT { (d)-[:ABOUT]->() } AS score
ORDER BY score DESC, doc_id
"""


def graph_scores(uid: str, p: C.GraphParams | None = None) -> dict:
    from neo4j import GraphDatabase
    p = p or C.GraphParams()
    auth = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", ""))
    with GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://localhost:7687"), auth=auth, notifications_min_severity="OFF") as drv:
        rows, _, _ = drv.execute_query(RECO_CYPHER, uid=uid, alpha=p.alpha, beta=p.beta, gamma=p.gamma)
    return {r["doc_id"]: r["score"] for r in rows}
