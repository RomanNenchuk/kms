"""Необов'язковий інструмент: read-only Cypher у Neo4j. Потрібен docker compose up -d neo4j + scripts/load_graph.py.
Захисти: guards.check_cypher (ключові слова, мітки, LIMIT) + READ-маршрутизація драйвера + тайм-аут.
Увага: Neo4j Community не має ролей (RBAC), тож окремого read-only користувача створити не можна."""
import hashlib
from . import config, guards


def run(query: str, level: str | None = None) -> dict:
    level = config.effective_level(level)
    ok, reason, cypher = guards.check_cypher(query, level)
    if not ok:
        return {"ok": False, "blocked": True, "error": reason}
    if not config.NEO4J_PASSWORD:
        return {"ok": False, "error": "neo4j_not_configured", "detail": "задайте NEO4J_PASSWORD у .env і запустіть docker compose up -d neo4j"}
    try:
        from neo4j import GraphDatabase, RoutingControl
        with GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)) as drv:
            recs, _, _ = drv.execute_query(cypher, routing_=RoutingControl.READ, timeout=config.CYPHER_TIMEOUT_S)
    except Exception as e:
        return {"ok": False, "error": "neo4j_error", "detail": f"{type(e).__name__}: {str(e)[:200]}"}
    rows = [r.data() for r in recs][:config.MAX_ROWS]
    if config.DEFENSES and not guards.rows_allowed(rows, level):
        return {"ok": False, "blocked": True, "error": "result_contains_restricted_properties"}
    sid = "cypher:" + hashlib.sha1(cypher.encode()).hexdigest()[:8]
    return {"ok": True, "id": sid, "cypher": cypher, "rows": rows, "row_count": len(rows), "citation_ids": [sid]}
