#!/usr/bin/env python3
"""Демонстрація безпеки text-to-Cypher (для звіту й захисту, питання 5).
Частина 1: валідатор блокує небезпечні запити ДО виконання.
Частина 2: навіть якщо валідатор обійти, READ-транзакція не дозволяє запис (перевіряємо на безпечному «пробному» вузлі).
Запуск з кореня проєкту (потрібні NEO4J_PASSWORD і активоване .venv):  python tests/safety_demo.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "t2c"))
import t2c
from neo4j import GraphDatabase

if not t2c.PWD:
    sys.exit("Задайте NEO4J_PASSWORD")
with GraphDatabase.driver(t2c.URI, auth=(t2c.USER, t2c.PWD)) as d:
    labels, rels = t2c.allowed_schema(d)
    print("=== Частина 1: валідатор ===")
    cases = [
        "MATCH (n) DETACH DELETE n",
        "MATCH (a:Airport) SET a.name = 'x' RETURN a",
        "CREATE (:Airport {iata:'ZZZ'}) RETURN 1",
        "LOAD CSV FROM 'file:///x.csv' AS row RETURN row",
        "CALL dbms.components() YIELD name RETURN name",
        "MATCH (a:Airplane) RETURN a",
        "MATCH (f:Flight)-[:FLIES_TO]->(a) RETURN f",
        "MATCH (a:Airport) RETURN a; MATCH (b) RETURN b",
        "MATCH (a:Airport) RETURN a.iata",
    ]
    for q in cases:
        ok, reason, final = t2c.validate(q, labels, rels)
        print(f"{'ПРОЙШОВ' if ok else 'ЗАБЛОКОВАНО':12s} {reason:32s} | {q}")

    print("\n=== Частина 2: READ-транзакція проти запису (обхід валідатора) ===")
    probe = "CREATE (n:SafetyProbe {t: 1}) RETURN n"
    try:
        t2c.read(d, probe)
        print("УВАГА: запис у READ-режимі НЕ було відхилено сервером!")
    except Exception as e:
        print("Сервер відхилив запис:", str(e).splitlines()[0][:200])
    left = d.execute_query("MATCH (n:SafetyProbe) RETURN count(n) AS c").records[0]["c"]
    print("Пробних вузлів у базі після спроби:", left)
    if left:
        d.execute_query("MATCH (n:SafetyProbe) DELETE n")
        print("Пробні вузли прибрано.")
