#!/usr/bin/env python3
"""CSV -> RDF (Turtle) у словнику av: з ЛР 8. Потрібно для Результату 5 (порівняння SPARQL vs Cypher на ТИХ САМИХ даних).
Вихід: data/data9.ttl. Завантажити разом із vocabulary.ttl з ЛР 8 (див. README). Походження (source/confidence)
у RDF свідомо не переноситься: потрібні reification або іменовані графи — це пункт порівняння."""
import csv, os, re
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
rd = lambda n: list(csv.DictReader(open(os.path.join(D, n), encoding="utf-8")))
loc = lambda s: re.sub(r"[^A-Za-z0-9_\-]", "_", s)
Q = lambda s: '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
out = ["@prefix av: <http://example.org/aviation#> .", "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
       "@prefix foaf: <http://xmlns.com/foaf/0.1/> .", "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .", ""]
def t(s, p, o): out.append(f"{s} {p} {o} .")
for r in rd("countries.csv"):
    s = f"av:Country_{loc(r['code'])}"; t(s, "a", "av:Country"); t(s, "rdfs:label", Q(r["name"]) + "@en")
for r in rd("cities.csv"):
    s = f"av:City_{loc(r['cityId'])}"; t(s, "a", "av:City"); t(s, "rdfs:label", Q(r["name"]) + "@en")
for r in rd("rel_in_country.csv"): t(f"av:City_{loc(r['startId'])}", "av:locatedIn", f"av:Country_{loc(r['endId'])}")
for r in rd("airports.csv"):
    s = f"av:Airport_{r['iata']}"; t(s, "a", "av:Airport"); t(s, "rdfs:label", Q(r["name"]) + "@en"); t(s, "av:iataCode", Q(r["iata"]))
for r in rd("rel_located_in.csv"): t(f"av:Airport_{r['startId']}", "av:locatedIn", f"av:City_{loc(r['endId'])}")
for r in rd("airlines.csv"):
    s = f"av:Airline_{r['code']}"; t(s, "a", "av:Airline"); t(s, "rdfs:label", Q(r["name"]) + "@en")
for r in rd("aircraft.csv"):
    s = f"av:Aircraft_{loc(r['registration'])}"; t(s, "a", "av:Aircraft")
    t(s, "av:registrationNumber", Q(r["registration"])); t(s, "av:seatCapacity", r["seatCapacity"])
for r in rd("rel_owned_by.csv"): t(f"av:Aircraft_{loc(r['startId'])}", "av:ownedBy", f"av:Airline_{r['endId']}")
for r in rd("pilots.csv"):
    s = f"av:Pilot_{r['pilotId']}"; t(s, "a", "av:Pilot"); t(s, "foaf:name", Q(r["name"]))
for r in rd("passengers.csv"):
    s = f"av:Passenger_{r['passengerId']}"; t(s, "a", "av:Passenger"); t(s, "foaf:name", Q(r["name"]))
for r in rd("risks.csv"):
    s = f"av:Risk_{r['riskId']}"; t(s, "a", "av:WeatherRisk" if r["kind"] == "weather" else "av:TechnicalRisk")
    t(s, "rdfs:label", Q(r["name"]) + "@en"); t(s, "av:riskLevel", r["level"])
F = lambda i: f"av:Flight_{loc(i)}"
for r in rd("flights.csv"):
    s = F(r["flightId"]); t(s, "a", "av:CargoFlight" if r["kind"] == "cargo" else "av:PassengerFlight")
    t(s, "av:flightNumber", Q(r["flightNumber"])); t(s, "av:scheduledDeparture", f'"{r["scheduledDeparture"]}"^^xsd:dateTime')
for fn, p, pre in [("rel_departs_from.csv", "av:departsFrom", "av:Airport_"), ("rel_arrives_at.csv", "av:arrivesAt", "av:Airport_"),
                   ("rel_operated_by.csv", "av:operatedBy", "av:Airline_"), ("rel_uses_aircraft.csv", "av:usesAircraft", "av:Aircraft_"),
                   ("rel_has_pilot.csv", "av:hasPilot", "av:Pilot_"), ("rel_has_passenger.csv", "av:hasPassenger", "av:Passenger_"),
                   ("rel_affected_by.csv", "av:affectedBy", "av:Risk_")]:
    for r in rd(fn): t(F(r["startId"]), p, pre + loc(r["endId"]))
for r in rd("delays.csv"):
    s = f"av:Delay_{r['delayId']}"; t(s, "a", "av:FlightDelay"); t(s, "av:delayMinutes", r["minutes"])
for r in rd("rel_has_delay.csv"):
    d = f"av:Delay_{r['endId']}"; t(d, "av:delaysFlight", F(r["startId"])); t(F(r["startId"]), "av:hasDelay", d)
for r in rd("rel_caused_by.csv"): t(f"av:Delay_{r['startId']}", "av:causedBy", f"av:Risk_{r['endId']}")
open(os.path.join(D, "data9.ttl"), "w", encoding="utf-8").write("\n".join(out) + "\n")
print("data9.ttl:", len([l for l in out if l.endswith(' .') and not l.startswith('@')]), "триплетів")
