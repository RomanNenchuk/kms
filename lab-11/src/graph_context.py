"""Результат 2: підграф із графа знань у контексті RAG.

  запит -> entity linking (назва / синонім / код) -> вузли-«насіння»
        -> витяг підграфа (1-2 кроки, ліміти на ребра) -> лінеаризація з ID вузлів
        -> extra_sources для RAG.ask()  (цитується як [graph:<id>])

Бекенди: Neo4j (основний) і CSV (резерв / офлайн-перевірка; ті самі дані, що load_graph.py).
Пасажири (Passenger, HAS_PASSENGER) свідомо виключені: це персональні дані, у зовнішню LLM вони не йдуть.

Запуск:
  python -m src.graph_context "Which flights are affected by Fog at Lviv?"   # лише лінкінг + підграф, без LLM
  python -m src.graph_context --compare [--sleep 2] [--limit N]              # експеримент «текст» vs «текст+підграф»
  python -m src.graph_context --show h07 g03                                 # збережені відповіді
  python -m src.graph_context --report                                       # перерахувати оцінки й звіт без LLM
"""
import csv, os, re, sys, json, time, collections, pathlib
from .config import ROOT, DATA, EVAL

KEYS = {"Country": "code", "City": "cityId", "Airport": "iata", "Airline": "code", "Aircraft": "registration",
        "Pilot": "pilotId", "Passenger": "passengerId", "Flight": "flightId", "Risk": "riskId", "FlightDelay": "delayId"}
SKIP_LABELS = {"Passenger"}
SKIP_RELS = ["HAS_PASSENGER"]
NODEFILES = {"Country": "countries.csv", "City": "cities.csv", "Airport": "airports.csv", "Airline": "airlines.csv",
             "Aircraft": "aircraft.csv", "Pilot": "pilots.csv", "Flight": "flights.csv", "Risk": "risks.csv",
             "FlightDelay": "delays.csv"}
RELFILES = [("rel_in_country.csv", "IN_COUNTRY", "City", "Country"), ("rel_located_in.csv", "LOCATED_IN", "Airport", "City"),
            ("rel_owned_by.csv", "OWNED_BY", "Aircraft", "Airline"), ("rel_departs_from.csv", "DEPARTS_FROM", "Flight", "Airport"),
            ("rel_arrives_at.csv", "ARRIVES_AT", "Flight", "Airport"), ("rel_operated_by.csv", "OPERATED_BY", "Flight", "Airline"),
            ("rel_uses_aircraft.csv", "USES_AIRCRAFT", "Flight", "Aircraft"), ("rel_has_pilot.csv", "HAS_PILOT", "Flight", "Pilot"),
            ("rel_next_leg.csv", "NEXT_LEG", "Flight", "Flight"), ("rel_at_airport.csv", "AT_AIRPORT", "Risk", "Airport"),
            ("rel_affected_by.csv", "AFFECTED_BY", "Flight", "Risk"), ("rel_has_delay.csv", "HAS_DELAY", "Flight", "FlightDelay"),
            ("rel_caused_by.csv", "CAUSED_BY", "FlightDelay", "Risk")]

# Українські синоніми (основа слова, бо відмінки): regex -> (мітка, ключ)
UA_SYNONYMS = [(r"льв[іо]в\w*", "City", "lviv"), (r"київ\w*|києв\w*|киє\w*", "City", "kyiv"), (r"харк[іо]в\w*", "City", "kharkiv"),
               (r"одес\w*", "City", "odesa"), (r"дніпр\w*", "City", "dnipro"), (r"варшав\w*", "City", "warsaw"),
               (r"краков\w*|кракув\w*|краків\w*", "City", "krakow"), (r"гданьск\w*", "City", "gdansk"),
               (r"риз[іи]\b|риг[аиу]\b", "City", "riga"), (r"франкфурт\w*", "City", "frankfurt"),
               (r"стамбул\w*", "City", "istanbul"), (r"гельсінк\w*", "City", "helsinki"), (r"берлін\w*", "City", "berlin"),
               (r"україн\w*", "Country", "UA"), (r"польщ\w*|польськ\w*", "Country", "PL"), (r"німеч\w*|німецьк\w*", "Country", "DE")]


def _clean(v):
    return v if isinstance(v, (str, int, float, bool)) else str(v)


# ---------------------------------------------------------------- бекенди
class CsvBackend:
    name = "csv"

    def __init__(self):
        self.props, self.adj = {}, collections.defaultdict(list)
        for label, fn in NODEFILES.items():
            with open(DATA / fn, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    self.props[(label, row[KEYS[label]])] = row
        for fn, typ, sl, el in RELFILES:
            with open(DATA / fn, encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    a, b = (sl, r["startId"]), (el, r["endId"])
                    rp = {"confidence": float(r["confidence"])}
                    if "gapMin" in r:
                        rp["gapMin"] = int(r["gapMin"])
                    self.adj[a].append({"type": typ, "out": True, "other": b, "rp": rp})
                    self.adj[b].append({"type": typ, "out": False, "other": a, "rp": rp})

    def nodes(self):
        return [(l, k, p) for (l, k), p in self.props.items()]

    def node(self, label, key):
        return self.props.get((label, key), {})

    def neighbors(self, label, key):
        return self.adj.get((label, key), [])


class Neo4jBackend:
    name = "neo4j"

    def __init__(self):
        from neo4j import GraphDatabase
        self.drv = GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                                        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "")))
        self.drv.verify_connectivity()
        self._p = {}

    @staticmethod
    def _props(d):
        return {k: (_clean(v)[:16] if k == "scheduledDeparture" else _clean(v)) for k, v in dict(d).items()}

    @staticmethod
    def _label(lbls):
        return next(l for l in lbls if l in KEYS)

    def nodes(self):
        out = []
        with self.drv.session() as s:
            for label, key in KEYS.items():
                if label in SKIP_LABELS:
                    continue
                for rec in s.run(f"MATCH (n:`{label}`) RETURN properties(n) AS p"):
                    p = self._props(rec["p"])
                    self._p[(label, str(p[key]))] = p
                    out.append((label, str(p[key]), p))
        return out

    def node(self, label, key):
        return self._p.get((label, key), {})

    def neighbors(self, label, key):
        q = (f"MATCH (n:`{label}` {{`{KEYS[label]}`: $k}})-[r]-(m) "
             "WHERE NOT type(r) IN $skip AND NOT m:Passenger "
             "RETURN type(r) AS t, startNode(r) = n AS out, labels(m) AS lbls, properties(m) AS mp, properties(r) AS rp")
        res = []
        with self.drv.session() as s:
            for rec in s.run(q, k=key, skip=SKIP_RELS):
                ml = self._label(rec["lbls"])
                mp = self._props(rec["mp"])
                mk = str(mp[KEYS[ml]])
                self._p[(ml, mk)] = mp
                rp = {k: v for k, v in self._props(rec["rp"]).items() if k in ("confidence", "gapMin")}
                res.append({"type": rec["t"], "out": rec["out"], "other": (ml, mk), "rp": rp})
        return res


def get_backend(kind=None):
    kind = kind or os.getenv("GRAPH_BACKEND", "neo4j")
    if kind == "neo4j":
        try:
            return Neo4jBackend()
        except Exception as e:
            print(f"[graph_context] Neo4j недоступний ({type(e).__name__}); використовую CSV-резерв", file=sys.stderr)
    return CsvBackend()


# ---------------------------------------------------------------- відображення вузлів
def node_name(label, p):
    return p.get("name") or p.get("flightNumber") or p.get("model") or ""


def node_attrs(label, p):
    keys = {"Airline": ["homeCountry"], "Aircraft": ["seatCapacity"], "Pilot": ["flightHours"],
            "Flight": ["scheduledDeparture", "kind"], "Risk": ["kind", "level"], "FlightDelay": ["minutes", "propagated"]}
    return ", ".join(f"{k}={p[k]}" for k in keys.get(label, []) if k in p)


def ref(label, key):
    return f"{label}#{key}"


# ---------------------------------------------------------------- entity linking
class EntityLinker:
    """Зв'язує запит із вузлами: точні коди (IATA, ID рейсу, реєстрація, RKxx, Dxxx), назви (без регістру,
    прийменники at/in/of/the необов'язкові), номер рейсу (-> усі рейси з цим номером), укр. основи слів."""

    def __init__(self, nodes):
        self.exact = collections.defaultdict(list)      # токен -> [(label,key)]
        self.names = []                                  # (regex, label, key)
        for label, key, p in nodes:
            if label == "Passenger":
                continue
            if label in ("Airport", "Aircraft", "Risk", "FlightDelay", "Flight"):
                self.exact[key].append((label, key))
            if label == "Flight" and p.get("flightNumber"):
                self.exact[p["flightNumber"]].append((label, key))
            name = p.get("name")
            if name:
                self.names.append((self._pat(name), label, key))
                toks = name.split()
                if label == "Airline" and len(toks) > 1 and len(toks[0]) >= 5:
                    self.names.append((self._pat(toks[0]), label, key))
        for rx, label, key in UA_SYNONYMS:
            self.names.append((re.compile(r"(?<!\w)(?:" + rx + ")", re.I), label, key))
        toks = sorted(self.exact, key=len, reverse=True)
        self.exact_re = re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(t) for t in toks) + r")(?![\w-])")

    @staticmethod
    def _pat(name):
        toks = [t for t in re.findall(r"[\w'-]+", name) if t.lower() not in ("at", "in", "of", "the")]
        inner = r"\W+(?:(?:at|in|of|the)\W+)?".join(re.escape(t) for t in toks)
        return re.compile(r"(?<!\w)" + inner + r"(?!\w)", re.I)

    def link(self, query):
        cands = {}                                       # span -> {nodes, alias}
        for m in self.exact_re.finditer(query):
            cands[m.span()] = {"nodes": list(dict.fromkeys(self.exact[m.group()])), "alias": m.group(), "via": "code"}
        for rx, label, key in self.names:
            for m in rx.finditer(query):
                c = cands.setdefault(m.span(), {"nodes": [], "alias": m.group(), "via": "name"})
                if (label, key) not in c["nodes"]:
                    c["nodes"].append((label, key))
        chosen, taken = [], []
        for span in sorted(cands, key=lambda s: (-(s[1] - s[0]), s[0])):     # найдовший збіг виграє
            if any(span[0] < b and a < span[1] for a, b in taken):
                continue
            taken.append(span)
            chosen.append((span, cands[span]))
        chosen.sort(key=lambda x: x[0][0])
        return [{"alias": c["alias"], "via": c["via"], "nodes": c["nodes"][:3]} for _, c in chosen]


# ---------------------------------------------------------------- підграф
class GraphContext:
    def __init__(self, backend=None, hops=2, per_type=8, per_type_hop2=4, per_node_hop2=10, max_edges=60, max_seeds=4):
        self.b = backend or get_backend()
        self.hops, self.per_type, self.per_type_hop2 = hops, per_type, per_type_hop2
        self.per_node_hop2, self.max_edges, self.max_seeds = per_node_hop2, max_edges, max_seeds
        self.linker = EntityLinker(self.b.nodes())

    def link(self, query):
        return self.linker.link(query)

    def seeds(self, query):
        out = []
        for ent in self.link(query):
            for n in ent["nodes"]:
                if n not in out:
                    out.append(n)
                if n[0] == "City":                       # місто -> його аеропорти (найкорисніший зв'язок для питань про «аеропорти»)
                    for e in self.b.neighbors(*n):
                        if e["type"] == "LOCATED_IN" and not e["out"] and e["other"] not in out:
                            out.append(e["other"])
        return out[:self.max_seeds + 2]

    def _expand(self, seed, budget, seen):
        edges, notes, visited, frontier = [], [], {seed}, [seed]
        for hop in range(1, self.hops + 1):
            nxt = []
            for node in sorted(frontier, key=lambda n: n[0] == "Flight"):   # спершу малі вузли (місто, країна), рейси в кінці
                groups = collections.defaultdict(list)
                for e in self.b.neighbors(*node):
                    groups[(e["type"], e["out"])].append(e)
                cap_t = self.per_type if hop == 1 else self.per_type_hop2
                node_new = 0
                for (t, out), es in sorted(groups.items()):
                    es.sort(key=lambda e: (-e["rp"].get("confidence", 0), e["other"]))
                    new = shown = 0
                    for e in es:
                        a, b = (node, e["other"]) if out else (e["other"], node)
                        eid = (a, t, b)
                        if eid in seen:
                            shown += 1
                            continue
                        if new >= cap_t or len(edges) >= budget or (hop > 1 and node_new >= self.per_node_hop2):
                            break
                        seen.add(eid)
                        edges.append({"a": a, "type": t, "b": b, "rp": e["rp"]})
                        new += 1
                        shown += 1
                        node_new += 1
                        if e["other"] not in visited:
                            visited.add(e["other"])
                            nxt.append(e["other"])
                    if shown < len(es):
                        notes.append({"node": node, "type": t, "out": out, "total": len(es), "shown": shown})
            frontier = nxt
        return edges, notes

    def linearize(self, seed, edges, notes):
        nodes = [seed] + [n for e in edges for n in (e["a"], e["b"]) if n != seed]
        nodes = list(dict.fromkeys(nodes))
        lines = [f"Knowledge-graph facts around {ref(*seed)} (neighbourhood up to {self.hops} hops, {len(edges)} edges). "
                 f"Node ids look like Label#key."]
        lines.append("Nodes:")
        for l, k in nodes:
            p = self.b.node(l, k)
            nm, at = node_name(l, p), node_attrs(l, p)
            lines.append(f"- {ref(l, k)}" + (f' "{nm}"' if nm else "") + (f" ({at})" if at else ""))
        lines.append("Edges:")
        for e in edges:
            extra = ", ".join(f"{k}={v}" for k, v in e["rp"].items())
            lines.append(f"- {ref(*e['a'])} --{e['type']}--> {ref(*e['b'])}" + (f" ({extra})" if extra else ""))
        for n in notes:
            if n["node"] == seed or n["total"] - n["shown"] >= 3:
                d = "outgoing" if n["out"] else "incoming"
                lines.append(f"Note: {ref(*n['node'])} has {n['total']} {d} {n['type']} edges in total; {n['shown']} shown.")
        return "\n".join(lines)

    def context_for(self, query):
        """-> (extra_sources для RAG.ask, info). Порожній список, якщо жодної сутності не знайдено."""
        seeds = self.seeds(query)
        info = {"linked": self.link(query), "seeds": [ref(*s) for s in seeds[:self.max_seeds]], "edges": 0, "chars": 0}
        if not seeds:
            return [], info
        seeds = seeds[:self.max_seeds]
        budget = max(15, self.max_edges // len(seeds))
        seen, sources = set(), []
        for s in seeds:
            edges, notes = self._expand(s, budget, seen)
            text = self.linearize(s, edges, notes)
            p = self.b.node(*s)
            sources.append({"id": f"graph:{s[1]}", "doc_id": None, "kind": "graph",
                            "header": f"Knowledge graph: {ref(*s)} {node_name(s[0], p)}".strip(), "text": text})
            info["edges"] += len(edges)
            info["chars"] += len(text)
        return sources, info


# ---------------------------------------------------------------- експеримент
def _cov(rxs, ans):
    return None if not rxs else sum(bool(re.search(rx, ans, re.I)) for rx in rxs) / len(rxs)


def score(q, res):
    """Гібридне питання має дві частини: текстову (з Вікіпедії) і графову (з графа). Повна відповідь = обидві повні."""
    if q["expect_abstain"]:
        return {"correct": bool(res["abstained"]), "text_cov": None, "graph_cov": None}
    if res["abstained"]:
        return {"correct": False, "text_cov": 0.0 if q["must_text"] else None, "graph_cov": 0.0 if q["must_graph"] else None}
    ans = res["answer"].lower()
    t, g = _cov(q["must_text"], ans), _cov(q["must_graph"], ans)
    return {"correct": all(x == 1.0 for x in (t, g) if x is not None), "text_cov": t, "graph_cov": g}


def run_compare(sleep=2.0, limit=None, backend=None):
    from .rag import RAG
    rag, gc = RAG(), GraphContext(backend)
    qs = [json.loads(l) for l in open(EVAL / "graph_questions.jsonl", encoding="utf-8")][:limit]
    rows = []
    for q in qs:
        gsrc, info = gc.context_for(q["question"])
        for mode in ("text", "text+graph"):
            res = rag.ask(q["question"], extra_sources=gsrc if mode == "text+graph" else None, tag=f"graph_vs_text:{mode}:{q['id']}")
            sc = score(q, res)
            rows.append({"id": q["id"], "type": q["qtype"], "mode": mode, **sc,
                         "graph_cited": any(c.startswith("graph:") for c in res["citations"]["cited"]),
                         "abstained": res["abstained"], "prompt_tokens": res["tokens"]["prompt"], "total_tokens": res["tokens"]["total"],
                         "latency_ms": res["latency_ms"]["total"], "citations_ok": res["citations"]["ok"],
                         "graph_edges": info["edges"] if mode == "text+graph" else 0, "answer": res["answer"]})
            print(f"{q['id']:>4} {mode:<10} correct={sc['correct']!s:<5} text={sc['text_cov']} graph={sc['graph_cov']} tok={res['tokens']['prompt']}")
            time.sleep(sleep)
    out = EVAL / "graph_vs_text_results.jsonl"
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    write_report(qs, rows, ROOT / "docs" / "graph_vs_text.md")
    print(f"\nЗбережено: {out} і docs/graph_vs_text.md")


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else 0.0


def _mark(cov, abstained=False):
    if cov is None:
        return "—"
    return "✅" if cov == 1 else ("❌ (відмова)" if abstained else ("❌" if cov == 0 else f"⚠️ {cov:.0%}"))


def _stats(rows, kind):
    out = {}
    for m in ("text", "text+graph"):
        rs = [r for r in rows if r["mode"] == m and r["type"] == kind]
        n_ok = sum(r["correct"] for r in rs)
        tp = [r["text_cov"] for r in rs if r["text_cov"] is not None]
        gp = [r["graph_cov"] for r in rs if r["graph_cov"] is not None]
        out[m] = {"n": len(rs), "ok": n_ok, "text_ok": sum(x == 1 for x in tp), "text_n": len(tp),
                  "graph_ok": sum(x == 1 for x in gp), "graph_n": len(gp), "tok": _avg([r["prompt_tokens"] for r in rs]),
                  "tok_ok": (sum(r["prompt_tokens"] for r in rs) / n_ok) if n_ok else None, "abst": sum(r["abstained"] for r in rs), "lat": _avg([r["latency_ms"] for r in rs]),
                  "expl": _avg([float(r["graph_cited"]) for r in rs])}
    return out


def write_report(qs, rows, path):
    H, G = _stats(rows, "hybrid"), _stats(rows, "graph_only")
    ht, hg, gt, gg = H["text"], H["text+graph"], G["text"], G["text+graph"]
    fmt = lambda v: f"{v:.0f}" if v is not None else "н/д (0 правильних)"
    by = lambda m, i: next(r for r in rows if r["mode"] == m and r["id"] == i)

    def table(kind, hybrid):
        head = ("| id | питання | текстова частина (текст / +граф) | графова частина (текст / +граф) | повна відповідь (текст / +граф) | prompt-токени |\n|---|---|---|---|---|---|"
                if hybrid else "| id | питання | правильно (текст / +граф) | prompt-токени |\n|---|---|---|---|")
        lines = [head]
        for q in (x for x in qs if x["qtype"] == kind):
            a, b = by("text", q["id"]), by("text+graph", q["id"])
            full = lambda r: "✅" if r["correct"] else ("❌ (відмова)" if r["abstained"] else "❌")
            if hybrid:
                lines.append(f"| {q['id']} | {q['question']} | {_mark(a['text_cov'], a['abstained'])} / {_mark(b['text_cov'], b['abstained'])} | "
                             f"{_mark(a['graph_cov'], a['abstained'])} / {_mark(b['graph_cov'], b['abstained'])} | {full(a)} / {full(b)} | {a['prompt_tokens']} → {b['prompt_tokens']} |")
            else:
                lines.append(f"| {q['id']} | {q['question']} {('— ' + q['note']) if q['note'] else ''} | {full(a)} / {full(b)} | {a['prompt_tokens']} → {b['prompt_tokens']} |")
        return "\n".join(lines)

    md = f"""# Граф vs текст: порівняння режимів RAG (ЛР 11, Результат 2)

_Згенеровано `python -m src.graph_context --compare`; числа з `eval/graph_questions.jsonl` і `eval/graph_vs_text_results.jsonl`._

## 1. Дизайн експерименту
- **«лише текст»**: RAG із Результату 1 (гібридний пошук + reranker, топ-5 батьківських контекстів корпусу).
- **«текст + підграф»**: ті самі 5 контекстів + підграф графа ЛР 9 як додаткові джерела `[graph:<id>]`.
  Entity linking: коди (IATA, ID рейсу, реєстрація, RKxx, Dxxx), назви (прийменники at/in/of/the необов'язкові), номер рейсу, українські основи слів;
  місто розгортається в його аеропорти. Підграф: ≤ 2 кроки, ≤ 8 ребер на тип зв'язку (1-й крок), ≤ 4 (2-й), ≤ 60 ребер на запит.
  Пасажири виключені (персональні дані).
- **Частина A, {ht['n']} гібридних питань**: кожне складається з двох частин — текстової (визначення/правило зі статті Вікіпедії з корпусу) і графової
  (факт про сутність нашої мережі: рейс, аеропорт, літак, пілот, ризик). Текстові еталони перевірені проти корпусу, графові обчислені з CSV
  (`scripts/make_graph_questions_v2.py`). Повна відповідь правильна, лише якщо є обидві частини.
- **Частина B, {gt['n']} графових питань**: технічна перевірка підграфа (ланцюжки, списки, ліміт, відсутній зв'язок, захист ПДн); для питань без відповіді правильна відмова.
- Правильність автоматична (регулярні вирази); відповіді ще треба переглянути вручну.

## 2. Частина A — гібридні питання
{table("hybrid", True)}

## 3. Частина B — перевірка підграфа
{table("graph_only", False)}

## 4. Зведення
| Метрика | лише текст | текст + підграф |
|---|---|---|
| A: повні відповіді | {ht['ok']}/{ht['n']} | {hg['ok']}/{hg['n']} |
| A: текстова частина правильна | {ht['text_ok']}/{ht['text_n']} | {hg['text_ok']}/{hg['text_n']} |
| A: графова частина правильна | {ht['graph_ok']}/{ht['graph_n']} | {hg['graph_ok']}/{hg['graph_n']} |
| A: відповіді з цитатою `[graph:…]` | {ht['expl']:.0%} | {hg['expl']:.0%} |
| B: правильні відповіді | {gt['ok']}/{gt['n']} | {gg['ok']}/{gg['n']} |
| A: середні prompt-токени | {ht['tok']:.0f} | {hg['tok']:.0f} |
| A: prompt-токенів на одну повну відповідь | {fmt(ht['tok_ok'])} | {fmt(hg['tok_ok'])} |
| A: відповідь повністю замінена відмовою (NO_ANSWER) | {ht['abst']}/{ht['n']} | {hg['abst']}/{hg['n']} |
| A: середня затримка, мс | {ht['lat']:.0f} | {hg['lat']:.0f} |

## 5. Висновок (числа)
- Повнота: повні відповіді на гібридні питання {ht['ok']}/{ht['n']} → {hg['ok']}/{hg['n']}; графова частина {ht['graph_ok']}/{ht['graph_n']} → {hg['graph_ok']}/{hg['graph_n']}.
- Текстова частина: {ht['text_ok']}/{ht['text_n']} → {hg['text_ok']}/{hg['text_n']}. Різниця пояснюється поведінкою моделі, а не пошуком: у режимі «лише текст» модель відмовилась від усієї відповіді (NO_ANSWER) у {ht['abst']}/{ht['n']} гібридних питань, хоча правило 3 промпту вимагає відповісти на покриту частину; з підграфом відмов {hg['abst']}/{hg['n']}.
- Вартість: prompt-токени ×{hg['tok'] / max(1, ht['tok']):.2f} ({ht['tok']:.0f} → {hg['tok']:.0f}); на одну повну відповідь {fmt(ht['tok_ok'])} → {fmt(hg['tok_ok'])} (порівняння має зміст, лише коли обидва режими мають правильні відповіді).
- Пояснюваність: {hg['expl']:.0%} відповідей режиму з підграфом цитують вузли графа `[graph:…]`, тобто факт можна перевірити за ID.
- Межі підграфа (частина B): див. питання з приміткою про агрегацію понад ліміт та питання з очікуваною відмовою.

## 6. Обмеження
- Графова частина гібридних питань у режимі «лише текст» недосяжна за побудовою (дані графа є лише в графі), тому приріст графової частини — очікуваний,
  а не відкриття. Змістовні виміри тут: (1) чи зберігається текстова частина при додаванні підграфа, (2) чи вдається об'єднати обидва джерела в одній
  відповіді (напр. h04: 42 хв < 3 год), (3) ціна в токенах і затримці, (4) поведінка на межі (агрегація, відсутній зв'язок, ПДн).
- Питання складені автором під наявні дані; вони не репрезентативні для реальних запитів користувачів. Вибірка мала (10 + 6), відсотки нестабільні.
- Автоматична оцінка за регулярними виразами може пропустити правильну відповідь іншими словами або зарахувати випадковий збіг; перегляньте відповіді вручну.
- Ретрівал для складених питань працює по цілому запиту, тому текстова частина може страждати від змішаного формулювання (причина — пошук, не граф).
"""
    path.parent.mkdir(exist_ok=True)
    path.write_text(md, encoding="utf-8")


# ---------------------------------------------------------------- CLI
def rebuild_report():
    """Перераховує оцінки зі збережених відповідей (після зміни еталонів/регулярок) і перегенеровує docs/graph_vs_text.md. LLM не викликається."""
    qs = [json.loads(l) for l in open(EVAL / "graph_questions.jsonl", encoding="utf-8")]
    qd = {q["id"]: q for q in qs}
    rows = [json.loads(l) for l in open(EVAL / "graph_vs_text_results.jsonl", encoding="utf-8")]
    for r in rows:
        r.update(score(qd[r["id"]], {"abstained": r["abstained"], "answer": r["answer"]}))
    (EVAL / "graph_vs_text_results.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    write_report(qs, rows, ROOT / "docs" / "graph_vs_text.md")
    print("Перераховано і збережено docs/graph_vs_text.md")


def show(ids):
    for l in open(EVAL / "graph_vs_text_results.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if r["id"] in ids:
            print(f"--- {r['id']} [{r['mode']}] correct={r['correct']} abstained={r['abstained']} text={r['text_cov']} graph={r['graph_cov']}\n{r['answer']}\n")


def main():
    a = sys.argv[1:]
    if a and a[0] == "--report":
        return rebuild_report()
    if a and a[0] == "--show":
        return show(set(a[1:]))
    if a and a[0] == "--compare":
        sleep = float(a[a.index("--sleep") + 1]) if "--sleep" in a else 2.0
        limit = int(a[a.index("--limit") + 1]) if "--limit" in a else None
        return run_compare(sleep, limit)
    gc = GraphContext()
    q = " ".join(a)
    print("backend:", gc.b.name)
    print("linked:", json.dumps(gc.link(q), ensure_ascii=False))
    srcs, info = gc.context_for(q)
    print(f"seeds={info['seeds']} edges={info['edges']} chars={info['chars']}\n")
    for s in srcs:
        print(f"=== [{s['id']}] {s['header']}\n{s['text']}\n")


if __name__ == "__main__":
    main()
