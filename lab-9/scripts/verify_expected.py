#!/usr/bin/env python3
"""Незалежна перевірка (pandas/networkx) очікуваних результатів запитів — для ручної верифікації (Результат 3, C4).
Рахує з CSV те саме, що мають повернути запити Q1..Q13 у Neo4j. Запуск: python scripts/verify_expected.py"""
import os, pandas as pd, networkx as nx
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
r = lambda n: pd.read_csv(os.path.join(D, n))
fl, dep, arr = r("flights.csv"), r("rel_departs_from.csv"), r("rel_arrives_at.csv")
op, hd, dl = r("rel_operated_by.csv"), r("rel_has_delay.csv"), r("delays.csv")
hp, nl, pax = r("rel_has_passenger.csv"), r("rel_next_leg.csv"), r("passengers.csv")
aff, risks, ua = r("rel_affected_by.csv"), r("risks.csv"), r("rel_uses_aircraft.csv")
air, loc, inc = r("airports.csv"), r("rel_located_in.csv"), r("rel_in_country.csv")
route = dep.merge(arr, on="startId")[["endId_x", "endId_y"]].rename(columns={"endId_x": "a", "endId_y": "b"})
dr = route.groupby(["a", "b"]).size().reset_index(name="flights")
G = nx.DiGraph(); G.add_weighted_edges_from(dr.itertuples(index=False))
print("== Кількості ==")
print("DIRECT_ROUTE:", len(dr), "| ROUTE_LINK:", len({tuple(sorted(x)) for x in zip(dr.a, dr.b)}))
print("\n== Q1 рейси з LWO 2026-11-02 ==")
q1 = fl.merge(dep, left_on="flightId", right_on="startId").merge(arr, on="startId")
q1 = q1[(q1.endId_x == "LWO") & (q1.date == "2026-11-02")].sort_values("scheduledDeparture")
print(q1[["flightNumber", "scheduledDeparture", "endId_y"]].to_string(index=False))
print("\n== Q2 досяжні з LWO за <=3 перельоти:", len(nx.single_source_shortest_path_length(G, "LWO", cutoff=3)) - 1, "аеропортів")
print("   за <=1:", len(nx.single_source_shortest_path_length(G, "LWO", cutoff=1)) - 1, "| за <=2:", len(nx.single_source_shortest_path_length(G, "LWO", cutoff=2)) - 1)
print("\n== Q3 LWO->OSL: довжина", nx.shortest_path_length(G, "LWO", "OSL"), "; усі найкоротші:", list(nx.all_shortest_paths(G, "LWO", "OSL")))
print("\n== Q4 за авіакомпаніями ==")
t = op.merge(hd.rename(columns={"endId": "delayId"})[["startId", "delayId"]], on="startId", how="left").merge(dl, on="delayId", how="left")
q4 = t.groupby("endId").agg(flights=("startId", "nunique"), delayed=("delayId", "count"), totalMin=("minutes", "sum")).sort_values("totalMin", ascending=False)
print(q4.to_string())
print("\n== Q5 ризик>=2 без затримки ==")
a = aff.merge(risks, left_on="endId", right_on="riskId"); a = a[a.level >= 2]
q5 = a[~a.startId.isin(hd.startId)]
print(q5[["startId", "name", "level"]].sort_values(["level", "startId"], ascending=[False, True]).to_string(index=False))
print("\n== Q6 пасажири із затримками >60 (топ-10) ==")
x = hp.merge(hd.rename(columns={"endId": "delayId"})[["startId", "delayId"]], on="startId").merge(dl, on="delayId")
x = x[x.minutes > 60].merge(pax, left_on="endId", right_on="passengerId")
q6 = x.groupby("name").agg(total=("minutes", "sum"), flights=("startId", list)).reset_index().sort_values(["total", "name"], ascending=[False, True]).head(10)
print(q6.to_string(index=False))
print("\n== Q9 аеропорти України:", sorted(loc.merge(inc, left_on="endId", right_on="startId").query("endId_y=='UA'").startId_x))
print("== Q11 аеропорти без рейсів:", sorted(set(air.iata) - set(route.a) - set(route.b)))
nxt = nx.DiGraph(); nxt.add_edges_from(zip(nl.startId, nl.endId))
f0 = list(aff[aff.endId == "RK01"].startId)
reach = {}
for s in f0:
    for g, dpt in nx.single_source_shortest_path_length(nxt, s, cutoff=4).items():
        if g != s: reach[g] = min(reach.get(g, 99), dpt)
print("\n== Q12 RK01: уражені рейси", f0, "-> downstream:", len(reach), "рейсів; глибини:", pd.Series(reach).value_counts().sort_index().to_dict())
fra = fl[fl.date == "2026-11-02"].merge(dep, left_on="flightId", right_on="startId")
fra = list(fra[fra.endId == "FRA"].flightId)
imp = set()
for s in fra:
    imp |= set(nx.single_source_shortest_path_length(nxt, s, cutoff=3))
px = hp[hp.startId.isin(imp)].endId.nunique()
print("== Q13 закриття FRA 2026-11-02: вильотів", len(fra), "| рейсів у зоні впливу", len(imp), "| унікальних пасажирів", px)
