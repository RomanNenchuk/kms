// ЛР 9 / Результат 4. GDS: PageRank + Louvain. Потрібен плагін Graph Data Science (див. README).
// Передумова: імпорт виконано, є DIRECT_ROUTE і ROUTE_LINK (кінець 03_import_rels.cypher).

// 0) Версія GDS (скріншот для звіту)
RETURN gds.version() AS gdsVersion;

// 1) Проєкції в памяті (з очищенням, якщо вже існують)
CALL gds.graph.drop('airRoutes', false) YIELD graphName RETURN graphName;
CALL gds.graph.drop('airLinks', false) YIELD graphName RETURN graphName;

CALL gds.graph.project('airRoutes', 'Airport',
  {DIRECT_ROUTE: {orientation: 'NATURAL', properties: 'flights'}})
YIELD graphName, nodeCount, relationshipCount;

CALL gds.graph.project('airLinks', 'Airport',
  {ROUTE_LINK: {orientation: 'UNDIRECTED', properties: 'flights'}})
YIELD graphName, nodeCount, relationshipCount;

// 2) PageRank (напрямлений, вага = кількість рейсів) -> властивість pagerank
CALL gds.pageRank.write('airRoutes',
  {writeProperty: 'pagerank', relationshipWeightProperty: 'flights', maxIterations: 50})
YIELD nodePropertiesWritten, ranIterations, didConverge;

// 3) Louvain (неорієнтований, вага = рейси) -> властивість community
CALL gds.louvain.write('airLinks',
  {writeProperty: 'community', relationshipWeightProperty: 'flights'})
YIELD communityCount, modularity, nodePropertiesWritten;

// 4) Топ-10 за PageRank
MATCH (a:Airport)
RETURN a.iata AS airport, a.name AS name, round(a.pagerank, 4) AS pagerank
ORDER BY a.pagerank DESC
LIMIT 10;

// 5) Спільноти: розмір і склад
MATCH (a:Airport)
RETURN a.community AS community, count(*) AS size, collect(a.iata) AS airports
ORDER BY size DESC;

// 6) Перевірка збереження у графі (Результат 4, C4)
MATCH (a:Airport) WHERE a.pagerank IS NOT NULL AND a.community IS NOT NULL
RETURN count(a) AS airportsWithResults;

// 7) Прибирання проєкцій з пам'яті (необов'язково)
// CALL gds.graph.drop('airRoutes') YIELD graphName RETURN graphName;
// CALL gds.graph.drop('airLinks') YIELD graphName RETURN graphName;
