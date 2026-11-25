"""Вимірювання 8 метрик на станах сховища й оцінка за порогами двох сценаріїв.
    python -m src.measure                 # baseline, clean, lab11 -> results/measurements/<стан>.json + results/history.jsonl
    python -m src.measure --variant clean # лише один стан
Історія (results/history.jsonl) — append-only; запис додається, лише якщо відбиток даних стану ще не траплявся
(повторний запуск на тих самих даних новий замір не створює)."""
from __future__ import annotations
import argparse, datetime as dt, json
import yaml
from . import store
from .metrics import FUNCS, Ctx

CFG = store.ROOT / "config" / "metrics.yml"
RES = store.ROOT / "results"
HIST = RES / "history.jsonl"


def load_cfg():
    return yaml.safe_load(open(CFG, encoding="utf-8"))


def measure(variant, cfg=None):
    cfg = cfg or load_cfg()
    c = Ctx(store.load_tables(variant), store.load_corpus(variant), cfg)
    out = []
    for d in cfg["metrics"]:
        value, n, bad, examples, note = FUNCS[d["id"]](c, d)
        val = round(float(value), 4)
        out.append({"id": d["id"], "lab14": d.get("lab14"), "name": d["name"], "dimension": d["dimension"], "value": val,
                    "n_checked": int(n), "n_bad": int(bad), "examples": [str(x) for x in list(examples)[:6]], "note": note,
                    "status": {s: ("ok" if val >= d["thresholds"][s] else "fail") for s in cfg["scenarios"]},
                    "thresholds": d["thresholds"]})
    summary = {s: {"ok": sum(m["status"][s] == "ok" for m in out), "fail": sum(m["status"][s] == "fail" for m in out)} for s in cfg["scenarios"]}
    return {"variant": variant, "measured": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "data_sha256": store.data_fingerprint(variant), "reference_date": cfg["reference_date"], "summary": summary, "metrics": out}


def read_history():
    return [json.loads(l) for l in open(HIST, encoding="utf-8")] if HIST.exists() else []


def record(res):
    """Додає замір в історію, якщо такого відбитка даних для цього стану ще немає. Повертає True, якщо додано."""
    if any(h["variant"] == res["variant"] and h["data_sha256"] == res["data_sha256"] for h in read_history()):
        return False
    row = {k: res[k] for k in ("variant", "measured", "data_sha256", "summary")}
    row["values"] = {m["id"]: m["value"] for m in res["metrics"]}
    with open(HIST, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return True


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--variant", choices=store.VARIANTS); a = ap.parse_args()
    cfg = load_cfg(); (RES / "measurements").mkdir(parents=True, exist_ok=True)
    for v in ([a.variant] if a.variant else list(store.VARIANTS)):
        res = measure(v, cfg)
        (RES / "measurements" / f"{v}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        added = record(res)
        print(f"\n== {v}  ({'новий замір додано в історію' if added else 'без змін: такі дані вже виміряно'})")
        print(f"{'ID':3} {'вимір':12} {'значення':>9}  {'chat':>6} {'audit':>6}   проблем/перевірено")
        for m in res["metrics"]:
            t = m["thresholds"]; st = lambda s: ("✓" if m["status"][s] == "ok" else "✗") + f" {t[s]:.3f}"
            print(f"{m['id']:3} {m['dimension']:12} {m['value']:9.4f}  {st('chat'):>6} {st('audit'):>6}   {m['n_bad']}/{m['n_checked']}")
        print("підсумок:", {s: f"{x['ok']}/{x['ok'] + x['fail']}" for s, x in res["summary"].items()})


if __name__ == "__main__":
    main()
