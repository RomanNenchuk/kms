// P1_shared_hub
MATCH (a:Airline)-[:HUB_AT]->(h:Airport)<-[:HUB_AT]-(b:Airline)
WHERE a.id < b.id
RETURN DISTINCT h.id AS hub, a.id AS a, b.id AS b ORDER BY hub, a, b;

// P1_same_group
MATCH (a:Airline), (b:Airline)
WHERE a.id < b.id AND (
  EXISTS { MATCH (x:Entity)-[:OWNS_STAKE_IN]->(a), (x)-[:OWNS_STAKE_IN]->(b) }
  OR EXISTS { MATCH (a)-[:OWNS_STAKE_IN]->(b) } OR EXISTS { MATCH (b)-[:OWNS_STAKE_IN]->(a) })
RETURN a.id AS a, b.id AS b ORDER BY a, b;

// P2_chains
MATCH (x:Entity)-[r1:OWNS_STAKE_IN]->(m:Airline)-[r2:OWNS_STAKE_IN]->(y:Entity)
WHERE x <> y
RETURN DISTINCT x.id AS x, m.id AS m, y.id AS y
ORDER BY x, m, y;

// P3_profiles
MATCH (a:Airline)-[r]->()
WHERE type(r) IN ['HUB_AT','LOCATED_IN','OPERATES','SERVES','OWNS_STAKE_IN','AGREEMENT_WITH','OPERATED_BY','INVOLVED_IN']
RETURN a.id AS airline, collect(DISTINCT type(r)) AS rels ORDER BY airline;
