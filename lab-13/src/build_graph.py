"""Будує data/graph_load.cypher: вузли (Entity + Document), ребра-твердження з походженням, зв'язки з Wikidata.

  python src/build_graph.py                              # золоті твердження (data/gold.jsonl)
  python src/build_graph.py --claims results/llm_test.jsonl --source gemini --out data/graph_load_llm.cypher
Завантаження в Neo4j (контейнер з docker-compose.yml):
  docker exec -i kms-lab13-neo4j cypher-shell -u neo4j -p kms-lab13-pass < data/graph_load.cypher
"""
import argparse
import csv
import json
from collections import Counter, defaultdict

import gold_tools as gt


def q(v):
    return json.dumps(v, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", default=str(gt.ROOT / "data" / "gold.jsonl"))
    ap.add_argument("--source", default="gold")
    ap.add_argument("--out", default=str(gt.ROOT / "data" / "graph_load.cypher"))
    ap.add_argument("--reset", action="store_true", help="додати на початок видалення всього графа (ребра створюються через CREATE, тож повторне завантаження без reset дублює їх)")
    a = ap.parse_args()
    claims = gt.read_jsonl(a.claims)
    sources = {r["doc_id"]: r for r in csv.DictReader(open(gt.ROOT / "data" / "sources.csv", encoding="utf-8"))}
    links = {}
    lp = gt.ROOT / "data" / "entity_links.csv"
    if lp.exists():
        for r in csv.DictReader(open(lp, encoding="utf-8")):
            v = (r.get("verified") or "").strip()
            qid = r["qid"] if v.lower() == "y" else (v if v.upper().startswith("Q") else "")
            if qid:
                links[r["canonical"]] = {"qid": qid, "label": r["wd_label"] if v.lower() == "y" else ""}
    ents, surf, docs_of = {}, defaultdict(Counter), defaultdict(set)
    for c in claims:
        for role in ("subject", "object"):
            m = c[role]
            ents[m["canonical"]] = m["type"]
            docs_of[m["canonical"]].add(c["doc_id"])
            if m.get("text"):
                surf[m["canonical"]][m["text"]] += 1
    L = ["// Згенеровано src/build_graph.py. Джерело тверджень: " + a.source,
         "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;",
         "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;"]
    if a.reset:
        L.append("MATCH (n) DETACH DELETE n;")
    for d in sorted({c["doc_id"] for c in claims}):
        s = sources.get(d, {})
        L.append(f'MERGE (d:Document {{id: {q(d)}}}) SET d.title = {q(s.get("title", ""))}, d.url = {q(s.get("url", ""))}, '
                 f'd.revid = {q(s.get("revid", ""))}, d.license = {q(s.get("license", ""))}, d.publisher = {q(s.get("publisher", ""))};')
    for cid, t in sorted(ents.items()):
        name = surf[cid].most_common(1)[0][0] if surf[cid] else cid.split(":", 1)[1].replace("_", " ").title()
        lk = links.get(cid)
        props = f'e.name = {q(name)}, e.type = {q(t)}'
        if lk:
            props += f', e.wikidata_id = {q(lk["qid"])}, e.wikidata_url = {q("https://www.wikidata.org/wiki/" + lk["qid"])}'
        L.append(f'MERGE (e:Entity:{t} {{id: {q(cid)}}}) SET {props};')
        for d in sorted(docs_of[cid]):
            L.append(f'MATCH (e:Entity {{id: {q(cid)}}}), (d:Document {{id: {q(d)}}}) MERGE (e)-[:MENTIONED_IN]->(d);')
    for i, c in enumerate(claims, 1):
        ev, ql = c["evidence"], c.get("qualifiers", {})
        p = {"claim_id": c.get("claim_id", f"{a.source}-{i:04d}"), "source": a.source, "doc_id": c["doc_id"],
             "evidence": ev["text"], "ev_start": ev.get("start"), "ev_end": ev.get("end"),
             "modality": c.get("modality", "asserted"), "annotator": c.get("annotator", "")}
        if "provenance" in c:
            p["model"] = c["provenance"].get("model", "")
            p["prompt_version"] = c["provenance"].get("prompt_version", "")
        for k in ("time", "count", "role", "kind"):
            if k in ql:
                p[k] = ql[k]
        if "amount" in ql:
            p["amount_value"], p["amount_currency"] = ql["amount"]["value"], ql["amount"]["currency"]
        pr = ", ".join(f"{k}: {q(v)}" for k, v in p.items() if v is not None)
        L.append(f'MATCH (s:Entity {{id: {q(c["subject"]["canonical"])}}}), (o:Entity {{id: {q(c["object"]["canonical"])}}}) '
                 f'CREATE (s)-[:{c["relation"]} {{{pr}}}]->(o);')
    open(a.out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"Записано {a.out}: {len(ents)} сутностей, {len(claims)} тверджень, зв'язано з Wikidata: {sum(1 for e in ents if e in links)}")


if __name__ == "__main__":
    main()