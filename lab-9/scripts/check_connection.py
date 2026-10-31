#!/usr/bin/env python3
"""Перевірка підключення з Python (Підготовка, ЛР 9). export NEO4J_PASSWORD=... ; python scripts/check_connection.py"""
import os, sys
from neo4j import GraphDatabase
pwd = os.getenv("NEO4J_PASSWORD") or sys.exit("Задайте NEO4J_PASSWORD")
with GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://localhost:7687"), auth=(os.getenv("NEO4J_USER", "neo4j"), pwd)) as d:
    d.verify_connectivity()
    r = d.execute_query("CALL dbms.components() YIELD name, versions, edition RETURN name, versions[0] AS v, edition")
    print("OK:", r.records[0].data())
    n = d.execute_query("MATCH (n) RETURN count(n) AS nodes").records[0]["nodes"]
    m = d.execute_query("MATCH ()-[r]->() RETURN count(r) AS rels").records[0]["rels"]
    print(f"вузлів: {n}, зв'язків: {m}")
