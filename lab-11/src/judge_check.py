"""Перевірка чутливості LLM-судді (Результат 4): чи ставить він менше за 1.0, коли у правильній відповіді навмисно є помилка.

Беремо 4 відповіді, які суддя вже оцінив у 1.0:
  - 2 з числом: змінюємо число на інше (+7) -> твердження суперечить/не підтверджується джерелом;
  - 2 без змін фактів: дописуємо вигадане речення про рік (якого немає в джерелах) з реальним [id].
Кожну спотворену відповідь суддя оцінює окремим викликом, у тому самому форматі, що й в основному прогоні (4 виклики).
Запуск:  python -m src.judge_check [--sleep 12.5]        Результат: eval/judge_sensitivity.json, docs/judge_sensitivity.md
"""
import os, re, json, sys, time
from .config import EVAL, ROOT
from .rag_eval import load_tests, load_results, judge_prompt, parse_judge, JUDGE_SYSTEM, QuotaExhausted

OUT, MD = EVAL / "judge_sensitivity.json", ROOT / "docs" / "judge_sensitivity.md"


def corrupt_number(ans):
    masked = re.sub(r"\[[^\]]*\]", lambda m: " " * len(m.group()), ans)      # цифри всередині [id] не чіпаємо
    m = re.search(r"\b\d{1,4}\b", masked)
    if not m:
        return None
    old, new = m.group(), str(int(m.group()) + 7)
    return ans[:m.start()] + new + ans[m.end():], f"{old} -> {new}", new


def fabricate(ans, ctx, cited):
    blob = " ".join(ctx.values()) + " " + ans
    year = next((y for y in ("1987", "1993", "2004", "1961") if y not in blob), None)
    if year is None or not cited:
        return None
    return ans.rstrip() + f" It was first formally introduced in {year} [{cited[0]}].", f"дописано «introduced in {year}»", year


def pick(results):
    """Детермінований вибір: перші 2 відповіді з числом + перші 2 інші відповіді для вигаданого речення."""
    ok = [r for rid, r in sorted(results.items()) if not r["abstained"] and r.get("judge") and r["judge"]["faithfulness"] == 1.0
          and r["citations"]["cited"] and rid.startswith("t") and int(rid[1:]) <= 18]            # лише питання з відповіддю
    items, used = [], set()
    for r in ok:
        c = corrupt_number(r["answer"])
        if c and len([i for i in items if i["kind"] == "number"]) < 2:
            items.append({"id": r["id"], "kind": "number", "answer": c[0], "change": c[1], "marker": c[2]}); used.add(r["id"])
    for r in ok:
        if r["id"] in used:
            continue
        f = fabricate(r["answer"], r["contexts"], r["citations"]["cited"])
        if f and len([i for i in items if i["kind"] == "fabricated"]) < 2:
            items.append({"id": r["id"], "kind": "fabricated", "answer": f[0], "change": f[1], "marker": f[2]}); used.add(r["id"])
    return items


def make_call(jm):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    cfg = types.GenerateContentConfig(system_instruction=JUDGE_SYSTEM, temperature=0, response_mime_type="application/json")

    def call(prompt):
        for attempt in range(6):
            try:
                return client.models.generate_content(model=jm, contents=prompt, config=cfg).text
            except Exception as e:
                msg = str(e)
                if attempt < 5 and any(x in msg for x in ("429", "500", "503", "UNAVAILABLE", "RESOURCE_EXHAUSTED")):
                    m = re.search(r"retry in ([\d.]+)s", msg)
                    wait = float(m.group(1)) + 2 if m else 2 ** min(attempt, 5) * 2
                    if wait > 120:
                        raise QuotaExhausted(f"добовий ліміт вичерпано; чекати ~{wait / 3600:.1f} год")
                    time.sleep(wait)
                    continue
                raise
    return call


def run(sleep=12.5, call=None):
    jm, gen = os.environ.get("JUDGE_MODEL"), os.environ.get("GEMINI_MODEL")
    if not jm or jm == gen:
        sys.exit("JUDGE_MODEL має бути заданий і відрізнятись від GEMINI_MODEL.")
    call = call or make_call(jm)
    tests = {t["id"]: t for t in load_tests()}
    results = load_results()
    done = {(r["id"], r["kind"]): r for r in (json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else [])}
    for it in pick(results):
        if (it["id"], it["kind"]) in done:
            continue
        try:
            raw = call(judge_prompt(tests[it["id"]]["question"], results[it["id"]]["contexts"], it["answer"]))
            j = parse_judge(raw)
        except QuotaExhausted as e:
            print(f"Зупинено: {e}. Збережене лишається; повтори пізніше.")
            break
        flagged = [c["claim"] for c in j["claims"] if c.get("verdict") != "supported" and it["marker"] in c["claim"]]
        done[(it["id"], it["kind"])] = {**{k: it[k] for k in ("id", "kind", "change", "answer")}, "faithfulness": j["faithfulness"],
                                        "detected": j["faithfulness"] is not None and j["faithfulness"] < 1.0, "flagged_claims": flagged, "judge_model": jm}
        OUT.write_text(json.dumps(list(done.values()), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{it['id']} {it['kind']:<10} {it['change']:<32} faithfulness={j['faithfulness']} flagged={len(flagged)}")
        time.sleep(sleep)
    write_md(list(done.values()))


def write_md(rows):
    if not rows:
        return
    det = sum(r["detected"] for r in rows)
    line = "\n".join(f"| {r['id']} | {r['kind']} | {r['change']} | {r['faithfulness']} | {'так' if r['detected'] else 'НІ'} | "
                     f"{'так' if r['flagged_claims'] else 'ні'} |" for r in rows)
    MD.write_text(f"""# Чутливість LLM-судді (ЛР 11, Результат 4)

Перевірка: у відповідях, які суддя оцінив у 1.0, навмисно вносимо помилку й оцінюємо знову (той самий промпт і модель `{rows[0]['judge_model']}`).
Спотворення: `number` — число змінено на інше; `fabricated` — дописано вигадане речення про рік, якого немає в джерелах.

| тест | тип | зміна | faithfulness | помилку виявлено (<1.0) | саме спотворене твердження позначено |
|---|---|---|---|---|---|
{line}

Виявлено {det} із {len(rows)}. {'Суддя реагує на обидва типи спотворень.' if det == len(rows) else 'Суддя пропускає частину помилок: його оцінки faithfulness завищені, це треба врахувати при інтерпретації метрики.'}
Обмеження: 4 штучні спотворення двох простих типів; вони показують, що суддя здатен ставити менше за 1.0, але не гарантують, що він знаходить тонші помилки.
""", encoding="utf-8")
    print(f"Збережено {MD}; виявлено {det}/{len(rows)}")


if __name__ == "__main__":
    run(float(sys.argv[sys.argv.index("--sleep") + 1]) if "--sleep" in sys.argv else 12.5)
