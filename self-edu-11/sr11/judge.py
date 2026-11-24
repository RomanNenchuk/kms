"""LLM-суддя faithfulness (вимога методички: JUDGE_MODEL ≠ GEMINI_MODEL; ≥ 5 оцінок підтвердити вручну).

Промпт і розбір відповіді — дослівна копія з lab-11/src/rag_eval.py (judge_v1), щоб оцінки були порівнянні з ЛР 11.
Копію зроблено навмисно: rag_eval.py містить f-рядок, який імпортується лише на Python ≥ 3.12.
"""
import datetime as dt
import json
import os
import re
import sys
import time
from . import config as C
from .queries import load_queries
from .runner import load_run, save_run


JUDGE_SYSTEM = """You are a strict evaluator of the faithfulness (groundedness) of answers written by a retrieval-augmented assistant.
You receive SOURCES, a QUESTION and an ANSWER. Judge ONLY against the SOURCES, never against your own knowledge.
1. Split the ANSWER into atomic factual claims. Ignore citation markers like [id]. Ignore sentences that only say that information is missing or that the sources disagree.
2. For each claim give a verdict: "supported" (stated in the SOURCES or follows directly from them), "unsupported" (not in the SOURCES, even if it is true in reality), or "contradicted" (the SOURCES say otherwise).
3. Reply with JSON only, no prose: {"claims":[{"claim":"...","verdict":"supported|unsupported|contradicted","evidence_id":"source id or null"}]}. If there are no factual claims, reply {"claims":[]}."""


def judge_prompt(question, contexts, answer):
    src = "\n\n".join(f"### SOURCE [{i}]\n{t}" for i, t in contexts.items())
    return f"SOURCES:\n{src}\n\nQUESTION:\n{question}\n\nANSWER:\n{answer}"


def parse_judge(text):
    data = json.loads(re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip())
    claims = data["claims"]
    n = len(claims)
    sup = sum(c.get("verdict") == "supported" for c in claims)
    return {"faithfulness": (sup / n) if n else None, "claims": claims}


def log_call(test_id, model, raw):
    path = C.LLM_LOG / "judge_calls.jsonl"
    path.parent.mkdir(exist_ok=True)
    rec = {"date": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "role": "judge", "test_id": test_id, "model": model,
           "params": {"temperature": 0, "response_mime_type": "application/json"}, "prompt_version": "judge_v1",
           "raw_output": raw, "human_decision": None}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def gemini_caller(system, model):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    cfg = types.GenerateContentConfig(system_instruction=system, temperature=0, response_mime_type="application/json")

    def call(prompt):
        for attempt in range(8):
            try:
                return client.models.generate_content(model=model, contents=prompt, config=cfg).text
            except Exception as e:
                msg = str(e)
                if attempt < 7 and any(x in msg for x in ("429", "500", "503", "UNAVAILABLE", "RESOURCE_EXHAUSTED")):
                    m = re.search(r"retry in ([\d.]+)s", msg)
                    wait = float(m.group(1)) + 2 if m else 2 ** min(attempt, 5) * 2
                    print(f"  ліміт тарифу, чекаю {wait:.0f} с")
                    time.sleep(wait)
                    continue
                raise
    return call


def run_judge(sleep=3.0, rpm=5, call=None, printer=print):
    C.load_env()
    gen, jm = os.environ.get("GEMINI_MODEL"), os.environ.get("JUDGE_MODEL")
    if not jm or jm == gen:
        sys.exit("JUDGE_MODEL має бути заданий і відрізнятись від GEMINI_MODEL (вимога методички).")
    call = call or gemini_caller(JUDGE_SYSTEM, jm)
    sleep = max(sleep, 60.0 / rpm + 0.5)
    tests = {q["id"]: q for q in load_queries()}
    results = load_run()
    todo = [r for r in results.values() if not r["abstained"] and "judge" not in r]
    printer(f"Суддя {jm}: {len(todo)} відповідей (відмови не оцінюються — тверджень немає)")
    for r in todo:
        raw = call(judge_prompt(tests[r["id"]]["question"], r["contexts"], r["answer"]))
        log_call(r["id"], jm, raw)
        try:
            r["judge"] = {**parse_judge(raw), "judge_model": jm}
        except Exception as e:
            r["judge"] = {"faithfulness": None, "claims": [], "judge_model": jm, "error": f"{type(e).__name__}: {e}", "raw": raw[:500]}
        save_run(results)
        printer(f"{r['id']} faithfulness={r['judge']['faithfulness']}")
        time.sleep(sleep)
