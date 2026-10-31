// Крок 4. Кількості (запустити до і ПІСЛЯ повторного імпорту — мають збігатися).
MATCH (n) RETURN count(n) AS nodes;
MATCH ()-[r]->() RETURN count(r) AS relationships;
MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS cnt ORDER BY cnt DESC;
MATCH ()-[r]->() RETURN type(r) AS relType, count(*) AS cnt ORDER BY cnt DESC;
