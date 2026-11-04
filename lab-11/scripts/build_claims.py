#!/usr/bin/env python3
"""Протокол «LLM-експерт»: claims/claims.csv + claims/summary.md.

Твердження беруться з розбору LLM-судді (eval/rag_eval_results.jsonl). Рівні верифікації:
  V1  — є валідна цитата, суддя не підтверджений людиною (статус pending);
  V3  — відповідь перевірена людиною за текстом (eval/human_sheet.csv): verified або rejected.
Нічого не вигадується: без людської перевірки твердження лишаються pending.
Запуск: python scripts/build_claims.py [--sheet eval/human_sheet.csv] [--out-dir claims]
"""
import csv, json, sys, pathlib, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent


def arg(name, default):
    return pathlib.Path(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


def read_jsonl(p):
    out = []
    for line in open(p, encoding="utf-8"):
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass                                   # пошкоджені рядки пропускаємо
    return out


def read_sheet(p):
    """id -> (0/1, примітка). Назву колонки human_faithful беремо за префіксом (редактор міг її скоротити)."""
    out = {}
    if not p.exists():
        return out
    with open(p, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            col = next((k for k in row if k and k.startswith("human_faithful")), None)
            v = (row.get(col) or "").strip() if col else ""
            if v in ("0", "1"):
                out[row["id"]] = (int(v), (row.get("human_note") or "").strip())
    return out


def doc_of(evid):
    return evid.split("c#")[0] if "c#" in evid else evid


def main():
    sheet_p = arg("--sheet", ROOT / "eval" / "human_sheet.csv")
    out_dir = arg("--out-dir", ROOT / "claims")
    out_dir.mkdir(exist_ok=True)
    results = {r["id"]: r for r in read_jsonl(ROOT / "eval" / "rag_eval_results.jsonl")}
    corpus = {}
    for r in read_jsonl(ROOT / "data" / "corpus.jsonl"):
        corpus.setdefault(r["doc_id"], r.get("source_url") or r.get("title") or "")
    human = read_sheet(sheet_p)

    rows = []
    for rid, r in sorted(results.items()):
        j = r.get("judge") or {}
        if r.get("abstained") or not j.get("claims"):
            continue
        cit_ok = r["citations"].get("ok", False)
        h = human.get(rid)
        for i, c in enumerate(j["claims"], 1):
            verdict, ev = c.get("verdict", "?"), c.get("evidence_id") or ""
            if h and h[0] == 1:
                level, status, cm = "V3", "verified", f"людина: усі твердження відповіді підтверджені текстом; суддя: {verdict}"
            elif h and h[0] == 0 and verdict != "supported":
                level, status, cm = "V3", "rejected", f"людина відхилила відповідь; суддя: {verdict}"
            elif h and h[0] == 0:
                level, status, cm = "V1", "pending", "людина відхилила відповідь, але це твердження окремо не розібране: перевір вручну"
            else:
                level = "V1" if (cit_ok and ev) else ""
                status = "pending"
                cm = f"суддя: {verdict}; людиною не перевірено" + ("" if (cit_ok and ev) else "; без валідної цитати")
            if h and h[1]:
                cm += f"; примітка: {h[1]}"
            rows.append({"id": f"{rid}-{i}", "claim": c.get("claim", ""), "type": "факт",
                         "source": f"{ev} ({doc_of(ev)})" if ev else "", "level": level, "status": status, "comment": cm})

    with open(out_dir / "claims.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "claim", "type", "source", "level", "status", "comment"])
        w.writeheader()
        w.writerows(rows)

    n = len(rows)
    st = collections.Counter(r["status"] for r in rows)
    lv = collections.Counter(r["level"] or "—" for r in rows)
    docs = sorted({doc_of(r["source"].split(" ")[0]) for r in rows if r["source"]})
    rejected = [r for r in rows if r["status"] == "rejected"]
    checked = sorted(rid for rid in human if rid in results)
    lines = [
        "# Таблиця тверджень: підсумок (протокол «LLM-експерт»)", "",
        f"_Згенеровано `scripts/build_claims.py` з `eval/rag_eval_results.jsonl`; таблиця: `claims/claims.csv`._", "",
        f"- Усього тверджень: **{n}** (відповіді без відмови, розібрані суддею).",
        f"- Підтверджено людиною (verified, V3): **{st['verified']}** ({st['verified'] / max(1, n):.0%}).",
        f"- Відхилено (rejected): **{st['rejected']}**; очікують перевірки (pending): **{st['pending']}**.",
        f"- За рівнями: {dict(lv)}.",
        f"- Відповідей, перевірених людиною за текстом: **{len(checked)}** ({', '.join(checked) if checked else 'жодної'}).", "",
        "## Відхилені твердження",
    ]
    lines += [f"- `{r['id']}`: {r['claim']} — {r['comment']}" for r in rejected] or ["- Немає."]
    lines += ["", "## Перелік джерел (документи, на які посилаються твердження)"]
    lines += [f"- `{d}`" + (f" — {corpus[d]}" if corpus.get(d) else "") for d in docs]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"claims: {n} | статуси {dict(st)} | рівні {dict(lv)} | людиною перевірено відповідей: {len(checked)}")
    print(f"-> {out_dir / 'claims.csv'}, {out_dir / 'summary.md'}")


if __name__ == "__main__":
    main()