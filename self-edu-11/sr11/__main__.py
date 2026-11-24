"""CLI СР11:  python -m sr11 <команда>

  validate   перевірка набору запитів (C1) і доказів у корпусі
  check      перевірка середовища (--models: завантажити моделі, --llm: тестовий виклик Gemini)
  run        прогін 20 запитів через RAG lab-11   [--sleep 3] [--resume] [--only q01,q02]
  judge      LLM-суддя faithfulness              [--sleep 3] [--rpm 5]
  classify   авто-класифікація -> results/classification.csv (ручні колонки human_* зберігаються)
  sheet      аркуш для ручної перевірки ≥ 5 оцінок судді  [--n 8]
  kappa      згода «суддя vs людина»
  report     results/report_tables.md (таблиці, чернетка висновків і плану)
  selftest   увесь конвеєр на заглушці (без моделей і API) у тимчасовому каталозі
"""
import argparse
import os
import sys
import tempfile
from . import config as C


def cmd_validate(a):
    from .queries import load_queries, validate
    problems, summary = validate(load_queries())
    print("Підсумок:", summary)
    if problems:
        print("ПРОБЛЕМИ:\n  - " + "\n  - ".join(problems))
        return 1
    print("C1 ✓: 20 запитів, ≥ 4 категорії, ≥ 4 без відповіді/шкідливих; докази знайдено в корпусі.")
    return 0


def cmd_check(a):
    C.load_env()
    ok = True
    for mod in ("faiss", "numpy", "rank_bm25", "sentence_transformers", "google.genai"):
        try:
            __import__(mod)
            print(f"  ✓ {mod}")
        except Exception as e:
            ok = False
            print(f"  ✗ {mod}: {type(e).__name__}: {e}")
    print(f"lab-11: {C.LAB11} {'✓' if C.LAB11.exists() else '✗'}")
    try:
        print(f"індекс: {C.index_dir()} ✓")
    except FileNotFoundError as e:
        ok = False
        print(f"  ✗ {e}")
    for k in ("GEMINI_API_KEY", "GEMINI_MODEL", "JUDGE_MODEL"):
        v = os.environ.get(k)
        print(f"  {'✓' if v else '✗'} {k}" + (f" = {v}" if v and k != "GEMINI_API_KEY" else ""))
        ok &= bool(v)
    if os.environ.get("GEMINI_MODEL") and os.environ.get("GEMINI_MODEL") == os.environ.get("JUDGE_MODEL"):
        ok = False
        print("  ✗ JUDGE_MODEL збігається з GEMINI_MODEL (методичка вимагає різні)")
    if a.models and ok:
        rag = __import__("sr11.runner", fromlist=["x"]).make_rag()
        print(f"  ✓ RAG ініціалізовано: {len(rag.vi.chunks)} фрагментів, модель {rag.model}")
    if a.llm and ok:
        from google import genai
        c = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        for m in (os.environ["GEMINI_MODEL"], os.environ["JUDGE_MODEL"]):
            print(f"  ✓ {m}: {c.models.generate_content(model=m, contents='Reply with the single word OK').text.strip()[:20]}")
    return 0 if ok else 1


def cmd_run(a):
    from .queries import load_queries
    from .runner import make_rag, run_queries
    qs = load_queries()
    run_queries(make_rag(), qs, sleep=a.sleep, resume=a.resume, only=set(a.only.split(",")) if a.only else None)


def cmd_judge(a):
    from .judge import run_judge
    run_judge(sleep=a.sleep, rpm=a.rpm)


def cmd_classify(a):
    from . import table
    rows = table.save(table.build())
    print(f"Записано {C.p('classification.csv')} ({len(rows)} рядків). Перевір колонки auto_*, за потреби впиши human_verdict/human_cause/human_note.")
    manual = [r["id"] for r in rows if r["needs_manual"]]
    print("Потребують ручної перевірки:", ", ".join(manual) or "—")


def cmd_sheet(a):
    from .review import make_sheet
    make_sheet(a.n)


def cmd_kappa(a):
    from .review import compute_kappa
    compute_kappa()


def cmd_report(a):
    from .report import write
    write()


def cmd_selftest(a):
    from .queries import load_queries
    from .runner import run_queries
    from .judge import run_judge
    from .stub import StubRAG, stub_judge
    from . import table, report
    tmp = tempfile.mkdtemp(prefix="sr11_selftest_")
    C.set_results_dir(tmp)
    C.LLM_LOG = type(C.LLM_LOG)(tmp) / "llm_log"
    os.environ.update(GEMINI_MODEL="stub-gen", JUDGE_MODEL="stub-judge")
    qs = load_queries()
    run_queries(StubRAG(qs), qs, sleep=0, printer=lambda *_: None)
    run_judge(sleep=0, rpm=10**6, call=stub_judge, printer=lambda *_: None)
    rows = table.save(table.build())
    md = report.build(rows=rows)
    C.p("report_tables.md").write_text(md, encoding="utf-8")
    print(f"selftest OK: {len(rows)} запитів оброблено на ЗАГЛУШЦІ; файли в {tmp}")
    print("\n".join(md.splitlines()[14:40]))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sr11", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate").set_defaults(f=cmd_validate)
    s = sub.add_parser("check"); s.add_argument("--models", action="store_true"); s.add_argument("--llm", action="store_true"); s.set_defaults(f=cmd_check)
    s = sub.add_parser("run"); s.add_argument("--sleep", type=float, default=3.0); s.add_argument("--resume", action="store_true"); s.add_argument("--only"); s.set_defaults(f=cmd_run)
    s = sub.add_parser("judge"); s.add_argument("--sleep", type=float, default=3.0); s.add_argument("--rpm", type=int, default=5); s.set_defaults(f=cmd_judge)
    sub.add_parser("classify").set_defaults(f=cmd_classify)
    s = sub.add_parser("sheet"); s.add_argument("--n", type=int, default=8); s.set_defaults(f=cmd_sheet)
    sub.add_parser("kappa").set_defaults(f=cmd_kappa)
    sub.add_parser("report").set_defaults(f=cmd_report)
    sub.add_parser("selftest").set_defaults(f=cmd_selftest)
    a = ap.parse_args(argv)
    sys.exit(a.f(a) or 0)


if __name__ == "__main__":
    main()
