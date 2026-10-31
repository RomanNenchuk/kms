#!/usr/bin/env python3
"""Генератор CSV для ЛР 9 (авіаперевезення). Детермінований: seed=42.
Довідкові дані (аеропорти/міста/країни) — публічні IATA-коди, складені вручну.
Рейси, пасажири, пілоти, ризики, затримки — СИНТЕТИЧНІ (сценарій), source=synthetic-*.
Запуск з кореня проєкту: python scripts/generate_data.py
"""
import csv, random, os, datetime as dt
from collections import defaultdict

random.seed(42)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(OUT, exist_ok=True)

SRC_REF = "iata-public-codes"
SRC_SYN = "synthetic-generator-v1"
SRC_SCN = "synthetic-risk-scenario"
REF_DATE = "2026-01-01"

# iata, назва аеропорту, id міста, назва міста, код країни
AIRPORTS = [
 ("LWO","Lviv Danylo Halytskyi","lviv","Lviv","UA"),("KBP","Kyiv Boryspil","kyiv","Kyiv","UA"),
 ("IEV","Kyiv Zhuliany","kyiv","Kyiv","UA"),("ODS","Odesa International","odesa","Odesa","UA"),
 ("HRK","Kharkiv International","kharkiv","Kharkiv","UA"),("DNK","Dnipro International","dnipro","Dnipro","UA"),
 ("IFO","Ivano-Frankivsk International","ivano-frankivsk","Ivano-Frankivsk","UA"),
 ("CWC","Chernivtsi International","chernivtsi","Chernivtsi","UA"),
 ("WAW","Warsaw Chopin","warsaw","Warsaw","PL"),("WMI","Warsaw Modlin","warsaw","Warsaw","PL"),
 ("KRK","Krakow John Paul II","krakow","Krakow","PL"),("GDN","Gdansk Lech Walesa","gdansk","Gdansk","PL"),
 ("WRO","Wroclaw Copernicus","wroclaw","Wroclaw","PL"),("KTW","Katowice Pyrzowice","katowice","Katowice","PL"),
 ("POZ","Poznan Lawica","poznan","Poznan","PL"),("RZE","Rzeszow Jasionka","rzeszow","Rzeszow","PL"),
 ("FRA","Frankfurt am Main","frankfurt","Frankfurt","DE"),("MUC","Munich","munich","Munich","DE"),
 ("BER","Berlin Brandenburg","berlin","Berlin","DE"),("HAM","Hamburg","hamburg","Hamburg","DE"),
 ("DUS","Dusseldorf","dusseldorf","Dusseldorf","DE"),("CGN","Cologne Bonn","cologne","Cologne","DE"),
 ("LHR","London Heathrow","london","London","GB"),("CDG","Paris Charles de Gaulle","paris","Paris","FR"),
 ("AMS","Amsterdam Schiphol","amsterdam","Amsterdam","NL"),("VIE","Vienna","vienna","Vienna","AT"),
 ("PRG","Prague Vaclav Havel","prague","Prague","CZ"),("BUD","Budapest Ferenc Liszt","budapest","Budapest","HU"),
 ("OTP","Bucharest Henri Coanda","bucharest","Bucharest","RO"),("IST","Istanbul Airport","istanbul","Istanbul","TR"),
 ("FCO","Rome Fiumicino","rome","Rome","IT"),("MAD","Madrid Barajas","madrid","Madrid","ES"),
 ("BCN","Barcelona El Prat","barcelona","Barcelona","ES"),("LIS","Lisbon Humberto Delgado","lisbon","Lisbon","PT"),
 ("ZRH","Zurich","zurich","Zurich","CH"),("CPH","Copenhagen Kastrup","copenhagen","Copenhagen","DK"),
 ("ARN","Stockholm Arlanda","stockholm","Stockholm","SE"),("HEL","Helsinki Vantaa","helsinki","Helsinki","FI"),
 ("OSL","Oslo Gardermoen","oslo","Oslo","NO"),("ATH","Athens Eleftherios Venizelos","athens","Athens","GR"),
 ("RIX","Riga International","riga","Riga","LV"),("VNO","Vilnius International","vilnius","Vilnius","LT"),
 ("TLL","Tallinn Lennart Meri","tallinn","Tallinn","EE"),("SOF","Sofia","sofia","Sofia","BG"),
 ("BEG","Belgrade Nikola Tesla","belgrade","Belgrade","RS"),("ZAG","Zagreb Franjo Tudman","zagreb","Zagreb","HR"),
 ("DUB","Dublin","dublin","Dublin","IE"),("BRU","Brussels","brussels","Brussels","BE"),
 ("TBS","Tbilisi International","tbilisi","Tbilisi","GE"),("KIV","Chisinau International","chisinau","Chisinau","MD"),
]
COUNTRIES = {"UA":"Ukraine","PL":"Poland","DE":"Germany","GB":"United Kingdom","FR":"France","NL":"Netherlands",
 "AT":"Austria","CZ":"Czechia","HU":"Hungary","RO":"Romania","TR":"Turkey","IT":"Italy","ES":"Spain","PT":"Portugal",
 "CH":"Switzerland","DK":"Denmark","SE":"Sweden","FI":"Finland","NO":"Norway","GR":"Greece","LV":"Latvia",
 "LT":"Lithuania","EE":"Estonia","BG":"Bulgaria","RS":"Serbia","HR":"Croatia","IE":"Ireland","BE":"Belgium",
 "GE":"Georgia","MD":"Moldova"}

# код, назва, країна, хаби, пул напрямків, розмір флоту, з них вантажних
AIRLINES = [
 ("SU","Sky Ukraine","UA",["KBP","LWO"],["IEV","ODS","HRK","DNK","IFO","CWC","WAW","KRK","FRA","IST","VIE","PRG","KIV","TBS","BER","RZE"],6,0),
 ("AL","AeroLink Europe","PL",["WAW","FRA"],["KRK","GDN","WRO","KTW","POZ","LWO","KBP","MUC","BER","HAM","DUS","CGN","LHR","CDG","AMS","BRU"],6,1),
 ("CA","CarpathAir","UA",["LWO","KRK"],["IFO","CWC","RZE","WAW","BUD","VIE","OTP","KIV","KBP","WMI","KTW","PRG"],4,0),
 ("BC","BaltiCair","LV",["RIX","VNO"],["TLL","HEL","ARN","CPH","WAW","GDN","BER","FRA","OSL"],4,0),
 ("EN","EuroNord","DK",["CPH","ARN"],["OSL","HEL","RIX","TLL","VNO","AMS","LHR","DUB","HAM","BER","GDN"],5,1),
 ("DJ","DanubeJet","AT",["VIE","BUD"],["OTP","SOF","BEG","ZAG","PRG","KIV","IST","MUC","ZRH","FCO","ATH","CWC"],4,0),
 ("AW","AlpineWings","CH",["ZRH","MUC"],["VIE","FRA","CDG","FCO","BCN","AMS","LHR","PRG","BRU","DUS"],3,0),
 ("MS","MedSky","IT",["FCO","MAD"],["BCN","LIS","ATH","IST","CDG","ZRH","SOF","BEG","ZAG","BUD","VIE","MUC"],4,0),
]
MODELS_PAX = [("Boeing 737-800",189),("Airbus A320",180),("Embraer E190",100),("Airbus A220-300",145),("ATR 72-600",70)]
MODEL_CARGO = ("Boeing 737-800F",0)

FIRST = ["Oleh","Iryna","Andrii","Olena","Taras","Natalia","Mykola","Sofiia","Jan","Anna","Piotr","Katarzyna",
         "Marek","Agnieszka","Lukas","Julia","Stefan","Hanna","Thomas","Klara","Maksym","Daryna","Viktor","Yulia"]
LAST = ["Kovalenko","Ivanenko","Bondar","Shevchenko","Melnyk","Tkachenko","Kravchuk","Boyko","Kowalski","Nowak",
        "Wisniewski","Wojcik","Schmidt","Muller","Weber","Fischer","Hrytsenko","Savchenko","Polishchuk","Lysenko"]


def w(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        cw = csv.writer(f, lineterminator="\n")
        cw.writerow(header)
        cw.writerows(rows)


REL_HDR = ["startId", "endId", "source", "confidence", "validFrom"]


def rel(name, rows, extra=None):
    w(name, REL_HDR + (extra or []), rows)


# ---------- довідкові вузли ----------
assert set(COUNTRIES) == {a[4] for a in AIRPORTS}
cities = {a[2]: (a[2], a[3]) for a in AIRPORTS}
w("countries.csv", ["code", "name"], [(c, COUNTRIES[c]) for c in sorted(COUNTRIES)])
w("cities.csv", ["cityId", "name"], sorted(cities.values()))
w("airports.csv", ["iata", "name"], [(a[0], a[1]) for a in AIRPORTS])
rel("rel_in_country.csv", [(s, c, SRC_REF, 1.0, REF_DATE) for s, c in sorted({(a[2], a[4]) for a in AIRPORTS})])
rel("rel_located_in.csv", [(a[0], a[2], SRC_REF, 1.0, REF_DATE) for a in AIRPORTS])

# ---------- авіакомпанії, судна ----------
w("airlines.csv", ["code", "name", "homeCountry"], [(a[0], a[1], a[2]) for a in AIRLINES])
aircraft = []  # (reg, model, seats, airline, cargo)
n = 1
for code, name, cc, hubs, pool, size, ncargo in AIRLINES:
    for i in range(size):
        cargo = i >= size - ncargo
        model, seats = MODEL_CARGO if cargo else MODELS_PAX[(n + i) % len(MODELS_PAX)]
        aircraft.append((f"{code}-{n:03d}", model, seats, code, cargo))
        n += 1
w("aircraft.csv", ["registration", "model", "seatCapacity"], [(a[0], a[1], a[2]) for a in aircraft])
rel("rel_owned_by.csv", [(a[0], a[3], SRC_SYN, 1.0, REF_DATE) for a in aircraft])

# ---------- імена ----------
names_used = set()


def uniq_name():
    while True:
        nm = f"{random.choice(FIRST)} {random.choice(LAST)}"
        if nm not in names_used:
            names_used.add(nm)
            return nm


# ---------- пілоти ----------
pilots = defaultdict(list)
pilot_rows = []
pid = 1
for code, name, cc, hubs, pool, size, ncargo in AIRLINES:
    for _ in range(size + 1):
        p = f"P{pid:03d}"
        pid += 1
        pilot_rows.append((p, uniq_name(), random.randint(1500, 14000)))
        pilots[code].append(p)
w("pilots.csv", ["pilotId", "name", "flightHours"], pilot_rows)

# ---------- рейси: ротації літаків (4 ноги на добу, 2 доби) ----------
DAYS = [dt.date(2026, 11, 2), dt.date(2026, 11, 3)]
flights = []
counters = defaultdict(lambda: 100)
by_airline = defaultdict(list)
for a in aircraft:
    by_airline[a[3]].append(a)
adef = {a[0]: a for a in AIRLINES}
for code, acs in by_airline.items():
    hubs, pool = adef[code][3], adef[code][4]
    for ai, ac in enumerate(acs):
        for di, day in enumerate(DAYS):
            h1 = hubs[0]
            h2 = hubs[1]
            d1, d2 = random.sample(pool, 2)
            legs = [(h1, d1), (d1, h2), (h2, d2), (d2, h1)]
            t = dt.datetime.combine(day, dt.time(5, 0)) + dt.timedelta(minutes=random.randint(0, 180) + ai * 15)
            for (o, d) in legs:
                counters[(code, day)] += 1
                num = f"{code}{counters[(code, day)]}"
                flights.append(dict(fid=f"{num}-{day:%Y%m%d}", num=num, dep=t, day=day, o=o, d=d, code=code,
                                    reg=ac[0], cargo=ac[4], pilot=pilots[code][(ai + di) % len(pilots[code])]))
                t += dt.timedelta(minutes=random.randint(170, 230))
for f in flights:
    assert f["o"] != f["d"], f
flights.sort(key=lambda f: (f["dep"], f["fid"]))
w("flights.csv", ["flightId", "flightNumber", "scheduledDeparture", "date", "kind"],
  [(f["fid"], f["num"], f["dep"].strftime("%Y-%m-%dT%H:%M:%S"), f["day"].isoformat(),
    "cargo" if f["cargo"] else "passenger") for f in flights])
D = lambda f: f["day"].isoformat()
rel("rel_departs_from.csv", [(f["fid"], f["o"], SRC_SYN, 0.98, D(f)) for f in flights])
rel("rel_arrives_at.csv", [(f["fid"], f["d"], SRC_SYN, 0.98, D(f)) for f in flights])
rel("rel_operated_by.csv", [(f["fid"], f["code"], SRC_SYN, 1.0, D(f)) for f in flights])
rel("rel_uses_aircraft.csv", [(f["fid"], f["reg"], SRC_SYN, 0.97, D(f)) for f in flights])
rel("rel_has_pilot.csv", [(f["fid"], f["pilot"], SRC_SYN, 0.95, D(f)) for f in flights])

# NEXT_LEG: наступна нога того ж літака (включно з переходом між добами)
byac = defaultdict(list)
for f in flights:
    byac[f["reg"]].append(f)
next_rows = []
for reg, fl in byac.items():
    fl.sort(key=lambda f: f["dep"])
    for a, b in zip(fl, fl[1:]):
        assert a["d"] == b["o"], (a["fid"], b["fid"])
        gap = int((b["dep"] - a["dep"]).total_seconds() // 60)
        next_rows.append((a["fid"], b["fid"], SRC_SYN, 0.95, b["day"].isoformat(), gap))
rel("rel_next_leg.csv", next_rows, ["gapMin"])

# ---------- пасажири ----------
pax = [(f"X{i:03d}", uniq_name()) for i in range(1, 91)]
w("passengers.csv", ["passengerId", "name"], pax)
seats = {a[0]: a[2] for a in aircraft}
state = {p[0]: (None, dt.datetime.min) for p in pax}
book = []
cur_day = None
for f in flights:
    if f["day"] != cur_day:
        cur_day = f["day"]
        state = {k: (None, dt.datetime.min) for k in state}
    if f["cargo"]:
        continue
    elig = [p for p, (loc, free) in state.items() if (loc is None or loc == f["o"]) and free <= f["dep"]]
    k = min(len(elig), random.randint(2, 5), seats[f["reg"]])
    for p in random.sample(elig, k):
        book.append((f["fid"], p, SRC_SYN, 0.9, D(f)))
        state[p] = (f["d"], f["dep"] + dt.timedelta(hours=3))
rel("rel_has_passenger.csv", book)

# ---------- ризики, затримки ----------
RISKS = [  # id, назва, тип, рівень, аеропорт, доба, год від, год до, (авіакомпанія, індекс літака)
 ("RK01", "Fog at Lviv", "weather", 3, "LWO", 0, 5, 11, None),
 ("RK02", "Hydraulic fault", "technical", 4, None, 0, None, None, ("AL", 1)),
 ("RK03", "Snowfall at Warsaw", "weather", 3, "WAW", 1, 6, 12, None),
 ("RK04", "Thunderstorm at Frankfurt", "weather", 4, "FRA", 0, 9, 16, None),
 ("RK05", "Crosswind at Gdansk", "weather", 2, "GDN", 0, 6, 16, None),
 ("RK06", "Fog at Riga", "weather", 3, "RIX", 1, 5, 10, None),
 ("RK07", "Avionics software fault", "technical", 3, None, 1, None, None, ("SU", 2)),
 ("RK08", "Storm at Istanbul", "weather", 5, "IST", 1, 6, 16, None),
 ("RK09", "Icing at Helsinki", "weather", 3, "HEL", 1, 5, 11, None),
 ("RK10", "Engine sensor warning", "technical", 4, None, 0, None, None, ("EN", 0)),
]
w("risks.csv", ["riskId", "name", "kind", "level"], [(r[0], r[1], r[2], r[3]) for r in RISKS])
at_airport, affected, delays, has_delay, caused = [], [], [], [], []
delay_of = {}
fby = {f["fid"]: f for f in flights}
nxt = {r[0]: r[1] for r in next_rows}
counter = [1]


def add_delay(fid, minutes, rk, propagated, conf):
    if fid in delay_of:
        return False
    d = f"D{counter[0]:03d}"
    counter[0] += 1
    delay_of[fid] = d
    day = fby[fid]["day"].isoformat()
    delays.append((d, minutes, "true" if propagated else "false"))
    has_delay.append((fid, d, SRC_SCN, conf, day))
    caused.append((d, rk, SRC_SCN, conf, day))
    return True


for rid, name, kind, level, ap, di, h1, h2, ac in RISKS:
    day = DAYS[di]
    if kind == "weather":
        at_airport.append((rid, ap, SRC_SCN, 0.9, day.isoformat()))
        hit = [f for f in flights if f["day"] == day and f["o"] == ap and h1 <= f["dep"].hour < h2]
    else:
        reg = by_airline[ac[0]][ac[1]][0]
        hit = [f for f in flights if f["day"] == day and f["reg"] == reg][1:]
    for f in hit:
        affected.append((f["fid"], rid, SRC_SCN, round(random.uniform(0.7, 0.95), 2), day.isoformat()))
        if random.random() < 0.8:
            m = level * random.randint(10, 22)
            if add_delay(f["fid"], m, rid, False, 0.9):
                cur, mm = f["fid"], m
                while cur in nxt and mm > 15:
                    cur = nxt[cur]
                    mm -= random.randint(12, 25)
                    if mm < 10:
                        break
                    add_delay(cur, mm, rid, True, 0.6)
rel("rel_at_airport.csv", at_airport)
rel("rel_affected_by.csv", affected)
w("delays.csv", ["delayId", "minutes", "propagated"], delays)
rel("rel_has_delay.csv", has_delay)
rel("rel_caused_by.csv", caused)

# ---------- статистика ----------
nodes = (len(COUNTRIES) + len(cities) + len(AIRPORTS) + len(AIRLINES) + len(aircraft) + len(pilot_rows)
         + len(pax) + len(flights) + len(RISKS) + len(delays))
rels = (len({(a[2], a[4]) for a in AIRPORTS}) + len(AIRPORTS) + len(aircraft) + 5 * len(flights) + len(next_rows)
        + len(book) + len(at_airport) + len(affected) + 2 * len(delays))
print("вузлів (з CSV):", nodes, "| зв'язків (з CSV, без похідних DIRECT_ROUTE/ROUTE_LINK):", rels)
print("рейсів", len(flights), "| бронювань", len(book), "| затримок", len(delays), "| AFFECTED_BY", len(affected))
