"""Доступ до сховища знань: data/<variant>/graph/*.csv і data/<variant>/corpus.jsonl.
Стани: lab11 (чисте сховище, еталон), baseline (baseline-v2 із синтетичними дефектами), clean (після очищення, ЛР 14)."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
VARIANTS = ("baseline", "clean", "lab11")

NODES = {
    "flights": ("Flight", "flightId"), "aircraft": ("Aircraft", "registration"), "airlines": ("Airline", "code"),
    "airports": ("Airport", "iata"), "cities": ("City", "cityId"), "countries": ("Country", "code"),
    "delays": ("Delay", "delayId"), "passengers": ("Passenger", "passengerId"), "pilots": ("Pilot", "pilotId"), "risks": ("Risk", "riskId"),
}
RELS = {
    "rel_affected_by": ("Flight", "affectedBy", "Risk"), "rel_arrives_at": ("Flight", "arrivesAt", "Airport"),
    "rel_at_airport": ("Risk", "atAirport", "Airport"), "rel_caused_by": ("Delay", "causedBy", "Risk"),
    "rel_departs_from": ("Flight", "departsFrom", "Airport"), "rel_has_delay": ("Flight", "hasDelay", "Delay"),
    "rel_has_passenger": ("Flight", "hasPassenger", "Passenger"), "rel_has_pilot": ("Flight", "hasPilot", "Pilot"),
    "rel_in_country": ("City", "inCountry", "Country"), "rel_located_in": ("Airport", "locatedIn", "City"),
    "rel_next_leg": ("Flight", "nextLeg", "Flight"), "rel_operated_by": ("Flight", "operatedBy", "Airline"),
    "rel_owned_by": ("Aircraft", "ownedBy", "Airline"), "rel_uses_aircraft": ("Flight", "usesAircraft", "Aircraft"),
}


def data_dir(variant: str) -> Path:
    if variant not in VARIANTS:
        raise ValueError(f"variant має бути одним із {VARIANTS}, а не {variant!r}")
    d = ROOT / "data" / variant
    if not d.exists():
        raise FileNotFoundError(d)
    return d


def load_tables(variant: str) -> dict[str, pd.DataFrame]:
    """Усі CSV графа; усе читається як рядки (щоб не губити нулі й коди на кшталт 'NA')."""
    return {p.stem: pd.read_csv(p, dtype=str, keep_default_na=False) for p in sorted((data_dir(variant) / "graph").glob("*.csv"))}


def load_corpus(variant: str) -> list[dict]:
    return [json.loads(line) for line in open(data_dir(variant) / "corpus.jsonl", encoding="utf-8") if line.strip()]


def data_fingerprint(variant: str) -> str:
    """SHA-256 усіх файлів стану (graph/*.csv + corpus.jsonl): однакові дані дають однаковий відбиток."""
    d, h = data_dir(variant), hashlib.sha256()
    for p in sorted((d / "graph").glob("*.csv")) + [d / "corpus.jsonl"]:
        h.update(p.name.encode()); h.update(p.read_bytes())
    return h.hexdigest()
