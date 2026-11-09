"""Результат 5: патерни й асоціативні правила на графі тверджень.

  python src/patterns.py                 # рахує у Python з data/gold.jsonl
  python src/patterns.py --neo4j         # те саме Cypher-запитами в Neo4j і звіряє числа (перехресна перевірка)
Пише results/patterns.json, data/patterns.cypher та docs/patterns_draft.md.
Для --neo4j: pip install neo4j; контейнер з docker-compose запущений.
"""
import argparse
import itertools
import json
from collections import defaultdict

import gold_tools as gt

CYPHER = {
    "P1_shared_hub": """MATCH (a:Airline)-[:HUB_AT]->(h:Airport)<-[:HUB_AT]-(b:Airline)
WHERE a.id < b.id
RETURN DISTINCT h.id AS hub, a.id AS a, b.id AS b ORDER BY hub, a, b""",  # DISTINCT: те саме твердження може прийти з кількох документів (паралельні ребра)
    "P1_same_group": """MATCH (a:Airline), (b:Airline)
WHERE a.id < b.id AND (
  EXISTS { MATCH (x:Entity)-[:OWNS_STAKE_IN]->(a), (x)-[:OWNS_STAKE_IN]->(b) }
  OR EXISTS { MATCH (a)-[:OWNS_STAKE_IN]->(b) } OR EXISTS { MATCH (b)-[:OWNS_STAKE_IN]->(a) })
RETURN a.id AS a, b.id AS b ORDER BY a, b""",
    "P2_chains": """MATCH (x:Entity)-[r1:OWNS_STAKE_IN]->(m:Airline)-[r2:OWNS_STAKE_IN]->(y:Entity)
WHERE x <> y
RETURN DISTINCT x.id AS x, m.id AS m, y.id AS y
ORDER BY x, m, y""",
    "P3_profiles": """MATCH (a:Airline)-[r]->()
WHERE type(r) IN ['HUB_AT','LOCATED_IN','OPERATES','SERVES','OWNS_STAKE_IN','AGREEMENT_WITH','OPERATED_BY','INVOLVED_IN']
RETURN a.id AS airline, collect(DISTINCT type(r)) AS rels ORDER BY airline""",
}


def load(path):
    return gt.read_jsonl(path)


def p1(claims):
    hubs = defaultdict(set)
    airlines = set()
    owns = defaultdict(set)
    for c in claims:
        for role in ("subject", "object"):
            if c[role]["type"] == "Airline":
                airlines.add(c[role]["canonical"])
        if c["relation"] == "HUB_AT":
            hubs[c["object"]["canonical"]].add(c["subject"]["canonical"])
        if c["relation"] == "OWNS_STAKE_IN":
            owns[c["subject"]["canonical"]].add(c["object"]["canonical"])
    pairs = sorted((h, a, b) for h, s in hubs.items() for a, b in itertools.combinations(sorted(s), 2))
    def related(a, b):
        return b in owns.get(a, ()) or a in owns.get(b, ()) or any(a in o and b in o for o in owns.values())
    all_pairs = list(itertools.combinations(sorted(airlines), 2))
    rel_all = {p for p in all_pairs if related(*p)}
    shared = {(a, b) for _, a, b in pairs}
    both = shared & rel_all
    n = len(all_pairs)
    conf = len(both) / len(shared) if shared else 0
    base = len(rel_all) / n if n else 0
    return {"hubs_total": len(hubs), "hubs_with_2plus": sum(1 for s in hubs.values() if len(s) > 1),
            "shared_hub_pairs": sorted(shared), "pairs_detail": pairs, "same_group_pairs_all": sorted(rel_all),
            "airline_pairs_total": n, "support_pairs": len(both), "support": round(len(both) / n, 4),
            "confidence": round(conf, 3), "baseline": round(base, 4), "lift": round(conf / base, 2) if base else None}


def p2(claims):
    """Ланцюги x -> m -> y за OWNS_STAKE_IN. Дублікати ребер зливаються, для ребра береться твердження з часом (точніше)."""
    edges = {}
    for c in claims:
        if c["relation"] != "OWNS_STAKE_IN":
            continue
        k = (c["subject"]["canonical"], c["object"]["canonical"])
        t = c.get("qualifiers", {}).get("time")
        e = edges.setdefault(k, {"time": None, "claims": [], "ev": c["evidence"]["text"]})
        e["claims"].append(c.get("claim_id"))
        if t and not e["time"]:
            e["time"], e["ev"] = t, c["evidence"]["text"]
    out_edges = defaultdict(list)
    for (x, y), e in edges.items():
        out_edges[x].append((y, e))
    rows = []
    for (x, m), e1 in sorted(edges.items()):
        if not m.startswith("airline:"):
            continue
        for y, e2 in sorted(out_edges.get(m, []), key=lambda t: t[0]):
            if x == y:
                continue
            t1, t2 = e1["time"], e2["time"]
            # x володіє m з t1, m вкладається в y у t2: у момент t2 ланцюг x->m->y існував лише якщо t1 <= t2
            status = ("consistent" if t1 <= t2 else "inconsistent") if (t1 and t2) else "unverified"
            rows.append({"x": x, "m": m, "y": y, "t1": t1, "t2": t2, "claims1": e1["claims"], "claims2": e2["claims"],
                         "status": status, "ev1": e1["ev"], "ev2": e2["ev"]})
    cnt = defaultdict(int)
    for r in rows:
        cnt[r["status"]] += 1
    return {"derived": len(rows), "by_status": dict(cnt), "rows": rows}


def p3(claims, min_support=3):
    prof = defaultdict(set)
    topic = set()
    for c in claims:
        for role in ("subject", "object"):
            if c[role].get("implicit_topic") and c[role]["type"] == "Airline":
                topic.add(c[role]["canonical"])
        if c["subject"]["type"] == "Airline":
            prof[c["subject"]["canonical"]].add(c["relation"])
    n = len(prof)
    items = sorted({i for s in prof.values() for i in s})
    sup = {i: sum(1 for s in prof.values() if i in s) for i in items}
    rules = []
    for a, b in itertools.permutations(items, 2):
        both = sum(1 for s in prof.values() if a in s and b in s)
        if both < min_support:
            continue
        conf = both / sup[a]
        lift = conf / (sup[b] / n)
        exc = sorted(k for k, s in prof.items() if a in s and b not in s)
        real = [k for k in exc if k in topic]            # профіль повний: справжній контрприклад
        gap = [k for k in exc if k not in topic]         # про авіакомпанію є дані лише з чужого документа
        ant_topic = [k for k in topic if a in prof.get(k, ())]
        conf_topic = (sum(1 for k in ant_topic if b in prof[k]) / len(ant_topic)) if ant_topic else None
        rules.append({"rule": f"{a} => {b}", "support": round(both / n, 3), "support_n": both, "confidence": round(conf, 3),
                      "lift": round(lift, 2), "exceptions": exc, "counterexamples_complete_profile": real,
                      "exceptions_explained_by_coverage": gap,
                      "confidence_topic_only": round(conf_topic, 3) if conf_topic is not None else None,
                      "n_topic": len(ant_topic)})
    rules.sort(key=lambda r: (-r["lift"], -r["confidence"], r["rule"]))
    return {"airlines": n, "topic_airlines": sorted(topic), "item_support": sup, "rules": rules,
            "profiles": {k: sorted(v) for k, v in sorted(prof.items())}}


def neo4j_check(res):
    from neo4j import GraphDatabase
    drv = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "kms-lab13-pass"))
    ok = {}
    with drv.session() as s:
        pairs = [(r["hub"], r["a"], r["b"]) for r in s.run(CYPHER["P1_shared_hub"])]
        ok["P1 пар зі спільним хабом"] = (len(pairs), len(res["p1"]["pairs_detail"]))
        grp = {(r["a"], r["b"]) for r in s.run(CYPHER["P1_same_group"])}
        ok["P1 пар однієї групи"] = (len(grp), len(res["p1"]["same_group_pairs_all"]))
        ch = list(s.run(CYPHER["P2_chains"]))
        ok["P2 похідних ланцюгів"] = (len(ch), res["p2"]["derived"])
        prof = {r["airline"]: set(r["rels"]) for r in s.run(CYPHER["P3_profiles"])}
        ok["P3 авіакомпаній з профілем"] = (len(prof), res["p3"]["airlines"])
    drv.close()
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", default=str(gt.ROOT / "data" / "gold.jsonl"))
    ap.add_argument("--neo4j", action="store_true")
    a = ap.parse_args()
    claims = load(a.claims)
    res = {"p1": p1(claims), "p2": p2(claims), "p3": p3(claims)}
    (gt.ROOT / "results").mkdir(exist_ok=True)
    (gt.ROOT / "results" / "patterns.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    (gt.ROOT / "data" / "patterns.cypher").write_text(
        "\n\n".join(f"// {k}\n{v};" for k, v in CYPHER.items()) + "\n", encoding="utf-8")
    P1, P2, P3 = res["p1"], res["p2"], res["p3"]
    print(f"P1: хабів {P1['hubs_total']}, зі ≥2 авіакомпаніями {P1['hubs_with_2plus']}; пар зі спільним хабом {len(P1['shared_hub_pairs'])}; "
          f"із них однієї групи {P1['support_pairs']}; conf={P1['confidence']} baseline={P1['baseline']} lift={P1['lift']}")
    print(f"P2: похідних ланцюгів {P2['derived']}, за статусом {P2['by_status']}")
    for r in P2["rows"]:
        print(f"   {r['x']} -> {r['m']} -> {r['y']}  t1={r['t1']} t2={r['t2']}  [{r['status']}]  {r['claims1']} {r['claims2']}")
    print(f"P3: авіакомпаній {P3['airlines']}; правил (support_n≥3): {len(P3['rules'])}")
    for r in P3["rules"][:10]:
        print(f"   {r['rule']:38} sup={r['support']} conf={r['confidence']} lift={r['lift']}  | топ-авіакомпанії: conf={r['confidence_topic_only']} (n={r['n_topic']}), справжніх контрприкладів: {len(r['counterexamples_complete_profile'])}, пояснено покриттям: {len(r['exceptions_explained_by_coverage'])}")
    if a.neo4j:
        print("Перехресна перевірка Python ↔ Neo4j (Neo4j, Python):")
        for k, (n4, py) in neo4j_check(res).items():
            print(f"   {k}: {n4}, {py}  {'OK' if n4 == py else 'РОЗБІЖНІСТЬ'}")


if __name__ == "__main__":
    main()