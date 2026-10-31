#!/usr/bin/env python3
"""text-to-Cypher з безпекою (ЛР 9, Результат 5).
Конвеєр: питання -> LLM -> валідація (заборонені ключові слова, мітки/зв'язки зі схеми БД, LIMIT) -> виконання
в READ-транзакції -> порівняння з еталоном -> метрики + журнал взаємодії з LLM (llm_log/).

Постачальники:  --provider gemini     (безкоштовний ключ Google AI Studio у GEMINI_API_KEY; типовий)
                --provider anthropic  (необов'язково; ANTHROPIC_API_KEY)
                --provider manual     (Cypher бере з tests/manual_cypher.jsonl: {"id":..,"cypher":..,"model":..})
Запуск:  python t2c/t2c.py --provider gemini      |      python t2c/t2c.py --provider manual
"""
import argparse, datetime as dt, json, os, re, sys, time, urllib.request, urllib.error
from collections import Counter
from neo4j import GraphDatabase, RoutingControl

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PWD = os.getenv("NEO4J_PASSWORD")
MODEL = os.getenv("T2C_MODEL", "claude-sonnet-5-5")          # для --provider anthropic
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")  # для --provider gemini (змініть, якщо модель недоступна у вашому ключі)
PROMPT_VERSION = "schema_prompt.v1"
DEFAULT_LIMIT = 100
FORBIDDEN = re.compile(r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|FOREACH|LOAD\s+CSV|CALL|START|GRANT|DENY|REVOKE|ALTER|RENAME|TERMINATE)\b|apoc\.|dbms\.", re.I)


def read(driver, cypher):
    recs, _, _ = driver.execute_query(cypher, routing_=RoutingControl.READ)  # READ-режим: сервер відхиляє запис
    return [r.data() for r in recs]


def allowed_schema(driver):
    labels = {r["label"] for r in read(driver, "CALL db.labels() YIELD label RETURN label")}
    rels = {r["relationshipType"] for r in read(driver, "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")}
    return labels, rels


def clean(text):
    t = text.strip()
    t = re.sub(r"^```(?:cypher)?\s*|\s*```$", "", t, flags=re.I).strip()
    return t.rstrip(";").strip()


def validate(cypher, labels, rels):
    """Повертає (ok, reason, cypher_with_limit)."""
    if not cypher or cypher.upper() == "REFUSE":
        return False, "refused_by_model", cypher
    if ";" in cypher:
        return False, "multiple_statements", cypher
    no_str = re.sub(r"'[^']*'|\"[^\"]*\"", "''", cypher)  # не шукати ключові слова всередині рядків
    m = FORBIDDEN.search(no_str)
    if m:
        return False, f"forbidden_keyword:{m.group(0).upper()}", cypher
    if not re.search(r"\bRETURN\b", no_str, re.I):
        return False, "no_return", cypher
    for grp in re.findall(r"\(\s*\w*\s*((?::\s*[A-Za-z_]+\s*)+)", no_str):
        for lab in re.findall(r"[A-Za-z_]+", grp):
            if lab not in labels:
                return False, f"unknown_label:{lab}", cypher
    for grp in re.findall(r"\[\s*\w*\s*:\s*([A-Za-z_|:\s]+)", no_str):
        for rt in re.findall(r"[A-Za-z_]+", grp):
            if rt not in rels:
                return False, f"unknown_relationship:{rt}", cypher
    if not re.search(r"\bLIMIT\b", no_str, re.I):
        cypher = f"{cypher}\nLIMIT {DEFAULT_LIMIT}"
    return True, "ok", cypher


def norm_rows(rows):
    """Порівняння без урахування назв стовпців і порядку рядків/стовпців."""
    def v(x):
        return str(round(x, 2)) if isinstance(x, float) else str(x)
    return sorted(tuple(sorted(v(x) for x in r.values())) for r in rows)


def ask_anthropic(question, system, log_params):
    import anthropic
    client = anthropic.Anthropic()  # ключ з ANTHROPIC_API_KEY
    kw = dict(model=MODEL, max_tokens=500, system=system, messages=[{"role": "user", "content": question}])
    try:
        resp = client.messages.create(temperature=0, **kw)
        log_params["temperature"] = 0
    except Exception as e:  # деякі моделі не приймають temperature
        if "temperature" not in str(e).lower():
            raise
        resp = client.messages.create(**kw)
        log_params["temperature"] = "model default (parameter rejected)"
    return "".join(b.text for b in resp.content if b.type == "text")


def ask_gemini(question, system, log_params):
    """Gemini через REST (без SDK). Безкоштовний ключ: https://aistudio.google.com -> Get API key."""
    key = os.getenv("GEMINI_API_KEY") or sys.exit("Задайте GEMINI_API_KEY у середовищі (ключ з Google AI Studio).")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    cfg = {"temperature": 0, "maxOutputTokens": 2000, "seed": 42}  # запас токенів: «thinking» моделі їх теж витрачають
    log_params.update({"temperature": 0, "seed": 42, "max_output_tokens": 2000})
    body = json.dumps({"systemInstruction": {"parts": [{"text": system}]},
                       "contents": [{"role": "user", "parts": [{"text": question}]}],
                       "generationConfig": cfg}).encode("utf-8")
    for attempt in range(5):
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
            cand = (data.get("candidates") or [{}])[0]
            return "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 4:      # ліміт безкоштовного рівня — чекаємо й повторюємо
                time.sleep(15 * (attempt + 1)); continue
            sys.exit(f"Gemini HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}")
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["gemini", "anthropic", "manual"], default="gemini")
    ap.add_argument("--tests", default=os.path.join(ROOT, "tests", "t2c.jsonl"))
    ap.add_argument("--manual", default=os.path.join(ROOT, "tests", "manual_cypher.jsonl"))
    a = ap.parse_args()
    if not PWD:
        sys.exit("Задайте NEO4J_PASSWORD у середовищі (export NEO4J_PASSWORD=...).")
    system = open(os.path.join(ROOT, "t2c", "schema_prompt.txt"), encoding="utf-8").read()
    manual = {}
    if a.provider == "manual":
        manual = {json.loads(l)["id"]: json.loads(l) for l in open(a.manual, encoding="utf-8") if l.strip()}
    tests = [json.loads(l) for l in open(a.tests, encoding="utf-8") if l.strip()]
    os.makedirs(os.path.join(ROOT, "llm_log"), exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = os.path.join(ROOT, "llm_log", f"t2c_{a.provider}_{stamp}.jsonl")
    res_path = os.path.join(ROOT, "tests", f"t2c_results_{a.provider}_{stamp}.jsonl")
    verdicts = []
    with GraphDatabase.driver(URI, auth=(USER, PWD)) as driver, open(log_path, "w", encoding="utf-8") as lf, open(res_path, "w", encoding="utf-8") as rf:
        labels, rels = allowed_schema(driver)
        for t in tests:
            params = {"max_tokens": 500, "seed": "not supported by API"}
            t0 = time.time()
            if a.provider == "gemini":
                raw = ask_gemini(t["question"], system, params); model = GEMINI_MODEL
                time.sleep(7)                       # безкоштовний рівень: обмеження запитів за хвилину
            elif a.provider == "anthropic":
                raw = ask_anthropic(t["question"], system, params); model = MODEL
            else:
                m = manual.get(t["id"], {}); raw = m.get("cypher", ""); model = m.get("model", "manual (external chat LLM)")
            llm_s = time.time() - t0
            cy = clean(raw)
            ok, reason, final = validate(cy, labels, rels)
            verdict, detail, rows_n, exec_s = None, reason, None, None
            if t["compare"] == "expect_reject":
                verdict = "correct" if not ok else "wrong_result"
                detail = reason if not ok else "query_passed_validation_but_should_be_rejected"
            elif not ok:
                verdict = "rejected_by_validator"
            else:
                try:
                    t1 = time.time(); got = read(driver, final); exec_s = time.time() - t1; rows_n = len(got)
                    exp = read(driver, t["gold_cypher"])
                    verdict = "correct" if norm_rows(got) == norm_rows(exp) else "wrong_result"
                    detail = f"rows={len(got)} expected_rows={len(exp)}"
                except Exception as e:
                    verdict, detail = "execution_error", str(e).splitlines()[0][:200]
            verdicts.append(verdict)
            lf.write(json.dumps({"ts": dt.datetime.now().isoformat(timespec="seconds"), "model": model, "provider": a.provider,
                                 "params": params, "prompt_version": PROMPT_VERSION, "id": t["id"], "question": t["question"],
                                 "raw_output": raw, "validator": reason, "final_cypher": final,
                                 "human_decision": "TODO: заповніть вручну (прийнято/відхилено + чому)"}, ensure_ascii=False) + "\n")
            rf.write(json.dumps({"id": t["id"], "verdict": verdict, "detail": detail, "rows": rows_n,
                                 "llm_seconds": round(llm_s, 2), "exec_seconds": None if exec_s is None else round(exec_s, 3)}, ensure_ascii=False) + "\n")
            print(f"{t['id']}: {verdict:22s} {detail}")
    c = Counter(verdicts); n = len(verdicts)
    print(f"\nКоректних: {c['correct']}/{n} = {c['correct']/n:.0%}  | розподіл: {dict(c)}")
    print("Журнал LLM:", log_path, "\nРезультати:", res_path)


if __name__ == "__main__":
    main()
