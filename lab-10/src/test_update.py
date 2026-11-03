"""Результат 3, крок 4: перевірка upsert/delete/rebuild на 5 документах.
Запуск: python -m src.test_update
Нічого не зберігає на диск (корпус та indexes/ не змінюються), дописує розділ у docs/embeddings_cmp.md.
"""
import json, re, time
from .config import ROOT
from .chunking import load_docs
from .index import VectorIndex

norm = lambda s: re.sub(r"\s+", "", s).lower()
N_DOCS = 5
MARKER = ("The Zephyrian Aviation Authority (ZAA) was founded in 1987 in the city of Quillon. "
          "It regulates all commercial flights over the Zephyrian archipelago. "
          "Its headquarters is located at Quillon Harbour Airport, which has two runways.")
MARKER_Q = "When was the Zephyrian Aviation Authority founded?"

queries = [json.loads(l) for l in open(ROOT / "eval" / "queries_20.jsonl", encoding="utf-8")]
queries = [q for q in queries if q.get("status") == "verified"]
docs = {d["doc_id"]: d for d in load_docs()}
vi = VectorIndex("e5")
vi.build(list(docs.values()))
total0 = len(vi.chunks)
print(f"Збудовано: {total0} векторів")

def rank_of(q, k=5):
    res = vi.search(q["question"], k=k)
    ev = norm(q["evidence"])
    for r, x in enumerate(res, 1):
        if ev in norm(x["context"]):
            return r, res
    return None, res

# вибираємо 5 різних документів, для яких запит знаходить доказ у вихідному індексі
chosen, seen = [], set()
for q in queries:
    if q["doc_id"] in seen or q["doc_id"] not in docs:
        continue
    r, _ = rank_of(q)
    if r is not None:
        chosen.append((q, r)); seen.add(q["doc_id"])
    if len(chosen) == N_DOCS:
        break
print("Документи для тесту:", [q["doc_id"] for q, _ in chosen])

rows, ok_all = [], True
for q, r0 in chosen:
    did = q["doc_id"]; d = docs[did]
    n_chunks = sum(1 for c, a in zip(vi.chunks, vi.alive) if c["doc_id"] == did and a)
    # delete
    t0 = time.perf_counter(); removed = vi.delete(did); t_del = 1000 * (time.perf_counter() - t0)
    _, res = rank_of(q, k=10)
    gone = all(x["doc_id"] != did for x in res)
    # upsert того самого тексту (повернення)
    t0 = time.perf_counter(); up = vi.upsert(d); t_up = 1000 * (time.perf_counter() - t0)
    r_back, _ = rank_of(q)
    # upsert зміненого тексту
    edited = {**d, "body": d["body"] + "\n\n## Test addendum\n\n" + MARKER}
    t0 = time.perf_counter(); up2 = vi.upsert(edited); t_up2 = 1000 * (time.perf_counter() - t0)
    res = vi.search(MARKER_Q, k=5)
    marker_found = bool(res) and res[0]["doc_id"] == did and "Zephyrian" in res[0]["context"]
    alive_doc = sum(1 for c, a in zip(vi.chunks, vi.alive) if c["doc_id"] == did and a)
    no_dupes = alive_doc == up2["added"]                       # старі версії не «живі»
    r_after_edit, _ = rank_of(q)                                # старий контент так само знаходиться
    ok = gone and r_back is not None and marker_found and no_dupes and r_after_edit is not None
    ok_all &= ok
    rows.append({"doc_id": did, "chunks": n_chunks, "rank_before": r0, "removed": removed,
                 "gone_after_delete": gone, "rank_after_reupsert": r_back, "marker_rank1": marker_found,
                 "no_duplicates": no_dupes, "rank_old_content_after_edit": r_after_edit,
                 "delete_ms": round(t_del, 2), "upsert_ms": round(t_up, 1), "upsert_edit_ms": round(t_up2, 1), "ok": ok})
    print(rows[-1])

dead_before = vi.dead_fraction(); total_before = len(vi.chunks); alive_before = sum(vi.alive)
t0 = time.perf_counter(); live = vi.rebuild(); t_rebuild = time.perf_counter() - t0
after = [rank_of(q)[0] for q, _ in chosen]
rebuild_ok = live == alive_before and vi.dead_fraction() == 0 and all(a is not None for a in after)
ok_all &= rebuild_ok
print(f"rebuild: було {total_before} векторів ({dead_before:.0%} мертвих) -> {live}; {t_rebuild:.2f} с; пошук працює: {all(a is not None for a in after)}")
print("ПІДСУМОК:", "УСЕ ПРОЙШЛО" if ok_all else "Є ПРОВАЛИ")

yn = lambda b: "так" if b else "НІ"
L = ["Перевірка на 5 документах (модель e5, стратегія hierarchical; нічого не збережено на диск). "
     "Тестовий розділ «Test addendum» вигаданий і існує лише в пам'яті під час перевірки.", "",
     "| документ | векторів | ранг до | зник після delete | ранг після повторного upsert | новий розділ знайдено №1 | без дублікатів | старий контент після зміни (ранг) | delete, мс | upsert, мс | upsert зі зміною, мс |",
     "|---|---|---|---|---|---|---|---|---|---|---|"]
for r in rows:
    L.append(f"| {r['doc_id']} | {r['chunks']} | {r['rank_before']} | {yn(r['gone_after_delete'])} | {r['rank_after_reupsert']} | "
             f"{yn(r['marker_rank1'])} | {yn(r['no_duplicates'])} | {r['rank_old_content_after_edit']} | {r['delete_ms']} | {r['upsert_ms']} | {r['upsert_edit_ms']} |")
L += ["", f"Rebuild: до компактизації {total_before} векторів, з них мертвих {dead_before:.0%} ({total_before - alive_before} шт.); "
          f"після — {live} векторів; час {t_rebuild:.2f} с; пошук після rebuild працює: {yn(all(a is not None for a in after))}.",
      "", "Процедура оновлення: `delete(doc_id)` позначає вектори документа як мертві (FAISS HNSW не вміє видаляти вектори), "
          "пошук їх пропускає; `upsert(doc)` = delete + додавання нових векторів у граф; коли мертвих багато (наприклад, понад 20%), "
          "викликається `rebuild()`, що будує граф лише з живих векторів."]
json.dump({"rows": rows, "rebuild": {"before": total_before, "dead_fraction": dead_before, "after": live, "seconds": t_rebuild}},
          open(ROOT / "eval" / "update_test.json", "w"), indent=2)
p = ROOT / "docs" / "embeddings_cmp.md"
if p.exists():
    s = p.read_text(encoding="utf-8")
    p.write_text(s.replace("(допишемо на наступному кроці)", "\n".join(L)), encoding="utf-8")
    print("docs/embeddings_cmp.md оновлено")
