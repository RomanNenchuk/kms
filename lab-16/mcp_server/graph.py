"""Граф знань (ЛР 9/11) з CSV: entity linking + підграф. Працює офлайн, без Neo4j.
Права: вузли з міток, до яких немає доступу (Passenger, Pilot), не потрапляють ні в seeds, ні в підграф."""
import csv
import collections
from . import config
from .guards import label_allowed

KEYS = {"Country": "code", "City": "cityId", "Airport": "iata", "Airline": "code", "Aircraft": "registration",
        "Pilot": "pilotId", "Passenger": "passengerId", "Flight": "flightId", "Risk": "riskId", "FlightDelay": "delayId"}
NODEFILES = {"Country": "countries.csv", "City": "cities.csv", "Airport": "airports.csv", "Airline": "airlines.csv",
             "Aircraft": "aircraft.csv", "Pilot": "pilots.csv", "Passenger": "passengers.csv", "Flight": "flights.csv",
             "Risk": "risks.csv", "FlightDelay": "delays.csv"}
RELFILES = [("rel_in_country.csv", "IN_COUNTRY", "City", "Country"), ("rel_located_in.csv", "LOCATED_IN", "Airport", "City"),
            ("rel_owned_by.csv", "OWNED_BY", "Aircraft", "Airline"), ("rel_departs_from.csv", "DEPARTS_FROM", "Flight", "Airport"),
            ("rel_arrives_at.csv", "ARRIVES_AT", "Flight", "Airport"), ("rel_operated_by.csv", "OPERATED_BY", "Flight", "Airline"),
            ("rel_uses_aircraft.csv", "USES_AIRCRAFT", "Flight", "Aircraft"), ("rel_has_pilot.csv", "HAS_PILOT", "Flight", "Pilot"),
            ("rel_has_passenger.csv", "HAS_PASSENGER", "Flight", "Passenger"),
            ("rel_next_leg.csv", "NEXT_LEG", "Flight", "Flight"), ("rel_at_airport.csv", "AT_AIRPORT", "Risk", "Airport"),
            ("rel_affected_by.csv", "AFFECTED_BY", "Flight", "Risk"), ("rel_has_delay.csv", "HAS_DELAY", "Flight", "FlightDelay"),
            ("rel_caused_by.csv", "CAUSED_BY", "FlightDelay", "Risk")]


def node_id(label: str, key: str) -> str:
    return f"graph:{label}:{key}"


class Graph:
    def __init__(self, data_dir=config.GRAPH_DIR):
        self.props: dict[tuple[str, str], dict] = {}
        self.adj = collections.defaultdict(list)
        for label, fn in NODEFILES.items():
            with open(data_dir / fn, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    self.props[(label, row[KEYS[label]])] = row
        for fn, typ, sl, el in RELFILES:
            with open(data_dir / fn, encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    a, b = (sl, r["startId"]), (el, r["endId"])
                    conf = float(r["confidence"])
                    self.adj[a].append((typ, True, b, conf))
                    self.adj[b].append((typ, False, a, conf))

    def link(self, entity: str, level: str, max_seeds: int = 5) -> list[tuple[str, str]]:
        """Entity linking: точний збіг ключа/назви/номера рейсу, інакше підрядок (від 3 символів)."""
        q = entity.strip().lower()
        exact, partial = [], []
        for (label, key), p in self.props.items():
            if not label_allowed(label, level):
                continue
            names = [x.lower() for x in (key, p.get("name", ""), p.get("flightNumber", "")) if x]
            if q in names:
                exact.append((label, key))
            elif len(q) >= 3 and any(q in n for n in names):
                partial.append((label, key))
        return (exact or partial)[:max_seeds]

    def subgraph(self, seeds, hops: int, level: str, max_edges: int = config.MAX_EDGES):
        hops = max(1, min(hops, config.MAX_HOPS))
        nodes, edges, seen_e = {}, [], set()
        dist = {}
        frontier = list(seeds)
        for s in seeds:
            nodes[s] = self.props[s]
            dist[s] = 0
        for depth in range(1, hops + 1):
            nxt = []
            for a in frontier:
                for typ, out, b, conf in self.adj.get(a, []):
                    if not label_allowed(b[0], level):
                        continue
                    src, dst = (a, b) if out else (b, a)
                    ek = (src, typ, dst)
                    if ek in seen_e:
                        continue
                    if len(edges) >= max_edges:
                        return nodes, edges, True, dist
                    seen_e.add(ek)
                    edges.append({"from": node_id(*src), "type": typ, "to": node_id(*dst), "confidence": conf, "hop": depth})
                    if b not in nodes:
                        nodes[b] = self.props[b]
                        dist[b] = depth
                        nxt.append(b)
            frontier = nxt
        return nodes, edges, False, dist


_graph: Graph | None = None


def get_graph() -> Graph:
    global _graph
    if _graph is None:
        _graph = Graph()
    return _graph


def lookup(entity: str, hops: int = 1, level: str | None = None) -> dict:
    level = config.effective_level(level)
    g = get_graph()
    seeds = g.link(entity, level)
    if not seeds:
        return {"ok": True, "found": False, "entity": entity, "nodes": [], "edges": [], "citation_ids": []}
    nodes, edges, truncated, dist = g.subgraph(seeds, hops, level)
    out_nodes = [{"id": node_id(*k), "label": k[0], "distance": dist[k], "props": v} for k, v in nodes.items()]
    seed_ids = [node_id(*sd) for sd in seeds]
    direct = {}                                   # прямі зв'язки стартових вузлів: тип ребра -> id сусідів
    for e in edges:
        if e["hop"] == 1:
            nb = e["to"] if e["from"] in seed_ids else e["from"]
            direct.setdefault(e["type"], []).append(nb)
    return {"ok": True, "found": True, "entity": entity, "seeds": seed_ids,
            "note": "distance/hop = 1 — прямий зв'язок зі знайденою сутністю; 2 — непрямий сусід (не стверджуй про нього прямого зв'язку).",
            "direct_relations": {t: {"count": len(v), "ids": v} for t, v in direct.items()},
            "nodes": out_nodes, "edges": edges, "truncated": truncated,
            "citation_ids": [n["id"] for n in out_nodes]}
