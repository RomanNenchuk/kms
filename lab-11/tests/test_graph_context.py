"""Тести Результату 2 (CSV-бекенд, без Neo4j і LLM): pytest tests/"""
import re
from src.graph_context import GraphContext, CsvBackend

gc = GraphContext(CsvBackend())


def test_linking_exact_and_name():
    assert gc.link("flight CA105-20261102 delay")[0]["nodes"] == [("Flight", "CA105-20261102")]
    assert gc.link("Fog in Lviv")[0]["nodes"] == [("Risk", "RK01")]            # «in» замість «at»
    assert gc.link("Які аеропорти у Львові?")[0]["nodes"] == [("City", "lviv")]  # укр. синонім


def test_longest_match_wins():
    ent = gc.link("Lviv Danylo Halytskyi airport")
    assert len(ent) == 1 and ent[0]["nodes"] == [("Airport", "LWO")]


def test_subgraph_limit_and_ids():
    src, info = gc.context_for("Which flights depart from LWO?")
    assert info["edges"] <= gc.max_edges and src[0]["id"] == "graph:LWO"
    assert "Airport#LWO" in src[0]["text"] and "Note:" in src[0]["text"]


def test_no_passenger_data():
    src, _ = gc.context_for("Who are the passengers on flight CA105-20261102?")
    assert src and not re.search(r"Passenger|HAS_PASSENGER", src[0]["text"])


def test_no_entity_no_context():
    assert gc.context_for("What is air cargo?")[0] == []
