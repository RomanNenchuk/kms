"""Інструменти золотого набору.

  python src/gold_tools.py fill     data/gold_draft_raw.jsonl data/gold_draft.jsonl   # додає claim_id та офсети
  python src/gold_tools.py validate data/gold_draft.jsonl                              # схема + сигнатури + підрядки
  python src/gold_tools.py stats    data/gold_draft.jsonl                              # кількості
  python src/gold_tools.py review   data/gold_draft.jsonl [D06]                        # читабельний перегляд для звірки
  python src/gold_tools.py agree    data/gold.jsonl data/annotator2.jsonl              # узгодженість двох розмітників (F1, κ)
  python src/gold_tools.py split    data/gold.jsonl data/split.json [DOC,DOC..]        # dev/test за документами (seed 42)
  python src/gold_tools.py score    results/rules_dev.jsonl data/gold.jsonl dev [--errors]  # P/R/F1 для налаштування на dev
  python src/gold_tools.py diff     data/gold_draft_raw.jsonl data/gold.jsonl          # що змінила людина: видалено/додано/змінено
  python src/gold_tools.py claims   data/gold.jsonl claims/claims.csv [data/rejected.jsonl] [--verified]

Схема береться з першого блоку ```json у docs/extraction_schema.md (єдине джерело істини).
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
SCHEMA_MD = ROOT / "docs" / "extraction_schema.md"

A, AP, AC, O, L, F, E, P, R = ("Airline", "Airport", "AircraftType", "Organization", "Location",
                               "Flight", "Event", "Person", "Regulation")
SIGNATURES = {
    "HUB_AT": ({A}, {AP}),
    "SERVES": ({A, F}, {AP, L}),
    "OPERATES": ({A}, {AC}),
    "MANUFACTURED_BY": ({AC}, {O}),
    "OWNS_STAKE_IN": ({O, A, P}, {A, AP, O}),
    "LOCATED_IN": ({AP, A, O, L}, {L}),
    "OPERATED_BY": ({F}, {A}),
    "INVOLVED_IN": ({P, F, A, AC, AP}, {E, F}),
    "ISSUED_BY": ({R}, {O}),
    "AGREEMENT_WITH": ({A, O}, {A, O}),
}


def load_schema():
    md = SCHEMA_MD.read_text(encoding="utf-8")
    return json.loads(re.search(r"```json\n(.*?)```", md, re.S).group(1))


def read_doc(doc_id):
    return (RAW / f"{doc_id}.txt").read_text(encoding="utf-8")


def read_jsonl(path):
    """Читає JSONL; терпимий до склеєних рядків (кілька об'єктів підряд) і CRLF."""
    text, dec, i, out = Path(path).read_text(encoding="utf-8-sig"), json.JSONDecoder(), 0, []
    while True:
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            return out
        obj, i = dec.raw_decode(text, i)
        out.append(obj)


def write_jsonl(path, rows):
    Path(path).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def slug(s):
    import unicodedata
    s = s.replace("–", " ").replace("—", " ")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def find_all(text, sub, lo=0, hi=None):
    hi = len(text) if hi is None else hi
    out, i = [], text.find(sub, lo, hi)
    while i != -1:
        out.append(i)
        i = text.find(sub, i + 1, hi)
    return out


def overlaps(a, b):
    return a[0] < b[1] and b[0] < a[1]


def cmd_fill(src, dst):
    rows, errors, counters = read_jsonl(src), [], Counter()
    docs = {}
    out = []
    for n, r in enumerate(rows, 1):
        d = r["doc_id"]
        text = docs.setdefault(d, read_doc(d))
        where = f"рядок {n} ({d})"
        ev = r["evidence"]["text"]
        hits = find_all(text, ev)
        if not hits:                       # запасний пошук, нечутливий до пробілів/переносів
            idx = [i for i, ch in enumerate(text) if not ch.isspace()]
            flat, want = "".join(text[i] for i in idx), "".join(ev.split())
            pos = find_all(flat, want) if want else []
            if len(pos) == 1:
                es, ee = idx[pos[0]], idx[pos[0] + len(want) - 1] + 1
                print(f"УВАГА {where}: evidence виправлено до точного підрядка: {text[es:ee]!r}")
                r["evidence"]["text"] = ev = text[es:ee]
                hits = [es]
        if len(hits) != 1:
            errors.append(f"{where}: evidence знайдено {len(hits)} раз(и): {ev[:70]!r}")
            continue
        es, ee = hits[0], hits[0] + len(ev)
        r["evidence"]["start"], r["evidence"]["end"] = es, ee
        taken = []
        for role in ("subject", "object"):
            m = r[role]
            if m.get("implicit_topic"):
                continue
            if "start" in m and "end" in m and text[m["start"]:m["end"]] == m["text"] and es <= m["start"] and m["end"] <= ee \
                    and not any(overlaps((m["start"], m["end"]), t) for t in taken):
                taken.append((m["start"], m["end"]))      # уже коректні офсети лишаємо
                continue
            cand = [i for i in find_all(text, m["text"], es, ee)
                    if not any(overlaps((i, i + len(m["text"])), t) for t in taken)]
            if not cand:
                errors.append(f"{where}: {role} {m['text']!r} не знайдено в evidence (або перекривається)")
                continue
            if len(cand) > 1:
                print(f"УВАГА {where}: {role} {m['text']!r} має {len(cand)} входжень в evidence, взято перше")
            m["start"], m["end"] = cand[0], cand[0] + len(m["text"])
            taken.append((m["start"], m["end"]))
        counters[d] += 1
        r["claim_id"] = f"{d}-{counters[d]:03d}"
        out.append(r)
    if errors:
        print("\n".join(errors))
        sys.exit(f"{len(errors)} помилок; файл не записано.")
    write_jsonl(dst, out)
    print(f"Записано {len(out)} тверджень у {dst}")


def cmd_validate(path):
    schema, rows, errors = load_schema(), read_jsonl(path), []
    validator = jsonschema.Draft202012Validator(schema)
    docs, seen = {}, set()
    for r in rows:
        cid = r.get("claim_id", "?")
        for e in validator.iter_errors(r):
            errors.append(f"{cid}: схема: {e.message}")
        if cid in seen:
            errors.append(f"{cid}: дубль claim_id")
        seen.add(cid)
        try:
            text = docs.setdefault(r["doc_id"], read_doc(r["doc_id"]))
            rel, s, o = r["relation"], r["subject"], r["object"]
            sig = SIGNATURES[rel]
            if s["type"] not in sig[0] or o["type"] not in sig[1]:
                errors.append(f"{cid}: сигнатура {rel}: {s['type']} -> {o['type']} недопустима")
            if rel == "AGREEMENT_WITH" and "kind" not in r.get("qualifiers", {}):
                errors.append(f"{cid}: AGREEMENT_WITH без qualifiers.kind")
            ev = r["evidence"]
            if text[ev["start"]:ev["end"]] != ev["text"]:
                errors.append(f"{cid}: офсети evidence не збігаються з текстом")
            for role, m in (("subject", s), ("object", o)):
                if m.get("implicit_topic"):
                    title_slug = slug(text.split("\n", 1)[0])
                    if m["canonical"].split(":", 1)[1] != title_slug:
                        print(f"УВАГА {cid}: implicit_topic, але canonical ≠ заголовок документа")
                    continue
                if text[m["start"]:m["end"]] != m["text"]:
                    errors.append(f"{cid}: офсети {role} не збігаються з текстом")
                elif not (ev["start"] <= m["start"] and m["end"] <= ev["end"]):
                    errors.append(f"{cid}: {role} поза evidence")
            if s.get("implicit_topic") and o.get("implicit_topic"):
                errors.append(f"{cid}: обидва кінці implicit_topic")
        except (KeyError, TypeError, FileNotFoundError) as ex:
            errors.append(f"{cid}: {type(ex).__name__}: {ex}")
    if errors:
        print("\n".join(errors))
        sys.exit(f"{len(errors)} помилок")
    print(f"OK: {len(rows)} тверджень валідні")


def cmd_stats(path):
    rows = read_jsonl(path)
    print(f"Тверджень: {len(rows)}; документів: {len({r['doc_id'] for r in rows})}")
    print("За відношеннями:", dict(Counter(r["relation"] for r in rows).most_common()))
    print("За документами:", dict(sorted(Counter(r["doc_id"] for r in rows).items())))
    print("Модальність:", dict(Counter(r["modality"] for r in rows)))


def cmd_review(path, doc=None):
    for r in read_jsonl(path):
        if doc and r["doc_id"] != doc:
            continue
        text = read_doc(r["doc_id"])
        ev = r["evidence"]
        marks = []
        for tag, m in (("[[", r["subject"]), ("{{", r["object"])):
            if not m.get("implicit_topic"):
                marks.append((m["start"], m["end"], tag, "]]" if tag == "[[" else "}}"))
        s = text[ev["start"]:ev["end"]]
        for st, en, o, c in sorted(marks, reverse=True):
            s = s[:en - ev["start"]] + c + s[en - ev["start"]:]
            s = s[:st - ev["start"]] + o + s[st - ev["start"]:]
        sub = "(тема)" if r["subject"].get("implicit_topic") else r["subject"]["text"]
        obj = "(тема)" if r["object"].get("implicit_topic") else r["object"]["text"]
        print(f"{r['claim_id']}  {sub} --{r['relation']}--> {obj}  {r.get('qualifiers', '')}")
        print(f"    {s}\n")


def ent_key(e):
    """Ключ сутності без префікса типу; 'of'/'the' ігноруються; злиття canonical з data/canonical_merge.csv (from,to)."""
    slug_ = e["canonical"].split(":", 1)[1]
    slug_ = "_".join(t for t in slug_.split("_") if t not in ("of", "the"))
    return ALIASES.get(slug_, slug_)


ALIASES = {}
_al = ROOT / "data" / "canonical_merge.csv"
if _al.exists():
    import csv
    for row in csv.reader(_al.open(encoding="utf-8")):
        if len(row) >= 2 and not row[0].startswith("#"):
            ALIASES[row[0].split(":", 1)[-1]] = row[1].split(":", 1)[-1]


def cmd_agree(f1, f2):
    from collections import defaultdict
    a, b = read_jsonl(f1), read_jsonl(f2)
    docs = {r["doc_id"] for r in b}
    a = [r for r in a if r["doc_id"] in docs]
    def index(rows):
        d = defaultdict(list)
        for r in rows:
            d[(r["doc_id"], ent_key(r["subject"]), ent_key(r["object"]))].append(r)
        return d
    ia, ib = index(a), index(b)
    both, only_a, only_b = set(ia) & set(ib), set(ia) - set(ib), set(ib) - set(ia)
    p, r_ = len(both) / max(len(ia), 1), len(both) / max(len(ib), 1)
    print(f"Документи: {sorted(docs)}; тверджень A1={len(ia)}, A2={len(ib)}, збіглося пар={len(both)}")
    print(f"Узгодженість добування: F1={2 * len(both) / (len(ia) + len(ib)):.3f}, Jaccard={len(both) / len(set(ia) | set(ib)):.3f}")
    items = [(ia[k][0]["relation"], ib[k][0]["relation"]) for k in both]
    items += [(ia[k][0]["relation"], "NONE") for k in only_a] + [("NONE", ib[k][0]["relation"]) for k in only_b]
    n = len(items)
    po = sum(x == y for x, y in items) / n
    cats = {c for pair in items for c in pair}
    pe = sum((sum(x == c for x, _ in items) / n) * (sum(y == c for _, y in items) / n) for c in cats)
    kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
    print(f"Cohen κ (відношення; NONE = пропущено) на {n} елементах: po={po:.3f}, pe={pe:.3f}, κ={kappa:.3f}")
    same_rel = sum(x == y for x, y in items[:len(both)])
    print(f"Збіг типу відношення у спільних парах: {same_rel}/{len(both)}")
    tdiff = [(k, ia[k][0][s]["type"], ib[k][0][s]["type"]) for k in both for s in ("subject", "object")
             if ia[k][0][s]["type"] != ib[k][0][s]["type"]]
    print("Розбіжності типу сутності:", tdiff or "—")
    print("Лише A1:", sorted(only_a)); print("Лише A2:", sorted(only_b))


def cmd_split(src, dst, force_dev=""):
    import random
    rows = read_jsonl(src)
    dev_forced = {d for d in force_dev.split(",") if d}
    by_doc = defaultdict_list(rows)
    docs = sorted(by_doc)
    free = [d for d in docs if d not in dev_forced]
    total = Counter(r["relation"] for r in rows)
    target = 0.3 * len(rows)
    rng, best = random.Random(SEED), None
    for _ in range(20000):
        k = rng.randint(5, max(5, len(free) // 2))
        test = set(rng.sample(free, k))
        n = sum(len(by_doc[d]) for d in test)
        if not (0.25 * len(rows) <= n <= 0.35 * len(rows)):
            continue
        c = Counter(r["relation"] for d in test for r in by_doc[d])
        score = sum(abs(c[rel] - 0.3 * total[rel]) for rel in total) + abs(n - target)
        score += 10 * sum(1 for rel in total if total[rel] >= 2 and c[rel] == 0)   # кожен тип відношення має бути в test
        if best is None or score < best[0]:
            best = (score, sorted(test))
    test = best[1]
    dev = [d for d in docs if d not in test]
    json.dump({"seed": SEED, "dev": dev, "test": test}, open(dst, "w"), indent=2)
    for name, ds in (("dev", dev), ("test", test)):
        rs = [r for d in ds for r in by_doc[d]]
        print(f"{name}: {len(ds)} док., {len(rs)} тверджень, {dict(Counter(r['relation'] for r in rs))}")


def _dkey(r):
    """Ключ для diff: документ + текст мітки (або canonical для пропущеної теми), щоб зміна типу не виглядала як видалення."""
    m = lambda e: e["text"] if "text" in e else ent_key(e)
    return (r["doc_id"], m(r["subject"]), m(r["object"]))


def _sig(r):
    return (r["relation"], r["subject"]["type"], r["object"]["type"], json.dumps(r.get("qualifiers", {}), sort_keys=True),
            r["modality"], r["evidence"]["text"])


def cmd_diff(old, new):
    o, n = {}, {}
    for r in read_jsonl(old):
        o.setdefault(_dkey(r), []).append(r)
    for r in read_jsonl(new):
        n.setdefault(_dkey(r), []).append(r)
    removed = sorted(set(o) - set(n))
    added = sorted(set(n) - set(o))
    changed = sorted(k for k in set(o) & set(n) if sorted(map(_sig, o[k])) != sorted(map(_sig, n[k])))
    print(f"Було: {sum(map(len, o.values()))}; стало: {sum(map(len, n.values()))}")
    print(f"Видалено: {len(removed)}; додано: {len(added)}; змінено: {len(changed)}")
    for title, ks, src in (("Видалено", removed, o), ("Додано", added, n), ("Змінено", changed, n)):
        for k in ks:
            r = src[k][0]
            print(f"  {title}: {r.get('claim_id', '?')} {k[1]} {r['relation']} {k[2]}")
    for k in changed:
        a, b = o[k][0], n[k][0]
        what = [f for f, x, y in zip(("relation", "subj.type", "obj.type", "qualifiers", "modality", "evidence"), _sig(a), _sig(b)) if x != y]
        print(f"  Змінено {k[0]} {k[1]}->{k[2]}: {', '.join(what)}")


def _fmt_ent(e):
    return "(тема документа)" if e.get("implicit_topic") else e["text"]


def cmd_claims(*argv):
    import csv
    flags = {x for x in argv if x.startswith("--")}
    pos = [x for x in argv if not x.startswith("--")]
    gold, out = pos[0], pos[1]
    rejected = read_jsonl(pos[2]) if len(pos) > 2 else []
    src = {r["doc_id"]: r for r in csv.DictReader((ROOT / "data" / "sources.csv").open(encoding="utf-8"))}
    status = "verified" if "--verified" in flags else "pending"

    def row(r, st, comment):
        q = r.get("qualifiers")
        stmt = f"{_fmt_ent(r['subject'])} {r['relation']} {_fmt_ent(r['object'])}" + (f" {json.dumps(q, ensure_ascii=False)}" if q else "")
        s = src[r["doc_id"]]
        ev = r["evidence"]
        place = f"[{ev['start']}:{ev['end']}]" if "start" in ev else ""
        return [r.get("claim_id", ""), stmt, "факт", f"{s['title']} (Wikipedia, rev {s['revid']}) {s['url']} {place}".strip(),
                "V2", st, comment]
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "твердження", "тип", "джерело", "рівень_верифікації", "статус", "коментар"])
        for r in read_jsonl(gold):
            note = f"розмітка: {r.get('annotator', '?')}; цитата: «{r['evidence']['text'][:120]}»"
            w.writerow(row(r, status, note))
        for r in rejected:
            w.writerow(row(r, "rejected", r.get("reject_reason", "")))
    print(f"Записано {len(read_jsonl(gold))} + {len(rejected)} відхилених у {out}; статус основних: {status}")


def cmd_score(*argv):
    pos = [x for x in argv if not x.startswith("--")]
    pred_f, gold_f, split = pos[0], pos[1], pos[2]
    if split == "test" and "--final" not in argv:
        sys.exit("test не використовується для налаштування (потрібен --final у Результаті 4).")
    docs = set(json.loads((ROOT / "data" / "split.json").read_text(encoding="utf-8"))[split])
    key = lambda r: (r["doc_id"], ent_key(r["subject"]), r["relation"], ent_key(r["object"]))
    G = {key(r): r for r in read_jsonl(gold_f) if r["doc_id"] in docs}
    P = {key(r): r for r in read_jsonl(pred_f) if r["doc_id"] in docs}
    def prf(g, p):
        tp = len(set(g) & set(p))
        pr, rc = tp / len(p) if p else 0.0, tp / len(g) if g else 0.0
        return tp, pr, rc, (2 * pr * rc / (pr + rc) if pr + rc else 0.0)
    tp, pr, rc, f1 = prf(G, P)
    print(f"[{split}] gold={len(G)} pred={len(P)} TP={tp}  P={pr:.3f} R={rc:.3f} F1={f1:.3f}")
    print(f"{'відношення':<18}{'gold':>5}{'pred':>5}{'TP':>5}{'P':>7}{'R':>7}{'F1':>7}")
    for rel in sorted({k[2] for k in G} | {k[2] for k in P}):
        g_ = {k: v for k, v in G.items() if k[2] == rel}
        p_ = {k: v for k, v in P.items() if k[2] == rel}
        t_, a, b, c = prf(g_, p_)
        print(f"{rel:<18}{len(g_):>5}{len(p_):>5}{t_:>5}{a:>7.2f}{b:>7.2f}{c:>7.2f}")
    if "--errors" in argv:
        for title, ks in (("FP (зайві)", sorted(set(P) - set(G))), ("FN (пропущені)", sorted(set(G) - set(P)))):
            print(f"\n{title}: {len(ks)}")
            for k in ks:
                print("  ", k[0], k[1], k[2], k[3])


def defaultdict_list(rows):
    d = {}
    for r in rows:
        d.setdefault(r["doc_id"], []).append(r)
    return d


SEED = 42

if __name__ == "__main__":
    c, a = (sys.argv[1] if len(sys.argv) > 1 else ""), sys.argv[2:]
    {"fill": lambda: cmd_fill(*a), "validate": lambda: cmd_validate(*a),
     "stats": lambda: cmd_stats(*a), "review": lambda: cmd_review(*a),
     "agree": lambda: cmd_agree(*a), "split": lambda: cmd_split(*a),
     "diff": lambda: cmd_diff(*a), "claims": lambda: cmd_claims(*a),
     "score": lambda: cmd_score(*a)}.get(c, lambda: print(__doc__))()