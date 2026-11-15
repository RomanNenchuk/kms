"""Пояснення рекомендацій зі шляху графа + автоперевірка (Результат 3).

Принцип: пояснення будується з ШЛЯХУ (reco/graph_reco.py: path()). LLM (Gemini) лише перефразовує готовий шаблонний текст
і не має права додавати сутності. Автоперевірка (Explainer.check) відхиляє пояснення, у яких:
  * у лапках «…» є назва, якої немає в шляху (вигадана або чужа сутність);
  * без лапок трапляється назва будь-якої іншої відомої сутності Hub (документ, тема, роль, авіакомпанія, ризик, рейс);
  * з'явилися числа, яких немає в шляху;
  * немає назви цільового документа.
Якщо перефразування не пройшло перевірку — використовується шаблонний текст (fallback).
CLI: python -m reco.explain --examples | --eval | --llm [--n 60]"""
from __future__ import annotations
import argparse, datetime as dt, json, os, random, re, sys, time, unicodedata
from . import config as C
from .data import load, graph_rows
from .labels import TOPIC_UA, ROLE_UA

PROMPT_VERSION = "explain_v1"
MIN_INTERVAL_S = 4.5          # безкоштовний рівень Gemini: 15 запитів/хв
_ZW = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), "")


def norm(s: str) -> str:
    """Типографська нормалізація перед звіркою назв: NFKC (нерозривні пробіли -> звичайні), прибрати символи нульової
    ширини, уніфікувати апострофи/лапки-«ялинки» не чіпаємо, звести пробіли. Це НЕ послаблює перевірку сутностей."""
    s = unicodedata.normalize("NFKC", s).translate(_ZW)
    s = s.replace("\u2019", "'").replace("\u02bc", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", s).strip()


def call_with_retry(fn, attempts=6, sleep=time.sleep):
    """Повтор при 429/503 з експоненційною паузою (5, 10, 20, 40, 60 с)."""
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            if i == attempts - 1 or not any(x in str(e) for x in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")):
                raise
            sleep(min(5 * 2 ** i, 60))
SYSTEM = ("Ти редактор коротких пояснень рекомендацій. Тобі дають готове пояснення і перелік дозволених сутностей. "
          "Перефразуй пояснення природною українською в 1–2 речення. Правила: використовуй ЛИШЕ дозволені сутності; "
          "назви сутностей беруть у лапки «…» і не змінюються, не перекладаються, не відмінюються; "
          "не додавай нових назв, чисел, причин і фактів. Відповідай лише текстом пояснення.")


class Explainer:
    def __init__(self, ds):
        self.ds = ds
        self.airlines = {r["code"]: r["name"] for r in graph_rows("airlines.csv")}
        self.risks = {r["riskId"]: r["name"] for r in graph_rows("risks.csv")}
        self.flights = {r["flightId"] for r in graph_rows("flights.csv")}
        # Всесвіт сутностей: поверхнева форма -> (тип, id). Довші форми шукаються першими.
        U = {}
        for d, it in ds.items.items(): U[it["title"]] = ("Doc", d)
        for t, s in TOPIC_UA.items(): U[s] = ("Topic", t)
        for r, s in ROLE_UA.items(): U[s] = ("Role", r)
        for a, s in self.airlines.items(): U[s] = ("Airline", a)
        for r, s in self.risks.items(): U[s] = ("Risk", r)
        for f in self.flights: U[f] = ("Flight", f)
        self.universe = U
        self._order = sorted(U, key=len, reverse=True)

    # ---- сутності шляху
    def surface(self, typ, val):
        return {"Doc": lambda v: self.ds.items[v]["title"], "Topic": lambda v: TOPIC_UA[v], "Role": lambda v: ROLE_UA[v],
                "Airline": lambda v: self.airlines[v], "Flight": lambda v: v, "Risk": lambda v: self.risks[v]}[typ](val)

    @staticmethod
    def _parse(node: str):
        typ, val = node.split(":", 1)
        return typ, val.split(" (")[0]

    def path_entities(self, path, doc_id):
        """Дозволені сутності: [(тип, id, поверхнева форма)] + дозволені числа."""
        ents = {("Doc", doc_id)}
        nums = set()
        if path.get("steps"):
            for a, rel, b in path["steps"]:
                for n in (a, b):
                    t, v = self._parse(n)
                    if t != "User": ents.add((t, v))
        if path.get("similar_to"):
            ents.add(("Doc", path["similar_to"])); nums.add(f"{path['cosine']:.2f}")
        return [(t, v, self.surface(t, v)) for t, v in sorted(ents)], nums

    # ---- шаблонне пояснення (детерміноване)
    def template(self, path, doc_id):
        q = lambda t, v: f"«{self.surface(t, v)}»"
        doc, comp = q("Doc", doc_id), path["component"]
        if comp == "embed":
            return (f"Рекомендовано {doc}, бо за змістом документ близький до {q('Doc', path['similar_to'])} з вашої історії "
                    f"(косинусна подібність {path['cosine']:.2f}).")
        st = {self._parse(a)[0] + "|" + rel: (a, b) for a, rel, b in path["steps"]}
        topic = q("Topic", path["topic"])
        if comp == "role":
            role = self._parse(st["User|HAS_ROLE"][1])[1]
            return f"Рекомендовано {doc}: ваша роль {q('Role', role)} пов'язана з темою {topic}, якій присвячено цей документ."
        if comp == "exposure":
            al = self._parse(st["User|WORKS_AT"][1])[1]; fl = self._parse(st["Airline|OPERATED_BY^-1"][1])[1]
            rk = self._parse(st["Flight|AFFECTED_BY"][1])[1]
            return (f"Рекомендовано {doc}: рейси авіакомпанії {q('Airline', al)} (наприклад, {q('Flight', fl)}) зазнали ризику "
                    f"{q('Risk', rk)}, а тема {topic}, якій присвячено документ, стосується таких ризиків.")
        src = self._parse(st["User|OPENED"][1])[1]
        return f"Рекомендовано {doc}: ви відкривали {q('Doc', src)} на тему {topic}, якій присвячено і цей документ."

    # ---- автоперевірка
    def check(self, text, path, doc_id):
        ents, nums = self.path_entities(path, doc_id)
        text = norm(text)
        allowed = {norm(s) for _, _, s in ents}
        quoted = re.findall(r"«([^»]+)»", text)
        unknown_quoted = [s for s in quoted if s not in allowed]
        rest, found = text, set()
        for s in self._order:                      # маскуємо найдовші збіги першими
            s = norm(s)
            if s in rest:
                found.add(s); rest = rest.replace(s, " ")
        foreign = sorted(s for s in found if s not in allowed)
        numbers = [n for n in re.findall(r"\d+(?:\.\d+)?", rest) if n not in nums]
        missing = [] if norm(self.ds.items[doc_id]["title"]) in text else ["target_doc"]
        ok = not (unknown_quoted or foreign or numbers or missing)
        return {"ok": ok, "unknown_quoted": unknown_quoted, "foreign": foreign, "foreign_numbers": numbers, "missing": missing}

    def explain(self, path, doc_id, paraphraser=None):
        """Повертає {"text", "source": template|llm|template_fallback, "check", "template"}."""
        base = self.template(path, doc_id)
        if paraphraser is None:
            return {"text": base, "source": "template", "check": self.check(base, path, doc_id), "template": base}
        raw = paraphraser(base, self.path_entities(path, doc_id)[0])
        chk = self.check(raw, path, doc_id)
        return {"text": raw if chk["ok"] else base, "source": "llm" if chk["ok"] else "template_fallback",
                "check": chk, "template": base, "raw": raw}

    def mutate(self, text, path, doc_id, rng):
        """Негативний тест перевірки: підміняємо дозволену назву на чужу (як це зробила б галюцинація)."""
        ents, _ = self.path_entities(path, doc_id)
        allowed = {s for _, _, s in ents}
        foreign = [s for s in self.universe if s not in allowed and not re.fullmatch(r"[A-Z]{2}\d+-\d+", s)]
        victim = rng.choice([s for s in allowed if s in text and s != self.ds.items[doc_id]["title"]] or [self.ds.items[doc_id]["title"]])
        return text.replace(victim, rng.choice(sorted(foreign)), 1)


# ---- LLM (Gemini) як перефразовувач; усі виклики журналюються в llm_log/explain_calls.jsonl
class GeminiParaphraser:
    def __init__(self, model=None, temperature=0.0, seed=42, log=C.ROOT / "llm_log" / "explain_calls.jsonl"):
        from google import genai
        from google.genai import types
        try:
            from dotenv import load_dotenv; load_dotenv(C.ROOT / ".env")
        except ImportError:
            pass
        self.model = model or os.environ.get("GEMINI_MODEL")
        if not self.model or not os.environ.get("GEMINI_API_KEY"):
            raise RuntimeError("Задайте GEMINI_API_KEY і GEMINI_MODEL у .env")
        self.types, self.client, self.log = types, genai.Client(), log
        self.params = {"temperature": temperature, "seed": seed}
        self._last, self.cache, self.calls = 0.0, {}, 0
        if self.log.exists():                                  # кеш: ті самі (модель, параметри, підказка, вхід) не викликаємо повторно
            for line in self.log.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                self.cache[self._key(r["model"], r["params"], r["prompt_version"], r["input"])] = r["raw_output"]

    @staticmethod
    def _key(model, params, version, inp):
        return json.dumps([model, params, version, inp], ensure_ascii=False, sort_keys=True)

    def __call__(self, base, ents):
        t = self.types
        inp = {"пояснення": base, "дозволені_сутності": [s for _, _, s in ents]}
        key = self._key(self.model, self.params, PROMPT_VERSION, inp)
        if key in self.cache:
            return self.cache[key]
        prompt = json.dumps(inp, ensure_ascii=False)
        wait = MIN_INTERVAL_S - (time.time() - self._last)
        if wait > 0: time.sleep(wait)
        r = call_with_retry(lambda: self.client.models.generate_content(model=self.model, contents=prompt, config=t.GenerateContentConfig(
            system_instruction=SYSTEM, **self.params)))
        self._last = time.time(); self.calls += 1
        out = (r.text or "").strip(); self.cache[key] = out
        print(f"  [Gemini] виклик {self.calls}", file=sys.stderr, flush=True)
        self.log.parent.mkdir(exist_ok=True)
        with open(self.log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": dt.datetime.now().isoformat(timespec="seconds"), "model": self.model, "params": self.params,
                                "prompt_version": PROMPT_VERSION, "input": json.loads(prompt), "raw_output": out}, ensure_ascii=False) + "\n")
        return out


def collect(rec, ex, users, k=5, method="hybrid"):
    """Усі (користувач, документ, шлях) з топ-k; вимагає гібрид/граф (шлях) або embed."""
    out = []
    for u in users:
        for it in rec.recommend(u, k, method, as_of=rec.ds.end[:10])["items"]:
            if it.get("path"):
                out.append((u, it["doc_id"], it["path"]))
    return out


def pick_examples(rec, ex, users, n=5):
    seen, picks = set(), []
    for method in ("hybrid", "embed"):
        for u, d, p in collect(rec, ex, users, 5, method):
            key = (p["component"])
            if key not in seen:
                seen.add(key); picks.append((u, d, p))
    for u, d, p in collect(rec, ex, users[10:], 5, "hybrid"):
        if len(picks) >= n: break
        picks.append((u, d, p))
    return picks[:n]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--examples", action="store_true"); ap.add_argument("--eval", action="store_true")
    ap.add_argument("--llm", action="store_true"); ap.add_argument("--n", type=int, default=60); a = ap.parse_args()
    from .recommender import Recommender
    rec = Recommender(); ds = rec.ds; ex = Explainer(ds); users = sorted(ds.split["warm_eval_users"])
    para = GeminiParaphraser() if a.llm else None
    (C.ROOT / "reports").mkdir(exist_ok=True)
    if a.examples or a.llm:
        lines = ["# Приклади пояснень (5 рекомендацій)", "", f"Джерело: {'Gemini (перефразування) + автоперевірка' if para else 'шаблон зі шляху'}. Згенеровано `python -m reco.explain {'--llm' if para else '--examples'}`.", ""]
        for i, (u, d, p) in enumerate(pick_examples(rec, ex, users), 1):
            e = ex.explain(p, d, para)
            path = " → ".join([p["steps"][0][0]] + [s[2] for s in p["steps"]]) if p.get("steps") else f"embed: {p['similar_to']} ~ {d}"
            lines += [f"## Приклад {i}: {u} → {ds.items[d]['title']}", f"- Компонента шляху: `{p['component']}`", f"- Шлях: `{path}`",
                      f"- Пояснення ({e['source']}): {e['text']}", f"- Автоперевірка: {'пройдена' if e['check']['ok'] else 'НЕ пройдена'} {json.dumps(e['check'], ensure_ascii=False) if not e['check']['ok'] else ''}"]
            if para: lines.append(f"- Сирий вихід LLM: {e.get('raw')}")
            lines.append("")
        (C.ROOT / "docs" / ("explain_examples_llm.md" if para else "explain_examples.md")).write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
    if a.eval:
        items = collect(rec, ex, users, 5, "hybrid") + collect(rec, ex, users, 5, "embed")
        ok = sum(ex.check(ex.template(p, d), p, d)["ok"] for _, d, p in items)
        rng = random.Random(42); caught = tot = 0
        for _, d, p in items:
            m = ex.mutate(ex.template(p, d), p, d, rng); tot += 1; caught += not ex.check(m, p, d)["ok"]
        res = {"n_explanations": len(items), "template_correct": ok, "template_correct_share": ok / len(items),
               "mutation_tests": tot, "mutations_detected": caught, "detection_rate": caught / tot}
        (C.ROOT / "reports" / "explain_eval.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8"); print(res)
    if a.llm:
        items = collect(rec, ex, users, 5, "hybrid") + collect(rec, ex, users, 5, "embed")
        items = random.Random(42).sample(items, min(a.n, len(items)))
        rows = [ex.explain(p, d, para) for _, d, p in items]
        res = {"model": para.model, "params": para.params, "prompt_version": PROMPT_VERSION, "n": len(rows),
               "llm_passed_check": sum(r["source"] == "llm" for r in rows),
               "llm_passed_share": sum(r["source"] == "llm" for r in rows) / len(rows),
               "fallbacks": sum(r["source"] == "template_fallback" for r in rows),
               "violations": [r["check"] for r in rows if not r["check"]["ok"]]}
        (C.ROOT / "reports" / "explain_llm.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8"); print(res)


if __name__ == "__main__":
    main()
