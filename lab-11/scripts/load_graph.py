#!/usr/bin/env python3
"""Завантаження графа ЛР 9 у Neo4j з data/*.csv (генерує scripts/generate_data.py, seed=42).

Схема виведена з назв CSV (14 базових типів зв'язків). Похідні DIRECT_ROUTE та ROUTE_LINK
тут НЕ створюються. Якщо в ЛР 9 є import/*.cypher — краще використати його.
Запуск: docker compose exec app python scripts/load_graph.py [--wipe]
"""
import csv, os, sys, pathlib
from neo4j import GraphDatabase

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", ""))

I, F, B, S = int, float, lambda v: v.lower() == "true", str
# файл, мітки, ключ, [(колонка, тип)]
NODES = [
    ("countries.csv", ["Country"], "code", [("name", S)]),
    ("cities.csv", ["City"], "cityId", [("name", S)]),
    ("airports.csv", ["Airport"], "iata", [("name", S)]),
    ("airlines.csv", ["Airline"], "code", [("name", S), ("homeCountry", S)]),
    ("aircraft.csv", ["Aircraft"], "registration", [("model", S), ("seatCapacity", I)]),
    ("pilots.csv", ["Pilot", "Person"], "pilotId", [("name", S), ("flightHours", I)]),
    ("passengers.csv", ["Passenger", "Person"], "passengerId", [("name", S)]),
    ("flights.csv", ["Flight"], "flightId", [("flightNumber", S), ("scheduledDeparture", S), ("date", S), ("kind", S)]),
    ("risks.csv", ["Risk"], "riskId", [("name", S), ("kind", S), ("level", I)]),
    ("delays.csv", ["FlightDelay"], "delayId", [("minutes", I), ("propagated", B)]),
]
# файл, тип, (мітка start, ключ), (мітка end, ключ), додаткові властивості
RELS = [
    ("rel_in_country.csv", "IN_COUNTRY", ("City", "cityId"), ("Country", "code"), []),
    ("rel_located_in.csv", "LOCATED_IN", ("Airport", "iata"), ("City", "cityId"), []),
    ("rel_owned_by.csv", "OWNED_BY", ("Aircraft", "registration"), ("Airline", "code"), []),
    ("rel_departs_from.csv", "DEPARTS_FROM", ("Flight", "flightId"), ("Airport", "iata"), []),
    ("rel_arrives_at.csv", "ARRIVES_AT", ("Flight", "flightId"), ("Airport", "iata"), []),
    ("rel_operated_by.csv", "OPERATED_BY", ("Flight", "flightId"), ("Airline", "code"), []),
    ("rel_uses_aircraft.csv", "USES_AIRCRAFT", ("Flight", "flightId"), ("Aircraft", "registration"), []),
    ("rel_has_pilot.csv", "HAS_PILOT", ("Flight", "flightId"), ("Pilot", "pilotId"), []),
    ("rel_next_leg.csv", "NEXT_LEG", ("Flight", "flightId"), ("Flight", "flightId"), [("gapMin", I)]),
    ("rel_has_passenger.csv", "HAS_PASSENGER", ("Flight", "flightId"), ("Passenger", "passengerId"), []),
    ("rel_at_airport.csv", "AT_AIRPORT", ("Risk", "riskId"), ("Airport", "iata"), []),
    ("rel_affected_by.csv", "AFFECTED_BY", ("Flight", "flightId"), ("Risk", "riskId"), []),
    ("rel_has_delay.csv", "HAS_DELAY", ("Flight", "flightId"), ("FlightDelay", "delayId"), []),
    ("rel_caused_by.csv", "CAUSED_BY", ("FlightDelay", "delayId"), ("Risk", "riskId"), []),
]


def read(name, casts):
    with open(DATA / name, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            yield row, {c: t(row[c]) for c, t in casts}


def main(wipe):
    with GraphDatabase.driver(URI, auth=AUTH) as drv, drv.session() as s:
        if wipe:
            s.run("MATCH (n) DETACH DELETE n")
        for _, labels, key, _p in NODES:
            s.run(f"CREATE CONSTRAINT {labels[0].lower()}_{key} IF NOT EXISTS "
                  f"FOR (n:{labels[0]}) REQUIRE n.{key} IS UNIQUE")
        for fn, labels, key, props in NODES:
            rows = [{"k": r[key], "p": p} for r, p in read(fn, props)]
            s.run(f"UNWIND $rows AS r MERGE (n:{labels[0]} {{{key}: r.k}}) SET n += r.p, n:{':'.join(labels)}", rows=rows)
            if fn == "flights.csv":
                s.run("MATCH (f:Flight) WHERE f.kind='passenger' SET f:PassengerFlight")
                s.run("MATCH (f:Flight) WHERE f.kind='cargo' SET f:CargoFlight")
                s.run("MATCH (f:Flight) SET f.scheduledDeparture = datetime(f.scheduledDeparture), f.date = date(f.date)")
            if fn == "risks.csv":
                s.run("MATCH (r:Risk) WHERE r.kind='weather' SET r:WeatherRisk")
                s.run("MATCH (r:Risk) WHERE r.kind='technical' SET r:TechnicalRisk")
        for fn, typ, (sl, sk), (el, ek), extra in RELS:
            rows = []
            for r, p in read(fn, extra):
                rows.append({"a": r["startId"], "b": r["endId"], "source": r["source"],
                             "confidence": float(r["confidence"]), "validFrom": r["validFrom"], "p": p})
            s.run(f"UNWIND $rows AS r MATCH (a:{sl} {{{sk}: r.a}}) MATCH (b:{el} {{{ek}: r.b}}) "
                  f"MERGE (a)-[x:{typ}]->(b) SET x.source=r.source, x.confidence=r.confidence, "
                  f"x.validFrom=date(r.validFrom), x += r.p", rows=rows)
        n = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        m = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        print(f"Готово: {n} вузлів, {m} зв'язків (очікується 673 і 2592 без похідних)")


if __name__ == "__main__":
    main("--wipe" in sys.argv)
