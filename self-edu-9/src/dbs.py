"""Тонкі обгортки над трьома сховищами: Neo4j і Memgraph (Bolt + Cypher), GraphDB (HTTP + SPARQL)."""
import csv
import os
import time
from pathlib import Path

import requests
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "sr9password"))
MEMGRAPH_URI = os.getenv("MEMGRAPH_URI", "bolt://localhost:7688")
GRAPHDB_URL = os.getenv("GRAPHDB_URL", "http://localhost:7200")
GRAPHDB_REPO = os.getenv("GRAPHDB_REPO", "avia")

BATCH = 250


def read_csv(name, ints=(), floats=()):
    with (DATA / name).open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k in ints:
            r[k] = int(r[k])
        for k in floats:
            r[k] = float(r[k])
    return rows


def wait_until(fn, what, timeout=240):
    t0, last = time.time(), None
    while time.time() - t0 < timeout:
        try:
            if fn():
                return
        except Exception as e:  # сервіс ще піднімається
            last = e
        time.sleep(2)
    raise RuntimeError(f"{what}: не дочекалися готовності за {timeout}с (остання помилка: {last})")


class BoltBackend:
    """Neo4j та Memgraph: однаковий Cypher і той самий драйвер neo4j (Memgraph говорить Bolt)."""
    kind = "cypher"

    def __init__(self, name, uri, auth, database=None, is_memgraph=False):
        self.name, self.uri, self.is_memgraph = name, uri, is_memgraph
        self.session_kw = {"database": database} if database else {}
        self.driver = GraphDatabase.driver(uri, auth=auth)

    def exec(self, query, **params):
        with self.driver.session(**self.session_kw) as s:
            return [list(r.values()) for r in s.run(query, **params)]

    def wait_ready(self):
        wait_until(lambda: self.exec("RETURN 1") == [[1]], self.name)

    def version(self):
        try:
            if self.is_memgraph:
                return self.exec("SHOW VERSION")[0][0]
            return self.exec("CALL dbms.components() YIELD name, versions RETURN name + ' ' + versions[0]")[0][0]
        except Exception:
            return "?"

    def counts(self):
        n = self.exec("MATCH (n) RETURN count(n)")[0][0]
        e = self.exec("MATCH ()-[r]->() RETURN count(r)")[0][0]
        return {"nodes": n, "edges": e}

    def _indexes(self):
        for label, prop in [("Airport", "code"), ("Airline", "code"), ("Aircraft", "reg"), ("Flight", "id")]:
            if self.is_memgraph:
                try:
                    self.exec(f"CREATE INDEX ON :{label}({prop})")
                except Exception:
                    pass  # індекс уже існує
            else:
                self.exec(f"CREATE INDEX {label.lower()}_{prop} IF NOT EXISTS FOR (n:{label}) ON (n.{prop})")
        if not self.is_memgraph:
            self.exec("CALL db.awaitIndexes(120)")

    def load(self):
        """Повне перезавантаження датасету. Повертає секунди (індекси + вставка)."""
        airports = read_csv("airports.csv", floats=("lat", "lon"))
        airlines = read_csv("airlines.csv")
        aircraft = read_csv("aircraft.csv", ints=("seats",))
        flights = read_csv("flights.csv", ints=("dep", "arr", "duration_min"))
        routes = read_csv("routes.csv", ints=("distance_km",))

        self.exec("MATCH (n) DETACH DELETE n")
        t0 = time.perf_counter()
        self._indexes()
        steps = [
            (airports, "UNWIND $rows AS r CREATE (:Airport {code: r.code, name: r.name, city: r.city, "
                       "country: r.country, lat: r.lat, lon: r.lon})"),
            (airlines, "UNWIND $rows AS r CREATE (:Airline {code: r.code, name: r.name, country: r.country})"),
            (aircraft, "UNWIND $rows AS r CREATE (ac:Aircraft {reg: r.reg, model: r.model, cls: r.cls, seats: r.seats}) "
                       "WITH ac, r MATCH (al:Airline {code: r.airline}) CREATE (al)-[:OWNS]->(ac)"),
            (flights, "UNWIND $rows AS r CREATE (f:Flight {id: r.id, number: r.number, dep: r.dep, arr: r.arr, "
                      "duration_min: r.duration_min}) "
                      "WITH f, r "
                      "MATCH (o:Airport {code: r.origin}), (d:Airport {code: r.dest}), "
                      "(al:Airline {code: r.airline}), (ac:Aircraft {reg: r.aircraft}) "
                      "CREATE (f)-[:DEPARTS_FROM]->(o), (f)-[:ARRIVES_AT]->(d), "
                      "(f)-[:OPERATED_BY]->(al), (f)-[:USES]->(ac)"),
            (routes, "UNWIND $rows AS r MATCH (a:Airport {code: r.origin}), (b:Airport {code: r.dest}) "
                     "CREATE (a)-[:ROUTE {distance_km: r.distance_km}]->(b)"),
        ]
        for rows, cypher in steps:
            for i in range(0, len(rows), BATCH):
                self.exec(cypher, rows=rows[i:i + BATCH])
        return time.perf_counter() - t0

    def run(self, q):
        return self.exec(q["cypher"])

    def close(self):
        self.driver.close()


class GraphDBBackend:
    """GraphDB: RDF4J REST API + SPARQL 1.1."""
    kind = "sparql"
    name = "GraphDB"

    def __init__(self, base=GRAPHDB_URL, repo=GRAPHDB_REPO):
        self.base, self.repo = base.rstrip("/"), repo
        self.http = requests.Session()

    def wait_ready(self):
        wait_until(lambda: self.http.get(f"{self.base}/rest/repositories", timeout=5).ok, self.name)

    def version(self):
        try:
            return self.http.get(f"{self.base}/rest/info/version", timeout=5).json().get("productVersion", "?")
        except Exception:
            return "?"

    def _ensure_repo(self):
        ids = [r["id"] for r in self.http.get(f"{self.base}/rest/repositories", timeout=10).json()]
        if self.repo not in ids:
            cfg = ROOT / "graphdb" / "repo-config.ttl"
            with cfg.open("rb") as fh:
                r = self.http.post(f"{self.base}/rest/repositories", files={"config": (cfg.name, fh, "text/turtle")},
                                   timeout=60)
            r.raise_for_status()
        wait_until(lambda: self.http.get(f"{self.base}/repositories/{self.repo}/size", timeout=5).ok,
                   f"репозиторій {self.repo}")

    def counts(self):
        r = self.http.get(f"{self.base}/repositories/{self.repo}/size", timeout=10)
        return {"triples": int(r.text.strip())}

    def load(self):
        self._ensure_repo()
        self.http.delete(f"{self.base}/repositories/{self.repo}/statements", timeout=60).raise_for_status()
        ttl = (DATA / "avia.ttl").read_bytes()
        t0 = time.perf_counter()
        r = self.http.post(f"{self.base}/repositories/{self.repo}/statements", data=ttl,
                           headers={"Content-Type": "text/turtle"}, timeout=300)
        r.raise_for_status()
        return time.perf_counter() - t0

    @staticmethod
    def _val(b):
        if b["type"] == "literal" and b.get("datatype", "").rsplit("#", 1)[-1] in ("integer", "int", "long"):
            return int(b["value"])
        return b["value"]

    def run(self, q):
        r = self.http.post(f"{self.base}/repositories/{self.repo}", data=q["sparql"].encode("utf-8"),
                           headers={"Content-Type": "application/sparql-query",
                                    "Accept": "application/sparql-results+json"}, timeout=120)
        r.raise_for_status()
        js = r.json()
        cols = js["head"]["vars"]
        return [[self._val(b[c]) for c in cols] for b in js["results"]["bindings"]]

    def close(self):
        self.http.close()


def all_backends():
    return [
        BoltBackend("Neo4j", NEO4J_URI, NEO4J_AUTH, database="neo4j"),
        BoltBackend("Memgraph", MEMGRAPH_URI, ("", ""), is_memgraph=True),
        GraphDBBackend(),
    ]
