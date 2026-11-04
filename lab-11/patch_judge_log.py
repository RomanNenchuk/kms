import pathlib

p = pathlib.Path("src/rag_eval.py")
s = p.read_text(encoding="utf-8")
if "log_judge_call" in s:
    raise SystemExit("вже застосовано")
helper = '''def log_judge_call(test_id, model, raw):
    """Журнал викликів судді (протокол «LLM-експерт»): дата, модель, параметри, версія підказки, сирий вихід."""
    import datetime as dt
    path = ROOT / "llm_log" / "judge_calls.jsonl"
    path.parent.mkdir(exist_ok=True)
    rec = {"date": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "role": "judge", "test_id": test_id,
           "model": model, "params": {"temperature": 0, "response_mime_type": "application/json"},
           "prompt_version": "judge_v1", "raw_output": raw, "human_decision": None}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\\n")


'''
a1 = "def run_judge(sleep=3.0, call=None, rpm=5):"
a2 = '        raw = call(judge_prompt(tests[rid]["question"], r["contexts"], r["answer"]))\n'
assert a1 in s and a2 in s, "якорі не знайдено: файл відрізняється від очікуваного"
s = s.replace(a1, helper + a1, 1).replace(a2, a2 + "        log_judge_call(rid, jm, raw)\n", 1)
p.write_text(s, encoding="utf-8")
print("патч застосовано")