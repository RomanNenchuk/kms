#!/usr/bin/env bash
# Виконує імпорт 01..04 через cypher-shell у контейнері lab9-neo4j. Потрібен NEO4J_PASSWORD.
set -euo pipefail
: "${NEO4J_PASSWORD:?export NEO4J_PASSWORD=...}"
cd "$(dirname "$0")/.."
for f in 01_constraints_indexes 02_import_nodes 03_import_rels 04_counts; do
  echo "=== $f ==="
  docker exec -i lab9-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" --format plain < "import/$f.cypher"
done
