"""Крок 2: прогін запитів через RAG із lab-11; збереження відповідей і джерел у results/run.jsonl."""
import datetime as dt
import json
import sys
import time
from . import config as C

MAX_CTX_CHARS = 3000          # як у lab-11/src/rag.py


def import_rag_module():
    """Імпортує lab-11/src/rag.py і перенаправляє журнал та індекси в self-edu-11 (lab-11 не змінюється)."""
    C.load_env()
    if not C.LAB11.exists():
        sys.exit(f"Не знайдено lab-11: {C.LAB11}. Поклади self-edu-11 поруч із lab-11 або задай LAB11_DIR.")
    sys.path.insert(0, str(C.LAB11))
    import src.index as idx
    import src.rag as rag
    idx.INDEXES = C.index_dir()
    rag.LOG_PATH = C.LLM_LOG / "rag_calls.jsonl"
    return rag


def make_rag():
    rag = import_rag_module()
    return rag.RAG()


def load_run():
    f = C.p("run.jsonl")
    if not f.exists():
        return {}
    return {r["id"]: r for r in (json.loads(l) for l in open(f, encoding="utf-8") if l.strip())}


def save_run(d):
    C.p("run.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in d.values()) + "\n", encoding="utf-8")


def run_queries(rag, queries, sleep=3.0, resume=False, only=None, top_k=5, printer=print):
    chunks = {c["chunk_id"]: c for c in rag.vi.chunks}
    results = load_run() if resume else {}
    for q in queries:
        if only and q["id"] not in only:
            continue
        if q["id"] in results:
            continue
        fx = [{"id": f["id"], "doc_id": None, "kind": "fixture", "header": f["header"], "text": f["text"]} for f in q["fixtures"]]
        try:
            res = rag.ask(q["question"], max_level=q["level"], extra_sources=fx or None, top_k=top_k, tag=f"sr11:{q['id']}")
        except Exception as e:                                           # 429 після ретраїв тощо: зберігаємо зроблене й виходимо
            save_run(results)
            printer(f"{q['id']}: помилка {type(e).__name__}: {str(e)[:160]}\nЗбережено {len(results)}; повтори з --resume.")
            return results
        ctx = {f["id"]: f["text"] for f in fx}
        for s in res["sources"]:
            if s["id"] not in ctx and s["id"] in chunks:
                c = chunks[s["id"]]
                ctx[s["id"]] = (c.get("context") or c["text"])[:MAX_CTX_CHARS]
        results[q["id"]] = {"id": q["id"], "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                            "level": q["level"], "answer": res["answer"], "abstained": res["abstained"],
                            "sources": res["sources"], "citations": res["citations"], "tokens": res["tokens"],
                            "latency_ms": res["latency_ms"]["total"], "request_id": res["request_id"],
                            "model": res["model"], "contexts": ctx}
        save_run(results)
        printer(f"{q['id']} {q['category']:<12} abstained={res['abstained']!s:<5} cited={len(res['citations']['cited'])} "
                f"invalid={len(res['citations']['invalid'])} tok={res['tokens']['total']}")
        time.sleep(sleep)
    save_run(results)
    printer(f"Збережено {len(results)} результатів -> {C.p('run.jsonl')}")
    return results
