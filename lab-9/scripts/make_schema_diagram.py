#!/usr/bin/env python3
"""Генерує docs/graph_schema.drawio (відкривається в draw.io / diagrams.net) і docs/graph_schema.png (graphviz)."""
import os, subprocess, html
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
NODES = {  # label: (ключ, інші властивості, x, y, колір)
 "Country":   ("code", "name", 80, 40, "#e1d5e7"),
 "City":      ("cityId", "name", 80, 200, "#e1d5e7"),
 "Airport":   ("iata", "name, pagerank, community", 80, 380, "#dae8fc"),
 "Risk":      ("riskId", "name, level  [:WeatherRisk|:TechnicalRisk]", 80, 600, "#f8cecc"),
 "FlightDelay": ("delayId", "minutes, propagated", 400, 600, "#f8cecc"),
 "Flight":    ("flightId", "flightNumber, scheduledDeparture, date  [:PassengerFlight|:CargoFlight]", 400, 380, "#fff2cc"),
 "Airline":   ("code", "name, homeCountry", 760, 200, "#d5e8d4"),
 "Aircraft":  ("registration", "model, seatCapacity", 760, 380, "#d5e8d4"),
 "Pilot":     ("pilotId", "name, flightHours  [+:Person]", 760, 560, "#ffe6cc"),
 "Passenger": ("passengerId", "name  [+:Person]", 760, 700, "#ffe6cc"),
}
EDGES = [  # from, to, type
 ("City","Country","IN_COUNTRY"),("Airport","City","LOCATED_IN"),("Aircraft","Airline","OWNED_BY"),
 ("Flight","Airport","DEPARTS_FROM"),("Flight","Airport","ARRIVES_AT"),("Flight","Airline","OPERATED_BY"),
 ("Flight","Aircraft","USES_AIRCRAFT"),("Flight","Pilot","HAS_PILOT"),("Flight","Passenger","HAS_PASSENGER"),
 ("Flight","Risk","AFFECTED_BY"),("Risk","Airport","AT_AIRPORT"),("Flight","FlightDelay","HAS_DELAY"),
 ("FlightDelay","Risk","CAUSED_BY"),("Flight","Flight","NEXT_LEG"),("Airport","Airport","DIRECT_ROUTE (derived)"),
]
# ---- draw.io ----
cells, ids = [], {}
nid = 2
for lab, (key, props, x, y, col) in NODES.items():
    ids[lab] = f"n{nid}"; nid += 1
    val = html.escape(f"<b>:{lab}</b><br/>🔑 {key}<br/><i>{props}</i>", quote=True)
    cells.append(f'<mxCell id="{ids[lab]}" value="{val}" style="rounded=1;whiteSpace=wrap;html=1;fillColor={col};strokeColor=#666666;align=left;spacingLeft=8;" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="270" height="90" as="geometry"/></mxCell>')
for a, b, t in EDGES:
    cells.append(f'<mxCell id="e{nid}" value="{html.escape(t)}" style="endArrow=classic;html=1;rounded=1;fontSize=11;labelBackgroundColor=#ffffff;" edge="1" parent="1" source="{ids[a]}" target="{ids[b]}"><mxGeometry relative="1" as="geometry"/></mxCell>')
    nid += 1
xml = ('<mxfile><diagram name="Aviation LPG schema"><mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" page="1" pageWidth="1169" pageHeight="900"><root>'
       '<mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(cells) + '</root></mxGraphModel></diagram></mxfile>')
open(os.path.join(ROOT, "docs", "graph_schema.drawio"), "w", encoding="utf-8").write(xml)
# ---- graphviz PNG ----
dot = ['digraph G {rankdir=LR; fontname="Helvetica"; node [shape=record, style="rounded,filled", fontname="Helvetica", fontsize=10]; edge [fontname="Helvetica", fontsize=9];']
for lab, (key, props, x, y, col) in NODES.items():
    dot.append(f'{lab} [fillcolor="{col}", label="{{:{lab}|key: {key}\\l{props.replace("[","(").replace("]",")").replace("|"," / ")}\\l}}"];')
for a, b, t in EDGES:
    dot.append(f'{a} -> {b} [label="{t}"{", style=dashed" if "derived" in t else ""}];')
dot.append("}")
p = os.path.join(ROOT, "docs", "graph_schema.dot"); open(p, "w").write("\n".join(dot))
subprocess.run(["dot", "-Tpng", "-Gdpi=130", p, "-o", os.path.join(ROOT, "docs", "graph_schema.png")], check=True)
os.remove(p)
print("ok")
