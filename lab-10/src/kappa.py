"""Результат 5, крок 2: узгодженість розмітки (κ) між людиною і Gemini.
  python -m src.kappa prepare   # пул пар «запит + фрагмент» з топ-4 hybrid_rerank
  python -m src.kappa label     # ТИ розмічаєш пари (наосліп) у терміналі
  python -m src.kappa gemini    # Gemini розмічає ті самі пари (логується в llm_log/)
  python -m src.kappa compute   # κ, збіг, розбіжності
"""
import json, random, re, sys, textwrap
from collections import Counter
from .config import ROOT, SEED

POOL, HUMAN, GEM = (ROOT / "eval" / f for f in ("kappa_pool.json", "kappa_human.json", "kappa_gemini.json"))
TARGET = {"paraphrase": 4, "keyword": 3, "multistep": 3, "unanswerable": 2}   # разом 12 запитів
TOPK = 4
norm = lambda s: re.sub(r"\s+", "", s).lower()
load = lambda p: json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
save = lambda p, o: p.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")

INSTRUCTION = ("Для кожної пари: чи містить ФРАГМЕНТ відповідь на ПИТАННЯ або необхідну частину відповіді?\n"
               "  1 = так (відповідь або її необхідна частина є у фрагменті)\n"
               "  0 = ні (фрагмент лише на ту саму тему, але відповіді не містить)")

def prepare():
    from .chunking import load_docs
    from .index import VectorIndex
    from .hybrid import HybridSearcher
    gold = [json.loads(l) for l in open(ROOT / "eval" / "gold.jsonl", encoding="utf-8")]
    rng = random.Random(SEED + 5)
    chosen = []
    for typ, n in TARGET.items():
        pool = [g for g in gold if g["type"] == typ]
        chosen += rng.sample(pool, min(n, len(pool)))
    docs = load_docs(); vi = VectorIndex("e5"); vi.build(docs); hs = HybridSearcher(vi, docs)
    pairs = []
    for g in chosen:
        for rank, r in enumerate(hs.search(g["question"], "hybrid_rerank", k=TOPK), 1):
            auto = int(any(norm(e) in norm(r["context"]) for e in g["evidence"]))
            pairs.append({"query_id": g["id"], "question": g["question"], "type": g["type"], "rank": rank,
                          "chunk_id": r["chunk_id"], "context": r["context"], "auto_label": auto})
    rng.shuffle(pairs)                         # перемішуємо, щоб порядок не підказував
    for i, p in enumerate(pairs, 1):
        p["pair_id"] = f"p{i:02d}"
    save(POOL, pairs)
    print(f"Запитів: {len(chosen)} {dict(Counter(g['type'] for g in chosen))}; пар: {len(pairs)} -> {POOL}")

def label():
    pairs, done = load(POOL), load(HUMAN)
    todo = [p for p in pairs if p["pair_id"] not in done]
    print(INSTRUCTION, f"\n\nРозмічено {len(done)} з {len(pairs)}. Команди: 1 / 0 / u (скасувати попереднє) / q (вийти, прогрес збережено)\n")
    i = 0
    while i < len(todo):
        p = todo[i]
        print("=" * 100, f"\n[{len(done) + 1}/{len(pairs)}] ПИТАННЯ: {p['question']}\n" + "-" * 100)
        print("\n".join(textwrap.fill(par, 110) for par in p["context"].split("\n") if par.strip()))
        while True:
            a = input("\nРелевантний? (1/0/u/q): ").strip().lower()
            if a in ("1", "0"):
                done[p["pair_id"]] = int(a); save(HUMAN, done); i += 1; break
            if a == "u" and i > 0:
                i -= 1; done.pop(todo[i]["pair_id"], None); save(HUMAN, done); break
            if a == "q":
                print("Збережено. Продовжити: python -m src.kappa label"); return
    print("\nГотово: розмічено все.")

def gemini():
    from .llm import ask
    pairs, done = load(POOL), load(GEM)
    system = "You are a careful annotator for a search-relevance dataset. Output JSON only."
    tmpl = ("Question: {q}\n\nPassage:\n\"\"\"\n{c}\n\"\"\"\n\n"
            "Label 1 if the passage contains the information that answers the question, or a necessary part of the answer "
            "(for a question with two parts, a passage that answers one of the parts counts). "
            "Label 0 if the passage is only about the same topic but does not contain the answer.\n"
            "Return JSON: {{\"label\": 0 or 1, \"reason\": \"one short sentence\"}}")
    for p in pairs:
        if p["pair_id"] in done: continue
        j = json.loads(ask(tmpl.format(q=p["question"], c=p["context"]), "kappa-v1", 0.0, system, True))
        done[p["pair_id"]] = {"label": int(j["label"]), "reason": j.get("reason", "")}
        save(GEM, done); print(p["pair_id"], done[p["pair_id"]]["label"], "-", done[p["pair_id"]]["reason"])
    print(f"Готово: {len(done)} пар -> {GEM}")

def kappa(a, b):
    from sklearn.metrics import cohen_kappa_score
    return float(cohen_kappa_score(a, b))

def compute():
    pairs, h, g = load(POOL), load(HUMAN), load(GEM)
    ids = [p["pair_id"] for p in pairs if p["pair_id"] in h and p["pair_id"] in g]
    assert len(ids) == len(pairs), f"розмічено людиною {len(h)}, Gemini {len(g)} з {len(pairs)}"
    P = {p["pair_id"]: p for p in pairs}
    H = [h[i] for i in ids]; G = [g[i]["label"] for i in ids]; A = [P[i]["auto_label"] for i in ids]
    k = kappa(H, G); agree = sum(x == y for x, y in zip(H, G)) / len(ids)
    cm = Counter(zip(H, G))
    scale = "незначна" if k < .2 else "слабка" if k < .4 else "помірна" if k < .6 else "суттєва" if k < .8 else "майже повна"
    print(f"Пар: {len(ids)}; запитів: {len({P[i]['query_id'] for i in ids})}")
    print(f"κ(людина, Gemini) = {k:.3f} ({scale}); збіг {agree:.1%}")
    print(f"Матриця (людина,Gemini): 1/1={cm[(1,1)]}  0/0={cm[(0,0)]}  людина1/Gemini0={cm[(1,0)]}  людина0/Gemini1={cm[(0,1)]}")
    print(f"Позитивних: людина {sum(H)}, Gemini {sum(G)}, за доказами (авто) {sum(A)}")
    ka_h, ka_g = kappa(H, A), kappa(G, A)
    print(f"Довідково: κ(людина, розмітка за доказами) = {ka_h:.3f}; κ(Gemini, за доказами) = {ka_g:.3f}")
    miss = [i for i in ids if h[i] == 1 and P[i]["auto_label"] == 0]
    print(f"Людина вважає релевантними {len(miss)} фрагментів, у яких немає речення-доказу: {miss}")
    dis = [i for i in ids if h[i] != g[i]["label"]]
    print(f"\nРозбіжності ({len(dis)}):")
    for i in dis:
        p = P[i]
        print(f"- {i} [{p['query_id']}] людина={h[i]} Gemini={g[i]['label']} за_доказами={p['auto_label']}\n    Q: {p['question']}\n    Gemini: {g[i]['reason']}\n    Фрагмент: {p['context'][:160].replace(chr(10), ' ')}...")
    save(ROOT / "eval" / "kappa_results.json", {"pairs": len(ids), "queries": len({P[i]['query_id'] for i in ids}), "kappa": round(k, 3),
         "scale": scale, "agreement": round(agree, 3), "confusion": {f"{a}/{b}": v for (a, b), v in cm.items()},
         "positives": {"human": sum(H), "gemini": sum(G), "evidence": sum(A)}, "kappa_human_vs_evidence": round(ka_h, 3),
         "kappa_gemini_vs_evidence": round(ka_g, 3), "human_relevant_without_evidence": miss, "disagreements": dis})

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"prepare": prepare, "label": label, "gemini": gemini, "compute": compute}.get(cmd, lambda: print(__doc__))()
