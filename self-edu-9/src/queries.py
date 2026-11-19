"""П'ять тестових запитів СР9 у двох діалектах: Cypher (Neo4j, Memgraph) і SPARQL (GraphDB).

Параметри сценарію зберігаються в одному місці (P), щоб Cypher, SPARQL і Python-оракул
(gen_data.py) рахували рівно те саме.
"""
from string import Template

P = {
    "ORIGIN": "KBP",       # Q1: аеропорт вильоту
    "TRIP_FROM": "WAW",    # Q3: звідки летимо з пересадкою
    "TRIP_TO": "CPH",      # Q3: куди
    "REACH_START": "ODS",  # Q4: звідки рахуємо досяжність
    "REACH_HOPS": 3,       # Q4: максимальна кількість перельотів
    "MIN_LAYOVER": 60,     # Q3: мін. пересадка, хв
    "MAX_LAYOVER": 720,    # Q3: макс. пересадка, хв
}
# SPARQL 1.1 не має {1,3}, тому розгортаємо шлях: route | route/route | route/route/route
P["SPARQL_PATH"] = "|".join("/".join(["ex:route"] * k) for k in range(1, P["REACH_HOPS"] + 1))

SPARQL_PREFIX = "PREFIX ex: <http://example.org/avia#>\n"


def _t(s: str) -> str:
    return Template(s).substitute(P).strip()


QUERIES = [
    {
        "id": "Q1",
        "title": "Рейси з аеропорту (lookup + 1 hop + сортування)",
        "cypher": _t("""
MATCH (f:Flight)-[:DEPARTS_FROM]->(:Airport {code: '$ORIGIN'})
RETURN f.id AS id, f.number AS number, f.dep AS dep
ORDER BY dep, id
"""),
        "sparql": SPARQL_PREFIX + _t("""
SELECT ?id ?number ?dep WHERE {
  ?a a ex:Airport ; ex:code "$ORIGIN" .
  ?f a ex:Flight ; ex:departsFrom ?a ; ex:id ?id ; ex:number ?number ; ex:dep ?dep .
}
ORDER BY ?dep ?id
"""),
    },
    {
        "id": "Q2",
        "title": "Кількість рейсів на авіакомпанію (join + агрегація)",
        "cypher": _t("""
MATCH (f:Flight)-[:OPERATED_BY]->(al:Airline)
RETURN al.code AS airline, count(f) AS flights
ORDER BY flights DESC, airline
"""),
        "sparql": SPARQL_PREFIX + _t("""
SELECT ?airline (COUNT(?f) AS ?flights) WHERE {
  ?f a ex:Flight ; ex:operatedBy ?al .
  ?al ex:code ?airline .
}
GROUP BY ?airline
ORDER BY DESC(?flights) ?airline
"""),
    },
    {
        "id": "Q3",
        "title": "Маршрути з однією пересадкою (multi-hop pattern + часові умови)",
        "cypher": _t("""
MATCH (:Airport {code: '$TRIP_FROM'})<-[:DEPARTS_FROM]-(f1:Flight)-[:ARRIVES_AT]->(m:Airport)
      <-[:DEPARTS_FROM]-(f2:Flight)-[:ARRIVES_AT]->(:Airport {code: '$TRIP_TO'})
WHERE f2.dep >= f1.arr + $MIN_LAYOVER AND f2.dep <= f1.arr + $MAX_LAYOVER
RETURN m.code AS transit, count(*) AS itineraries
ORDER BY itineraries DESC, transit
"""),
        "sparql": SPARQL_PREFIX + _t("""
SELECT ?transit (COUNT(*) AS ?itineraries) WHERE {
  ?o a ex:Airport ; ex:code "$TRIP_FROM" .
  ?d a ex:Airport ; ex:code "$TRIP_TO" .
  ?f1 ex:departsFrom ?o ; ex:arrivesAt ?m ; ex:arr ?arr1 .
  ?f2 ex:departsFrom ?m ; ex:arrivesAt ?d ; ex:dep ?dep2 .
  ?m ex:code ?transit .
  FILTER(?dep2 >= ?arr1 + $MIN_LAYOVER && ?dep2 <= ?arr1 + $MAX_LAYOVER)
}
GROUP BY ?transit
ORDER BY DESC(?itineraries) ?transit
"""),
    },
    {
        "id": "Q4",
        "title": "Досяжні аеропорти за ≤ 3 перельоти (variable-length traversal)",
        "cypher": _t("""
MATCH (:Airport {code: '$REACH_START'})-[:ROUTE*1..$REACH_HOPS]->(b:Airport)
RETURN count(DISTINCT b) AS reachable
"""),
        "sparql": SPARQL_PREFIX + _t("""
SELECT (COUNT(DISTINCT ?b) AS ?reachable) WHERE {
  ?a a ex:Airport ; ex:code "$REACH_START" .
  ?a ($SPARQL_PATH) ?b .
}
"""),
    },
    {
        "id": "Q5",
        "title": "Топ-5 найзавантаженіших аеропортів (глобальна агрегація + top-k)",
        "cypher": _t("""
MATCH (:Flight)-[r:DEPARTS_FROM|ARRIVES_AT]->(a:Airport)
RETURN a.code AS airport, count(r) AS movements
ORDER BY movements DESC, airport
LIMIT 5
"""),
        "sparql": SPARQL_PREFIX + _t("""
SELECT ?airport (COUNT(?f) AS ?movements) WHERE {
  { ?f ex:departsFrom ?a } UNION { ?f ex:arrivesAt ?a }
  ?a ex:code ?airport .
}
GROUP BY ?airport
ORDER BY DESC(?movements) ?airport
LIMIT 5
"""),
    },
]
