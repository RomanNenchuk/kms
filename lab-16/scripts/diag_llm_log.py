#!/usr/bin/env python3
"""Діагностика журналу Gemini (llm_log/explain_calls.jsonl): для кожного виходу, де назва в лапках «…» не збігається з
дозволеною, показує посимвольну різницю з найближчою дозволеною назвою. Запуск: python scripts/diag_llm_log.py"""
import difflib, json, pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from reco.explain import norm

log = ROOT / "llm_log" / "explain_calls.jsonl"
n = bad = 0
for line in log.read_text(encoding="utf-8").splitlines():
    r = json.loads(line); n += 1
    allowed = [norm(s) for s in r["input"]["дозволені_сутності"]]
    for span in re.findall(r"«([^»]+)»", norm(r["raw_output"])):
        if span in allowed:
            continue
        bad += 1
        best = max(allowed, key=lambda a: difflib.SequenceMatcher(None, span, a).ratio())
        print(f"\nвиклик {n}: назва НЕ збігається з дозволеною")
        print("  у виході LLM :", repr(span))
        print("  найближча    :", repr(best))
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, span, best).get_opcodes():
            if op != "equal":
                print(f"  різниця      : {op}: LLM={span[i1:i2]!r} (коди {[hex(ord(c)) for c in span[i1:i2]]}) vs дозволена={best[j1:j2]!r}")
print(f"\nперевірено {n} унікальних викликів, назв, що не збігаються: {bad}")
