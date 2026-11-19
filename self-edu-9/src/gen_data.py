#!/usr/bin/env python3
"""Генерує синтетичний датасет «управління авіаційними перевезеннями».

Виходи (каталог data/):
  airports.csv, airlines.csv, aircraft.csv, flights.csv, routes.csv   — для LPG (Neo4j, Memgraph)
  avia.ttl                                                            — той самий граф як RDF (GraphDB)
  oracle.json                                                         — еталонні відповіді Q1–Q5,
                                                                         пораховані чистим Python

Аеропорти реальні (IATA-коди), а авіакомпанії, флот і розклад — вигадані (seed фіксований).
"""
import csv
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

import queries as Q

SEED = 9
N_FLIGHTS = 700
FLEET_PER_AIRLINE = 10
OUT = Path(__file__).resolve().parent.parent / "data"

# code, name, city, country, lat, lon
AIRPORTS = [
    ("KBP", "Boryspil International", "Kyiv", "UA", 50.345, 30.895),
    ("LWO", "Lviv Danylo Halytskyi", "Lviv", "UA", 49.813, 23.956),
    ("ODS", "Odesa International", "Odesa", "UA", 46.427, 30.676),
    ("WAW", "Warsaw Chopin", "Warsaw", "PL", 52.166, 20.967),
    ("KRK", "Krakow John Paul II", "Krakow", "PL", 50.078, 19.785),
    ("GDN", "Gdansk Lech Walesa", "Gdansk", "PL", 54.378, 18.466),
    ("RZE", "Rzeszow-Jasionka", "Rzeszow", "PL", 50.110, 22.019),
    ("PRG", "Vaclav Havel Prague", "Prague", "CZ", 50.101, 14.260),
    ("VIE", "Vienna International", "Vienna", "AT", 48.110, 16.570),
    ("BUD", "Budapest Ferenc Liszt", "Budapest", "HU", 47.437, 19.256),
    ("FRA", "Frankfurt am Main", "Frankfurt", "DE", 50.038, 8.562),
    ("MUC", "Munich", "Munich", "DE", 48.354, 11.786),
    ("BER", "Berlin Brandenburg", "Berlin", "DE", 52.367, 13.503),
    ("HAM", "Hamburg", "Hamburg", "DE", 53.630, 9.988),
    ("DUS", "Dusseldorf", "Dusseldorf", "DE", 51.289, 6.767),
    ("CGN", "Cologne Bonn", "Cologne", "DE", 50.866, 7.143),
    ("STR", "Stuttgart", "Stuttgart", "DE", 48.690, 9.222),
    ("AMS", "Amsterdam Schiphol", "Amsterdam", "NL", 52.311, 4.768),
    ("BRU", "Brussels", "Brussels", "BE", 50.901, 4.484),
    ("CDG", "Paris Charles de Gaulle", "Paris", "FR", 49.010, 2.548),
    ("ORY", "Paris Orly", "Paris", "FR", 48.723, 2.379),
    ("LHR", "London Heathrow", "London", "GB", 51.470, -0.454),
    ("LGW", "London Gatwick", "London", "GB", 51.154, -0.182),
    ("STN", "London Stansted", "London", "GB", 51.886, 0.239),
    ("MAN", "Manchester", "Manchester", "GB", 53.354, -2.275),
    ("DUB", "Dublin", "Dublin", "IE", 53.421, -6.270),
    ("MAD", "Madrid Barajas", "Madrid", "ES", 40.494, -3.567),
    ("BCN", "Barcelona El Prat", "Barcelona", "ES", 41.297, 2.083),
    ("LIS", "Lisbon Humberto Delgado", "Lisbon", "PT", 38.774, -9.134),
    ("FCO", "Rome Fiumicino", "Rome", "IT", 41.800, 12.239),
    ("MXP", "Milan Malpensa", "Milan", "IT", 45.631, 8.728),
    ("VCE", "Venice Marco Polo", "Venice", "IT", 45.505, 12.352),
    ("ATH", "Athens Eleftherios Venizelos", "Athens", "GR", 37.936, 23.945),
    ("IST", "Istanbul", "Istanbul", "TR", 41.275, 28.752),
    ("SAW", "Istanbul Sabiha Gokcen", "Istanbul", "TR", 40.899, 29.309),
    ("OTP", "Bucharest Henri Coanda", "Bucharest", "RO", 44.571, 26.085),
    ("SOF", "Sofia", "Sofia", "BG", 42.697, 23.411),
    ("BEG", "Belgrade Nikola Tesla", "Belgrade", "RS", 44.818, 20.309),
    ("ZAG", "Zagreb", "Zagreb", "HR", 45.743, 16.069),
    ("CPH", "Copenhagen Kastrup", "Copenhagen", "DK", 55.618, 12.651),
    ("ARN", "Stockholm Arlanda", "Stockholm", "SE", 59.652, 17.919),
    ("OSL", "Oslo Gardermoen", "Oslo", "NO", 60.198, 11.100),
    ("HEL", "Helsinki-Vantaa", "Helsinki", "FI", 60.317, 24.963),
    ("RIX", "Riga International", "Riga", "LV", 56.924, 23.971),
    ("VNO", "Vilnius", "Vilnius", "LT", 54.634, 25.286),
    ("TLL", "Tallinn Lennart Meri", "Tallinn", "EE", 59.413, 24.833),
    ("ZRH", "Zurich", "Zurich", "CH", 47.465, 8.549),
    ("GVA", "Geneva", "Geneva", "CH", 46.237, 6.109),
    ("DXB", "Dubai International", "Dubai", "AE", 25.253, 55.366),
    ("DOH", "Doha Hamad", "Doha", "QA", 25.273, 51.608),
    ("TLV", "Tel Aviv Ben Gurion", "Tel Aviv", "IL", 32.011, 34.887),
    ("CAI", "Cairo International", "Cairo", "EG", 30.122, 31.406),
    ("JFK", "New York JFK", "New York", "US", 40.641, -73.778),
    ("EWR", "Newark Liberty", "Newark", "US", 40.690, -74.175),
    ("ORD", "Chicago O'Hare", "Chicago", "US", 41.974, -87.907),
    ("ATL", "Atlanta Hartsfield-Jackson", "Atlanta", "US", 33.641, -84.428),
    ("YYZ", "Toronto Pearson", "Toronto", "CA", 43.678, -79.625),
    ("LAX", "Los Angeles", "Los Angeles", "US", 33.942, -118.408),
    ("TBS", "Tbilisi", "Tbilisi", "GE", 41.669, 44.955),
    ("EVN", "Yerevan Zvartnots", "Yerevan", "AM", 40.147, 44.396),
]
BIG = {"LHR", "FRA", "CDG", "AMS", "IST", "MAD", "FCO", "MUC", "VIE", "WAW", "KBP",
       "DXB", "ZRH", "CPH", "BCN", "JFK"}  # у вибірці «іншого кінця» мають вагу ×4

# code, name, country, hubs (вигадані авіакомпанії)
AIRLINES = [
    ("SKB", "SkyBridge Airlines", "UA", ["KBP", "WAW"]),
    ("NRD", "Nordwind Air", "DE", ["FRA", "MUC"]),
    ("DNP", "Dnipro Wings", "UA", ["KBP", "LWO"]),
    ("BLT", "Baltic Arrow", "LV", ["RIX", "HEL"]),
    ("AZR", "Azure Anatolia", "TR", ["IST", "SAW"]),
    ("CRP", "Carpathia Jet", "AT", ["VIE", "BUD"]),
    ("TIS", "Thames & Isles", "GB", ["LHR", "AMS"]),
    ("LVV", "Leopolis Air", "UA", ["LWO", "KRK"]),
    ("EUX", "EuroExpress", "FR", ["CDG", "FRA"]),
    ("MDW", "Midway Gulf", "AE", ["DXB", "DOH"]),
    ("ALP", "Alpine Connect", "CH", ["ZRH", "MUC"]),
    ("STP", "Scandi Transpolar", "SE", ["ARN", "CPH"]),
]

MODELS = {
    "regional": [("E190", 100), ("ATR 72-600", 70), ("A220-300", 145)],
    "narrow": [("A320-200", 180), ("B737-800", 189), ("A321neo", 220), ("B737 MAX 8", 178)],
    "wide": [("B787-9", 290), ("A330-300", 277), ("A350-900", 325)],
}


def haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[4], a[5], b[4], b[5]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def build():
    rng = random.Random(SEED)
    ap = {a[0]: a for a in AIRPORTS}
    codes = list(ap)
    weights = [4 if c in BIG else 1 for c in codes]

    fleet = defaultdict(list)
    aircraft = []
    for al in AIRLINES:
        classes = ["regional"] * 2 + ["narrow"] * 5 + ["wide"] * 3
        assert len(classes) == FLEET_PER_AIRLINE
        for i, cls in enumerate(classes, 1):
            model, seats = rng.choice(MODELS[cls])
            row = {"reg": f"{al[0]}-{i:02d}", "model": model, "cls": cls, "seats": seats, "airline": al[0]}
            aircraft.append(row)
            fleet[al[0]].append(row)

    airline_w = [3 if a[0] in ("SKB", "DNP", "TIS", "NRD", "EUX") else 2 for a in AIRLINES]
    flights = []
    for n in range(1, N_FLIGHTS + 1):
        al = rng.choices(AIRLINES, weights=airline_w)[0]
        hub = rng.choice(al[3])
        other = hub
        while other == hub:
            other = rng.choices(codes, weights=weights)[0]
        o, d = (hub, other) if rng.random() < 0.5 else (other, hub)
        dist = haversine_km(ap[o], ap[d])
        need = ("regional", "narrow") if dist < 800 else ("narrow",) if dist < 3800 else ("wide",)
        ac = rng.choice([a for a in fleet[al[0]] if a["cls"] in need])
        dep = rng.randrange(7) * 1440 + rng.randrange(60, 264) * 5  # хв від початку тижня, 05:00–22:00
        dur = int(30 + dist / 800 * 60)
        flights.append({
            "id": f"FL{n:04d}", "number": f"{al[0]}{100 + n % 900}", "airline": al[0], "aircraft": ac["reg"],
            "origin": o, "dest": d, "dep": dep, "arr": dep + dur, "duration_min": dur,
        })

    pairs = sorted({(f["origin"], f["dest"]) for f in flights})
    routes = [{"origin": o, "dest": d, "distance_km": round(haversine_km(ap[o], ap[d]))} for o, d in pairs]
    return aircraft, flights, routes


def compute_oracle(flights, routes):
    P = Q.P
    q1 = sorted(([f["id"], f["number"], f["dep"]] for f in flights if f["origin"] == P["ORIGIN"]),
                key=lambda r: (r[2], r[0]))
    c2 = Counter(f["airline"] for f in flights)
    q2 = sorted(([k, v] for k, v in c2.items()), key=lambda r: (-r[1], r[0]))

    c3 = Counter()
    for f1 in (f for f in flights if f["origin"] == P["TRIP_FROM"]):
        for f2 in flights:
            if (f2["origin"] == f1["dest"] and f2["dest"] == P["TRIP_TO"]
                    and f1["arr"] + P["MIN_LAYOVER"] <= f2["dep"] <= f1["arr"] + P["MAX_LAYOVER"]):
                c3[f1["dest"]] += 1
    q3 = sorted(([k, v] for k, v in c3.items()), key=lambda r: (-r[1], r[0]))

    adj = defaultdict(set)
    for r in routes:
        adj[r["origin"]].add(r["dest"])
    reach, frontier = set(), {P["REACH_START"]}
    for _ in range(P["REACH_HOPS"]):
        frontier = {b for a in frontier for b in adj[a]}
        reach |= frontier
    q4 = [[len(reach)]]

    c5 = Counter()
    for f in flights:
        c5[f["origin"]] += 1
        c5[f["dest"]] += 1
    q5 = sorted(([k, v] for k, v in c5.items()), key=lambda r: (-r[1], r[0]))[:5]
    return {"Q1": q1, "Q2": q2, "Q3": q3, "Q4": q4, "Q5": q5}


def lit(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_ttl(path, aircraft, flights, routes):
    L = ["@prefix ex: <http://example.org/avia#> .", ""]
    for c, name, city, country, lat, lon in AIRPORTS:
        L.append(f"ex:airport_{c} a ex:Airport ; ex:code {lit(c)} ; ex:name {lit(name)} ; ex:city {lit(city)} ; "
                 f"ex:country {lit(country)} ; ex:lat {lat} ; ex:lon {lon} .")
    for c, name, country, _ in AIRLINES:
        L.append(f"ex:airline_{c} a ex:Airline ; ex:code {lit(c)} ; ex:name {lit(name)} ; ex:country {lit(country)} .")
    for a in aircraft:
        L.append(f"ex:aircraft_{a['reg']} a ex:Aircraft ; ex:reg {lit(a['reg'])} ; ex:model {lit(a['model'])} ; "
                 f"ex:cls {lit(a['cls'])} ; ex:seats {a['seats']} .")
        L.append(f"ex:airline_{a['airline']} ex:owns ex:aircraft_{a['reg']} .")
    for f in flights:
        L.append(f"ex:flight_{f['id']} a ex:Flight ; ex:id {lit(f['id'])} ; ex:number {lit(f['number'])} ; "
                 f"ex:dep {f['dep']} ; ex:arr {f['arr']} ; ex:durationMin {f['duration_min']} ; "
                 f"ex:departsFrom ex:airport_{f['origin']} ; ex:arrivesAt ex:airport_{f['dest']} ; "
                 f"ex:operatedBy ex:airline_{f['airline']} ; ex:uses ex:aircraft_{f['aircraft']} .")
    for r in routes:
        # distance_km немає в RDF: у простому RDF не можна повісити атрибут на ребро (потрібен RDF-star/reification)
        L.append(f"ex:airport_{r['origin']} ex:route ex:airport_{r['dest']} .")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    OUT.mkdir(exist_ok=True)
    aircraft, flights, routes = build()
    write_csv(OUT / "airports.csv", [dict(zip(["code", "name", "city", "country", "lat", "lon"], a)) for a in AIRPORTS],
              ["code", "name", "city", "country", "lat", "lon"])
    write_csv(OUT / "airlines.csv", [{"code": a[0], "name": a[1], "country": a[2]} for a in AIRLINES],
              ["code", "name", "country"])
    write_csv(OUT / "aircraft.csv", aircraft, ["reg", "model", "cls", "seats", "airline"])
    write_csv(OUT / "flights.csv", flights,
              ["id", "number", "airline", "aircraft", "origin", "dest", "dep", "arr", "duration_min"])
    write_csv(OUT / "routes.csv", routes, ["origin", "dest", "distance_km"])
    write_ttl(OUT / "avia.ttl", aircraft, flights, routes)
    oracle = compute_oracle(flights, routes)
    (OUT / "oracle.json").write_text(json.dumps(oracle, ensure_ascii=False, indent=1), encoding="utf-8")

    nodes = len(AIRPORTS) + len(AIRLINES) + len(aircraft) + len(flights)
    edges = len(flights) * 4 + len(aircraft) + len(routes)
    print(f"Вузлів: {nodes} (Airport {len(AIRPORTS)}, Airline {len(AIRLINES)}, Aircraft {len(aircraft)}, "
          f"Flight {len(flights)}); ребер: {edges} (ROUTE {len(routes)})")
    for qid, rows in oracle.items():
        print(f"  {qid}: {len(rows)} рядків; перші: {rows[:3]}")


if __name__ == "__main__":
    main()
