"""Генератор синтетичних даних: авіаперевезення -> зіркова схема (Parquet).

ДОКУМЕНТАЦІЯ ГЕНЕРАТОРА (вимога C1, результат 2)
------------------------------------------------
Детермінований: однаковий --seed і --rows дають ті самі дані.
Один рядок факту = один рейс (flight leg) за 2025 рік.

Припущення моделі:
* Аеропорти — 28 реальних європейських (координати наближені), 10 з них хаби.
  Авіакомпанії — 8 ВИГАДАНИХ (3 full-service, 3 low-cost, 2 regional), по 8 бортів.
* Регіональні авіакомпанії літають лише маршрутами < 1500 км.
* Попит: сезонність по місяцях (літо вище) і по днях тижня (пт/нд вище).
* Причина затримки — лист таксономії (клас -> підклас, IRI). Ймовірності залежать
  від сезону (зимою — сніг/туман, влітку — грози та завантаженість ATC) і від хабу.
* Затримка: «вчасно» = 0–14 хв; інакше lognormal за класом причини.
* Скасування: можливі лише при наявній причині (погода/техніка найімовірніші);
  для скасованих рейсів пасажири, дохід, пальне, затримка = 0.
* Завантаження ~ Beta(9, 2) з поправками на сезон і тип авіакомпанії.
* Дохід = пасажири * тариф(відстань, тип авіакомпанії) * шум; пальне = відстань * витрата типу ПС.
* dim_aircraft — SCD2: ~25% бортів мають переобладнання салону (зміна seats) у березні–вересні.
* airframe_hours — лічильник нальоту борту (напівадитивна міра), зростає з часом.

Запуск: python etl/generate.py --seed 42 --rows 5000
"""
from __future__ import annotations

import argparse
import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
DATASET_VERSION = "1.0"
YEAR = 2025
OPEN_END = date(9999, 12, 31)
IRI_BASE = "http://example.org/avia/delay#"

# iata, name, city, country, lat, lon, is_hub
AIRPORTS = [
    ("WAW", "Warsaw Chopin", "Warsaw", "Poland", 52.166, 20.967, 1),
    ("KRK", "Krakow John Paul II", "Krakow", "Poland", 50.078, 19.785, 0),
    ("GDN", "Gdansk Lech Walesa", "Gdansk", "Poland", 54.377, 18.466, 0),
    ("KTW", "Katowice", "Katowice", "Poland", 50.474, 19.080, 0),
    ("PRG", "Prague Vaclav Havel", "Prague", "Czechia", 50.101, 14.260, 0),
    ("VIE", "Vienna", "Vienna", "Austria", 48.110, 16.570, 1),
    ("BUD", "Budapest Liszt Ferenc", "Budapest", "Hungary", 47.439, 19.262, 0),
    ("FRA", "Frankfurt", "Frankfurt", "Germany", 50.033, 8.571, 1),
    ("MUC", "Munich", "Munich", "Germany", 48.354, 11.786, 1),
    ("BER", "Berlin Brandenburg", "Berlin", "Germany", 52.362, 13.501, 0),
    ("AMS", "Amsterdam Schiphol", "Amsterdam", "Netherlands", 52.309, 4.764, 1),
    ("BRU", "Brussels", "Brussels", "Belgium", 50.901, 4.484, 0),
    ("CDG", "Paris Charles de Gaulle", "Paris", "France", 49.010, 2.548, 1),
    ("LHR", "London Heathrow", "London", "United Kingdom", 51.470, -0.454, 1),
    ("DUB", "Dublin", "Dublin", "Ireland", 53.421, -6.270, 0),
    ("MAD", "Madrid Barajas", "Madrid", "Spain", 40.472, -3.561, 1),
    ("BCN", "Barcelona El Prat", "Barcelona", "Spain", 41.297, 2.078, 0),
    ("LIS", "Lisbon Humberto Delgado", "Lisbon", "Portugal", 38.774, -9.134, 0),
    ("FCO", "Rome Fiumicino", "Rome", "Italy", 41.800, 12.239, 0),
    ("MXP", "Milan Malpensa", "Milan", "Italy", 45.630, 8.723, 0),
    ("ZRH", "Zurich", "Zurich", "Switzerland", 47.458, 8.548, 1),
    ("CPH", "Copenhagen", "Copenhagen", "Denmark", 55.618, 12.656, 0),
    ("ARN", "Stockholm Arlanda", "Stockholm", "Sweden", 59.652, 17.919, 0),
    ("HEL", "Helsinki-Vantaa", "Helsinki", "Finland", 60.317, 24.963, 0),
    ("OTP", "Bucharest Henri Coanda", "Bucharest", "Romania", 44.572, 26.102, 0),
    ("SOF", "Sofia", "Sofia", "Bulgaria", 42.695, 23.406, 0),
    ("ATH", "Athens Eleftherios Venizelos", "Athens", "Greece", 37.936, 23.944, 0),
    ("IST", "Istanbul", "Istanbul", "Turkiye", 41.275, 28.752, 1),
]

# code, name, country, type, share of flights
AIRLINES = [
    ("SKB", "SkyBridge Air", "Germany", "full-service", 0.18),
    ("NRW", "Nordic Wings", "Sweden", "full-service", 0.10),
    ("MRD", "Meridian Airways", "France", "full-service", 0.14),
    ("EUL", "EuroLite", "Ireland", "low-cost", 0.22),
    ("ADJ", "AdriaJet", "Italy", "low-cost", 0.12),
    ("FLX", "Falcon Express", "Hungary", "low-cost", 0.08),
    ("CRP", "Carpathian Airlines", "Poland", "regional", 0.10),
    ("BLT", "BalticAir", "Finland", "regional", 0.06),
]

# type -> (manufacturer, seats, fuel kg per km)
AIRCRAFT_TYPES = {
    "A320": ("Airbus", 180, 3.1),
    "A321": ("Airbus", 220, 3.6),
    "A220-300": ("Airbus", 145, 2.8),
    "B737-800": ("Boeing", 189, 3.3),
    "B737 MAX 8": ("Boeing", 178, 2.9),
    "E190": ("Embraer", 100, 2.7),
    "ATR 72-600": ("ATR", 70, 1.4),
}
FLEET_BY_TYPE = {
    "full-service": ["A320", "A321", "A220-300", "B737 MAX 8"],
    "low-cost": ["A320", "B737-800", "A321"],
    "regional": ["E190", "ATR 72-600"],
}
FLEET_SIZE = 8

# ТАКСОНОМІЯ причин затримок (замініть/узгодьте з таксономією з ЛР 5).
# class, class_label, subclass, subclass_label
TAXONOMY = [
    ("NoDelay", "No delay", "OnTime", "On time"),
    ("Weather", "Weather", "Fog", "Fog"),
    ("Weather", "Weather", "Thunderstorm", "Thunderstorm"),
    ("Weather", "Weather", "SnowIce", "Snow / ice"),
    ("Weather", "Weather", "StrongWind", "Strong wind"),
    ("Technical", "Technical", "AircraftDefect", "Aircraft defect"),
    ("Technical", "Technical", "MaintenanceOverrun", "Maintenance overrun"),
    ("ATC", "Air traffic control", "AtcCongestion", "ATC congestion"),
    ("ATC", "Air traffic control", "AirspaceRestriction", "Airspace restriction"),
    ("Airport", "Airport operations", "GroundHandling", "Ground handling"),
    ("Airport", "Airport operations", "RunwayCapacity", "Runway capacity"),
    ("Airport", "Airport operations", "SecurityCheck", "Security check"),
    ("Crew", "Crew", "CrewShortage", "Crew shortage"),
    ("Crew", "Crew", "DutyTimeLimit", "Duty time limit"),
]
CLASSES = ["NoDelay", "Weather", "Technical", "ATC", "Airport", "Crew"]
SUBCLASSES = {c: [t[2] for t in TAXONOMY if t[0] == c] for c in CLASSES}

MONTH_DEMAND = [0.75, 0.72, 0.85, 0.95, 1.0, 1.1, 1.2, 1.2, 1.05, 0.95, 0.8, 0.9]
DOW_DEMAND = [1.0, 0.9, 0.9, 1.0, 1.15, 1.0, 1.1]  # пн..нд
HOUR_WEIGHTS = [1, 3, 5, 6, 5, 4, 4, 4, 5, 5, 5, 4, 4, 5, 5, 4, 3, 1]  # 05..22
CANCEL_PROB = {"Weather": 0.06, "Technical": 0.05, "ATC": 0.02, "Airport": 0.02, "Crew": 0.04}
DELAY_MU = {"Weather": 4.0, "Technical": 4.3, "ATC": 3.6, "Airport": 3.5, "Crew": 4.0}
SEASON = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
          6: "Summer", 7: "Summer", 8: "Summer", 9: "Autumn", 10: "Autumn", 11: "Autumn"}
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def haversine(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def build_dim_date() -> pd.DataFrame:
    days = pd.date_range(f"{YEAR}-01-01", f"{YEAR}-12-31", freq="D")
    return pd.DataFrame({
        "date_key": days.strftime("%Y%m%d").astype(int),
        "full_date": days.date,
        "year": days.year, "quarter": days.quarter, "month": days.month,
        "month_name": [MONTH_NAMES[m - 1] for m in days.month],
        "day": days.day, "day_of_week": days.dayofweek + 1,
        "day_name": [DAY_NAMES[d] for d in days.dayofweek],
        "is_weekend": days.dayofweek >= 5,
        "season": [SEASON[m] for m in days.month],
    })


def build_dim_airport() -> pd.DataFrame:
    df = pd.DataFrame(AIRPORTS, columns=["iata", "name", "city", "country", "latitude", "longitude", "is_hub"])
    df.insert(0, "airport_key", range(1, len(df) + 1))
    df["is_hub"] = df["is_hub"].astype(bool)
    return df


def build_dim_airline() -> pd.DataFrame:
    df = pd.DataFrame([a[:4] for a in AIRLINES], columns=["airline_code", "name", "country", "airline_type"])
    df.insert(0, "airline_key", range(1, len(df) + 1))
    return df


def build_dim_delay_cause() -> pd.DataFrame:
    rows = []
    for i, (cls, cls_label, sub, sub_label) in enumerate(TAXONOMY, start=1):
        rows.append((i, IRI_BASE + sub, sub_label, IRI_BASE + cls, cls_label))
    return pd.DataFrame(rows, columns=["delay_cause_key", "subclass_iri", "subclass_label", "class_iri", "class_label"])


def build_fleet(rng: np.random.Generator):
    """Повертає dim_aircraft (SCD2) та структуру fleets[airline_idx] -> список бортів."""
    rows, fleets, key = [], [], 1
    reg_no = 1
    for a_idx, (code, *_rest) in enumerate(AIRLINES):
        a_type = AIRLINES[a_idx][3]
        fleet = []
        for _ in range(FLEET_SIZE):
            t = str(rng.choice(FLEET_BY_TYPE[a_type]))
            manuf, seats, _burn = AIRCRAFT_TYPES[t]
            reg = f"SY-{code[0]}{reg_no:03d}"
            reg_no += 1
            versions = []
            if rng.random() < 0.25:  # переобладнання салону
                change = date(YEAR, 3, 1) + timedelta(days=int(rng.integers(0, 214)))
                new_seats = int(np.clip(seats + rng.choice([-12, -6, 6, 12]), 60, 260))
                versions.append((key, reg, t, manuf, seats, date(2024, 1, 1), change, False))
                versions.append((key + 1, reg, t, manuf, new_seats, change, OPEN_END, True))
                key += 2
            else:
                versions.append((key, reg, t, manuf, seats, date(2024, 1, 1), OPEN_END, True))
                key += 1
            rows.extend(versions)
            fleet.append({"reg": reg, "type": t, "versions": versions,
                          "hours0": float(rng.uniform(5000, 40000)),
                          "rate": float(rng.uniform(7, 11))})
        fleets.append(fleet)
    dim = pd.DataFrame(rows, columns=["aircraft_key", "registration", "aircraft_type", "manufacturer",
                                      "seats", "valid_from", "valid_to", "is_current"])
    return dim, fleets


def build_routes(rng, airports: pd.DataFrame):
    lat, lon, hub = airports["latitude"].values, airports["longitude"].values, airports["is_hub"].values
    n = len(airports)
    dist = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                dist[i, j] = haversine(lat[i], lon[i], lat[j], lon[j])
    routes = []  # по авіакомпаніях: (origin_idx, dest_idx)
    for code, _name, _country, a_type, _share in AIRLINES:
        max_d = 1500 if a_type == "regional" else 3500
        cand = [(i, j) for i in range(n) for j in range(n) if i != j and 300 <= dist[i, j] <= max_d]
        w = np.array([1.0 + 2.0 * (hub[i] or hub[j]) for i, j in cand])
        idx = rng.choice(len(cand), size=30, replace=False, p=w / w.sum())
        chosen = [cand[k] for k in idx]
        pop = 1.0 / (np.arange(1, len(chosen) + 1) ** 0.8)
        rng.shuffle(pop)
        routes.append((chosen, pop / pop.sum()))
    return dist, routes


def main(seed: int, rows: int) -> None:
    rng = np.random.default_rng(seed)
    DATA.mkdir(exist_ok=True)

    dim_date = build_dim_date()
    dim_airport = build_dim_airport()
    dim_airline = build_dim_airline()
    dim_cause = build_dim_delay_cause()
    dim_aircraft, fleets = build_fleet(rng)
    dist, routes = build_routes(rng, dim_airport)
    hub = dim_airport["is_hub"].values
    cause_key = {t[2]: i for i, t in enumerate(TAXONOMY, start=1)}

    # дати з сезонністю
    days = pd.date_range(f"{YEAR}-01-01", f"{YEAR}-12-31", freq="D")
    wd = np.array([MONTH_DEMAND[d.month - 1] * DOW_DEMAND[d.dayofweek] for d in days])
    day_idx = np.sort(rng.choice(len(days), size=rows, p=wd / wd.sum()))
    airline_idx = rng.choice(len(AIRLINES), size=rows, p=[a[4] for a in AIRLINES])
    hours = rng.choice(np.arange(5, 23), size=rows, p=np.array(HOUR_WEIGHTS) / sum(HOUR_WEIGHTS))

    recs = []
    for n in range(rows):
        d = days[day_idx[n]].date()
        month = d.month
        a = int(airline_idx[n])
        a_type = AIRLINES[a][3]
        chosen, pop = routes[a]
        r = int(rng.choice(len(chosen), p=pop))
        o, de = chosen[r]
        ac = fleets[a][int(rng.integers(0, FLEET_SIZE))]
        ver = next(v for v in ac["versions"] if v[5] <= d < v[6])
        seats, a_key = ver[4], ver[0]
        distance = round(float(dist[o, de]), 1)

        # причина затримки: клас -> підклас
        winter, summer = month in (12, 1, 2), month in (6, 7, 8)
        p_nodelay = 0.62 - 0.04 * bool(hub[o]) - 0.05 * (winter or summer)
        w = {"Weather": 0.16 * (2.5 if winter else 1.4 if summer else 1.0),
             "Technical": 0.14,
             "ATC": 0.14 * (1.8 if summer else 1.0) * (1.3 if hub[o] else 1.0),
             "Airport": 0.12 * (1.6 if hub[o] else 1.0),
             "Crew": 0.08}
        tot = sum(w.values())
        probs = [p_nodelay] + [(1 - p_nodelay) * w[c] / tot for c in CLASSES[1:]]
        cls = CLASSES[int(rng.choice(len(CLASSES), p=probs))]
        if cls == "Weather":
            sw = [0.3, 0.02, 0.5, 0.18] if winter else [0.05, 0.65, 0.0, 0.30] if summer else [0.3, 0.2, 0.05, 0.45]
        elif cls == "Technical":
            sw = [0.6, 0.4]
        elif cls == "ATC":
            sw = [0.7, 0.3]
        elif cls == "Airport":
            sw = [0.4, 0.35, 0.25]
        elif cls == "Crew":
            sw = [0.6, 0.4]
        else:
            sw = [1.0]
        sub = SUBCLASSES[cls][int(rng.choice(len(sw), p=np.array(sw) / sum(sw)))]

        cancelled = 0
        if cls == "NoDelay":
            delay = int(rng.integers(0, 15))
        else:
            delay = int(np.clip(rng.lognormal(DELAY_MU[cls], 0.6), 15, 600))
            if rng.random() < CANCEL_PROB[cls]:
                cancelled = 1

        lf = float(rng.beta(9, 2)) + (0.05 if summer else 0.0) + (0.04 if a_type == "low-cost" else 0.0)
        pax = int(min(seats, round(seats * min(lf, 1.0))))
        fare = (35 + 0.09 * distance) * {"low-cost": 0.7, "full-service": 1.25, "regional": 1.0}[a_type]
        revenue = round(pax * fare * float(rng.lognormal(0, 0.15)), 2)
        burn = AIRCRAFT_TYPES[ac["type"]][2]
        fuel = round(distance * burn * float(rng.lognormal(0, 0.05)) + 300, 1)
        airframe = round(ac["hours0"] + (d - date(YEAR, 1, 1)).days * ac["rate"] + int(hours[n]) / 24 * ac["rate"], 1)
        if cancelled:
            delay, pax, revenue, fuel = 0, 0, 0.0, 0.0

        recs.append((
            n + 1, f"{AIRLINES[a][0]}{100 + r}", int(d.strftime("%Y%m%d")), int(hours[n]),
            o + 1, de + 1, a + 1, a_key, cause_key[sub],
            distance, seats, pax, delay, fuel, revenue, cancelled, airframe,
        ))

    fact = pd.DataFrame(recs, columns=[
        "flight_id", "flight_number", "date_key", "scheduled_dep_hour",
        "origin_airport_key", "dest_airport_key", "airline_key", "aircraft_key", "delay_cause_key",
        "distance_km", "seats", "passengers", "delay_minutes", "fuel_kg", "revenue_usd",
        "cancelled", "airframe_hours",
    ])
    fact["scheduled_dep_hour"] = fact["scheduled_dep_hour"].astype("int16")
    fact["cancelled"] = fact["cancelled"].astype("int16")

    for name, df in [("dim_date", dim_date), ("dim_airport", dim_airport), ("dim_airline", dim_airline),
                     ("dim_aircraft", dim_aircraft), ("dim_delay_cause", dim_cause), ("fact_flight", fact)]:
        df.to_parquet(DATA / f"{name}.parquet", index=False)
        print(f"{name}: {len(df)} рядків")

    (DATA / "VERSION").write_text(
        f"dataset_version={DATASET_VERSION}\nseed={seed}\nrows={rows}\nyear={YEAR}\n"
        f"numpy={np.__version__}\npandas={pd.__version__}\n"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--rows", type=int, default=5000)
    a = p.parse_args()
    main(a.seed, a.rows)
