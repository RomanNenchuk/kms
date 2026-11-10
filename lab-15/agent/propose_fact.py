"""propose_fact: безпечний запис нових знань із людиною в циклі (Результат 5).

Конвеєр:  пропозиція -> політика (заборонені дії, підозрілий вміст) -> provenance (перевірка джерела)
          -> SHACL (semantic/shapes.ttl) -> семантичні перевірки (дублі, існування) -> оцінка ризику
          -> low: автозапис | medium/high: черга на схвалення людини -> запис лише з provenance.
Агент (LLM) може лише ПРОПОНУВАТИ (propose). Схвалює людина окремою командою (review / interactive): агент цієї функції не має.
Усі кроки пишуться в журнал аудиту logs/audit.jsonl (ланцюжок хешів). Схвалені факти йдуть у data/updates/approved_facts.jsonl,
а НЕ в CSV графа: злиття з графом — окремий свідомий крок (так оцінки Результатів 2–4 лишаються відтворюваними).

CLI:  python -m agent.propose_fact propose --file fact.json | list | review ID approve|reject --reviewer X --reason ".."
                                  | interactive --reviewer X | metrics | verify-audit | expire --days 7"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
import time
from decimal import Decimal
from pathlib import Path

from mcp_server import config, guards
from mcp_server.graph import get_graph

ROOT = config.ROOT
SHAPES = ROOT / "semantic" / "shapes.ttl"
STATE_DIR = ROOT / "data" / "updates"          # proposals.json, approved_facts.jsonl
AUDIT = config.LOG_DIR / "audit.jsonl"
NS = "https://example.org/aviation#"
ACTIONS = {"add_relation", "add_risk", "update_property"}
FORBIDDEN_ACTIONS = {"delete_relation", "delete_node", "delete", "overwrite"}
ALLOWED_REL = {"AFFECTED_BY"}
TIERS = ["low", "medium", "high"]

TOOL_SCHEMA = {
    "name": "propose_fact",
    "description": "Запропонувати нове знання для сховища. Нічого не записує без перевірки; середній і високий ризик чекають схвалення людини.",
    "input_schema": {"type": "object", "required": ["action", "source"], "properties": {
        "action": {"enum": sorted(ACTIONS)},
        "relation": {"type": "object", "description": "для add_relation: {type:'AFFECTED_BY', start:<flightId>, end:<riskId>, confidence:0..1}"},
        "risk": {"type": "object", "description": "для add_risk: {riskId, name, kind, level}"},
        "update": {"type": "object", "description": "для update_property: {key:<riskId>, property:'level', new:1..5}"},
        "source": {"type": "object", "description": "{type: kb|graph|url|operator, ref, quote?}: обов'язково"},
        "rationale": {"type": "string"}}},
}


# --- допоміжне: файли, хеші, журнал ---------------------------------------------------------------
def _now() -> tuple[float, str]:
    t = time.time()
    return t, time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t))


def _canon(o) -> str:
    return json.dumps(o, sort_keys=True, ensure_ascii=False, default=str)


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _proposals_path() -> Path:
    return STATE_DIR / "proposals.json"


def _approved_path() -> Path:
    return STATE_DIR / "approved_facts.jsonl"


def _load() -> dict:
    p = _proposals_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save(d: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _proposals_path().write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def audit(event: str, pid: str, actor: str, **detail) -> dict:
    """Додає запис у журнал аудиту. prev/hash утворюють ланцюжок: зміна старого запису ламає перевірку verify_audit."""
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    prev = "0" * 64
    if AUDIT.exists():
        lines = [l for l in AUDIT.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            prev = json.loads(lines[-1])["hash"]
    epoch, iso = _now()
    rec = {"ts": iso, "epoch": round(epoch, 3), "event": event, "proposal_id": pid, "actor": actor, "detail": detail, "prev": prev}
    rec["hash"] = _sha(prev + _canon({k: v for k, v in rec.items() if k != "hash"}))
    with open(AUDIT, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    return rec


def verify_audit() -> tuple[bool, str]:
    if not AUDIT.exists():
        return True, "журнал порожній"
    prev = "0" * 64
    for i, line in enumerate(l for l in AUDIT.read_text(encoding="utf-8").splitlines() if l.strip()):
        r = json.loads(line)
        h = r.pop("hash")
        if r["prev"] != prev or _sha(prev + _canon(r)) != h:
            return False, f"ланцюжок порушено на записі {i + 1}"
        prev = h
    return True, f"ланцюжок цілий ({i + 1} записів)"


# --- перевірка джерела (provenance) -----------------------------------------------------------------
_kb_cache: dict | None = None


def _kb_chunks() -> dict:
    global _kb_cache
    if _kb_cache is None:
        _kb_cache = {}
        for line in open(config.KB_CORPUS, encoding="utf-8"):
            r = json.loads(line)
            _kb_cache[r["chunk_id"]] = r["text"]
    return _kb_cache


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def verify_source(fact: dict) -> tuple[str, str]:
    """Повертає (trust, пояснення). trust: verified | unverified | rejected."""
    src = fact.get("source") or {}
    typ, ref = str(src.get("type", "")).strip(), str(src.get("ref", "")).strip()
    if not typ or not ref:
        return "rejected", "no_provenance"
    if typ == "kb":
        ref = ref.removeprefix("kb:")
        text = _kb_chunks().get(ref)
        if text is None:
            return "rejected", f"unknown_kb_chunk:{ref}"
        quote = _norm(src.get("quote", ""))
        if len(quote) < 20:
            return "rejected", "quote_required_for_kb_source"
        if quote not in _norm(text):
            return "rejected", "evidence_mismatch:quote_not_in_chunk"
        return "verified", f"цитата знайдена у kb:{ref}"
    if typ == "graph":
        g, rel = get_graph(), fact.get("relation") or {}
        if fact.get("action") == "add_relation":
            if (("FlightDelay", ref) in g.props and
                    any(t == "HAS_DELAY" and b == ("FlightDelay", ref) for t, fwd, b, _ in g.adj[("Flight", rel.get("start"))] if fwd) and
                    any(t == "CAUSED_BY" and b == ("Risk", rel.get("end")) for t, fwd, b, _ in g.adj[("FlightDelay", ref)] if fwd)):
                return "verified", f"виводиться з графа: Flight-HAS_DELAY->{ref}-CAUSED_BY->Risk"
        return "unverified", "graph_reference_does_not_support_fact"
    if typ == "url":
        return ("unverified", "url_not_fetched_untrusted") if re.fullmatch(r"https://[\w.-]+\.[a-z]{2,}(/\S*)?", ref, re.I) else ("rejected", "bad_url")
    if typ == "operator":
        return "unverified", "operator_statement_not_verifiable"
    return "rejected", f"unknown_source_type:{typ}"


# --- SHACL -------------------------------------------------------------------------------------------
def shacl_validate(fact: dict) -> list[str]:
    """Будує RDF-граф пропозиції (+ типи існуючих сутностей) і перевіряє його за semantic/shapes.ttl. Повертає список порушень."""
    from rdflib import Graph as RG, Literal, Namespace, RDF, URIRef
    from rdflib.namespace import XSD
    from pyshacl import validate
    AV, g, kg = Namespace(NS), RG(), get_graph()
    prop = URIRef(NS + "proposal")
    src = fact.get("source") or {}

    def ent(label, key):
        u = URIRef(f"{NS}{label}_{key}")
        if (label, str(key)) in kg.props:
            g.add((u, RDF.type, AV[label]))
        return u

    def num(v, dt):
        try:
            return Literal(v, datatype=dt) if not isinstance(v, bool) and v is not None else Literal(str(v))
        except Exception:
            return Literal(str(v))

    act = fact.get("action")
    if act == "add_relation":
        r = fact.get("relation") or {}
        g.add((prop, RDF.type, AV.RelationProposal))
        g.add((prop, AV.start, ent("Flight", r.get("start"))))
        g.add((prop, AV.end, ent("Risk", r.get("end"))))
        g.add((prop, AV.relType, Literal(str(r.get("type")))))
        conf = r.get("confidence")
        g.add((prop, AV.confidence, Literal(Decimal(str(conf)), datatype=XSD.decimal) if isinstance(conf, (int, float)) and not isinstance(conf, bool) else Literal(str(conf))))
    elif act == "add_risk":
        r = fact.get("risk") or {}
        g.add((prop, RDF.type, AV.RiskProposal))
        g.add((prop, AV.riskId, Literal(str(r.get("riskId")))))
        g.add((prop, AV.name, Literal(str(r.get("name")))))
        g.add((prop, AV.kind, Literal(str(r.get("kind")))))
        lv = r.get("level")
        g.add((prop, AV.level, Literal(lv, datatype=XSD.integer) if isinstance(lv, int) and not isinstance(lv, bool) else Literal(str(lv))))
    elif act == "update_property":
        u = fact.get("update") or {}
        g.add((prop, RDF.type, AV.UpdateProposal))
        g.add((prop, AV.target, ent("Risk", u.get("key"))))
        g.add((prop, AV.property, Literal(str(u.get("property")))))
        nv = u.get("new")
        g.add((prop, AV.newValue, Literal(nv, datatype=XSD.integer) if isinstance(nv, int) and not isinstance(nv, bool) else Literal(str(nv))))
    if src.get("type"):
        g.add((prop, AV.sourceType, Literal(str(src["type"]))))
    if src.get("ref"):
        g.add((prop, AV.sourceRef, Literal(str(src["ref"]))))
    conforms, rg, _ = validate(g, shacl_graph=str(SHAPES), inference="none")
    if conforms:
        return []
    from rdflib.namespace import SH
    return sorted({f"{str(rg.value(r, SH.resultPath) or '').split('#')[-1]}: {rg.value(r, SH.resultMessage)}" for r in rg.subjects(RDF.type, SH.ValidationResult)})


# --- політика, семантичні перевірки, ризик ------------------------------------------------------------
def _strings(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _strings(v)
    elif isinstance(o, str):
        yield o


def policy_check(fact: dict) -> str | None:
    act = fact.get("action")
    if act in FORBIDDEN_ACTIONS:
        return f"forbidden_action:{act}"
    if act not in ACTIONS:
        return f"unsupported_action:{act}"
    rel = (fact.get("relation") or {}).get("type")
    if act == "add_relation" and rel not in ALLOWED_REL:
        return f"forbidden_relation:{rel}" if rel in config.REL_LEVEL else f"unsupported_relation:{rel}"
    flags = [f for s in _strings(fact) for f in guards.scan_untrusted(s)]
    if flags:
        return f"suspicious_content:{flags[0]}"
    return None


def semantic_check(fact: dict) -> str | None:
    g, act = get_graph(), fact["action"]
    if act == "add_relation":
        r = fact["relation"]
        if any(t == r["type"] and b == ("Risk", r["end"]) for t, fwd, b, _ in g.adj[("Flight", r["start"])] if fwd):
            return "duplicate_relation"
    elif act == "add_risk":
        if ("Risk", fact["risk"]["riskId"]) in g.props:
            return "risk_already_exists"
    elif act == "update_property":
        u = fact["update"]
        old = g.props.get(("Risk", u["key"]), {}).get(u["property"])
        if str(old) == str(u["new"]):
            return "no_change"
        if u.get("expected_old") is not None and str(u["expected_old"]) != str(old):
            return f"stale_expected_old:{old}"
    return None


def classify(fact: dict, trust: str) -> tuple[str, list[str]]:
    """Детермінована оцінка ризику (без LLM). Повертає (low|medium|high, причини)."""
    base = {"add_relation": 0, "add_risk": 1, "update_property": 2}[fact["action"]]
    tier, why = base, [f"базовий рівень дії {fact['action']}: {TIERS[base]}"]
    if trust != "verified":
        tier += 1; why.append("джерело не підтверджено (+1)")
    if fact["action"] == "add_relation" and fact["relation"]["confidence"] < 0.8:
        tier += 1; why.append("confidence < 0.8 (+1)")
    if fact["action"] == "add_risk" and fact["risk"]["level"] >= 4:
        tier += 1; why.append("високий рівень серйозності нового ризику (+1)")
    return TIERS[min(tier, 2)], why


# --- головна функція ---------------------------------------------------------------------------------
def _pid(fact: dict) -> str:
    core = {k: fact.get(k) for k in ("action", "relation", "risk", "update", "source")}
    return "P-" + _sha(_canon(core))[:8]


def _finish(store, rec, status, **extra):
    rec.update(status=status, **extra)
    store[rec["id"]] = rec
    _save(store)
    return {"proposal_id": rec["id"], "status": status, **{k: v for k, v in extra.items()}}


def propose(fact: dict, proposer: str = "agent") -> dict:
    """Єдина точка входу для агента. Нічого не записує у знання без перевірок; ніколи не схвалює середній/високий ризик."""
    store = _load()
    pid = _pid(fact)
    if pid in store and store[pid]["status"] in ("pending", "applied", "approved"):
        return {"proposal_id": pid, "status": store[pid]["status"], "duplicate_submission": True, "risk": store[pid].get("risk")}
    epoch, iso = _now()
    rec = {"id": pid, "fact": fact, "proposer": proposer, "proposed_at": iso, "proposed_epoch": epoch}
    audit("proposed", pid, proposer, action=fact.get("action"), source=fact.get("source"))

    def reject(stage, reason, **extra):
        audit("rejected_by_" + stage, pid, "system", reason=reason, **extra)
        return _finish(store, rec, "rejected", stage=stage, reason=reason, **extra)

    if (p := policy_check(fact)):
        return reject("policy", p)
    trust, note = verify_source(fact)
    if trust == "rejected":
        return reject("provenance", note)
    audit("source_checked", pid, "system", trust=trust, note=note)
    if (viol := shacl_validate(fact)):
        return reject("shacl", "shacl_violation", violations=viol)
    audit("shacl_ok", pid, "system")
    if (sem := semantic_check(fact)):
        return reject("semantic", sem)
    tier, why = classify(fact, trust)
    rec.update(risk=tier, risk_reasons=why, source_trust=trust, source_note=note)
    audit("classified", pid, "system", risk=tier, reasons=why)
    if tier == "low" and trust == "verified":
        rec["approved_by"] = "auto-policy"
        audit("auto_approved", pid, "system", risk=tier)
        _apply(rec)
        return _finish(store, rec, "applied", risk=tier, risk_reasons=why, auto=True)
    audit("pending_review", pid, "system", risk=tier)
    return _finish(store, rec, "pending", risk=tier, risk_reasons=why, needs="human_approval")


def _apply(rec: dict):
    """Запис у сховище схвалених фактів. Без provenance не виконується."""
    f = rec["fact"]
    if not (f.get("source") or {}).get("ref") or not rec.get("approved_by"):
        raise PermissionError("запис без provenance або без схвалення заборонений")
    entry = {"fact_id": rec["id"], "action": f["action"], "payload": f.get("relation") or f.get("risk") or f.get("update"),
             "provenance": {"source": f["source"], "trust": rec.get("source_trust"), "proposed_by": rec["proposer"],
                            "approved_by": rec["approved_by"], "risk": rec.get("risk"), "rationale": f.get("rationale")}}
    entry["hash"] = _sha(_canon(entry))
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(_approved_path(), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    audit("applied", rec["id"], rec["approved_by"], fact_hash=entry["hash"])


def review(pid: str, decision: str, reviewer: str, reason: str = "", simulated: bool = False) -> dict:
    """Рішення людини. Агент цю функцію не викликає (її немає серед його інструментів)."""
    store = _load()
    rec = store.get(pid)
    if not rec:
        return {"ok": False, "error": "unknown_proposal"}
    if rec["status"] != "pending":
        return {"ok": False, "error": f"not_pending:{rec['status']}"}
    if decision not in ("approve", "reject"):
        return {"ok": False, "error": "decision_must_be_approve_or_reject"}
    if not reviewer.strip():
        return {"ok": False, "error": "reviewer_required"}
    if reviewer.strip() == rec["proposer"]:
        return {"ok": False, "error": "self_approval_forbidden"}
    if decision == "reject" and not reason.strip():
        return {"ok": False, "error": "reason_required_for_rejection"}
    if decision == "approve" and rec["risk"] == "high" and not reason.strip():
        return {"ok": False, "error": "reason_required_for_high_risk_approval"}
    epoch, iso = _now()
    rec.update(reviewed_by=reviewer, reviewed_at=iso, review_seconds=round(epoch - rec["proposed_epoch"], 1), review_reason=reason)
    if decision == "reject":
        audit("rejected_by_human", pid, reviewer, reason=reason, simulated=simulated, seconds=rec["review_seconds"])
        return {"ok": True, **_finish(store, rec, "rejected", stage="human", reason=reason)}
    rec["approved_by"] = reviewer
    audit("approved_by_human", pid, reviewer, reason=reason, simulated=simulated, seconds=rec["review_seconds"])
    _apply(rec)
    return {"ok": True, **_finish(store, rec, "applied")}


def expire_stale(max_age_days: float = 7.0, now: float | None = None) -> list[str]:
    """Заявки, що надто довго чекають, закриваються як відхилені (за замовчуванням — відмова)."""
    store, out, t = _load(), [], now or time.time()
    for pid, rec in store.items():
        if rec["status"] == "pending" and t - rec["proposed_epoch"] > max_age_days * 86400:
            audit("expired", pid, "system", days=max_age_days)
            rec.update(status="rejected", stage="expired", reason="expired_without_review")
            out.append(pid)
    _save(store)
    return out


def metrics() -> dict:
    """Метрики з журналу аудиту."""
    ev = [json.loads(l) for l in AUDIT.read_text(encoding="utf-8").splitlines() if l.strip()] if AUDIT.exists() else []
    by = {}
    for e in ev:
        by.setdefault(e["proposal_id"], []).append(e)
    cnt = lambda name: sum(any(x["event"] == name for x in v) for v in by.values())
    risk = {t: 0 for t in TIERS}
    for v in by.values():
        for x in v:
            if x["event"] == "classified":
                risk[x["detail"]["risk"]] += 1
    human_app, human_rej = cnt("approved_by_human"), cnt("rejected_by_human")
    secs = [x["detail"]["seconds"] for v in by.values() for x in v if x["event"] in ("approved_by_human", "rejected_by_human") and not x["detail"].get("simulated")]
    secs_all = [x["detail"]["seconds"] for v in by.values() for x in v if x["event"] in ("approved_by_human", "rejected_by_human")]
    auto = cnt("auto_approved")
    rej_val = sum(any(x["event"].startswith("rejected_by_") and x["event"] != "rejected_by_human" for x in v) for v in by.values())
    decided_h = human_app + human_rej
    classified = sum(risk.values())
    med = lambda a: round(statistics.median(a), 1) if a else None
    return {"proposals": len(by), "rejected_before_review (policy/provenance/shacl/semantic)": rej_val, "classified": classified, "by_risk": risk,
            "auto_approved": auto, "human_reviewed": decided_h, "human_approved": human_app, "human_rejected": human_rej,
            "approval_rate_human": round(human_app / decided_h, 3) if decided_h else None,
            "approval_rate_of_classified": round((auto + human_app) / classified, 3) if classified else None,
            "median_review_seconds_real": med(secs), "median_review_seconds_incl_simulated": med(secs_all),
            "simulated_reviews": len(secs_all) - len(secs)}


# --- CLI -----------------------------------------------------------------------------------------------
def _show(rec):
    f = rec["fact"]
    print(f"\n[{rec['id']}] ризик={rec['risk']} джерело={rec['source_trust']} ({rec['source_note']})")
    print(f"  дія: {f['action']}  дані: {json.dumps(f.get('relation') or f.get('risk') or f.get('update'), ensure_ascii=False)}")
    print(f"  джерело: {json.dumps(f['source'], ensure_ascii=False)}\n  причина ризику: {'; '.join(rec['risk_reasons'])}\n  обґрунтування: {f.get('rationale')}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose"); p.add_argument("--file", required=True)
    sub.add_parser("list")
    r = sub.add_parser("review"); r.add_argument("id"); r.add_argument("decision", choices=["approve", "reject"])
    r.add_argument("--reviewer", required=True); r.add_argument("--reason", default="")
    i = sub.add_parser("interactive"); i.add_argument("--reviewer", required=True)
    sub.add_parser("metrics"); sub.add_parser("verify-audit")
    e = sub.add_parser("expire"); e.add_argument("--days", type=float, default=7)
    a = ap.parse_args()
    if a.cmd == "propose":
        print(json.dumps(propose(json.loads(Path(a.file).read_text(encoding="utf-8"))), ensure_ascii=False, indent=2))
    elif a.cmd == "list":
        for rec in _load().values():
            print(rec["id"], rec["status"], rec.get("risk"), rec["fact"]["action"], rec.get("reason", ""))
    elif a.cmd == "review":
        print(json.dumps(review(a.id, a.decision, a.reviewer, a.reason), ensure_ascii=False, indent=2))
    elif a.cmd == "interactive":
        pend = [x for x in _load().values() if x["status"] == "pending"]
        print(f"Очікують рішення: {len(pend)}")
        for rec in pend:
            _show(rec)
            d = input("  рішення [a=схвалити / r=відхилити / s=пропустити]: ").strip().lower()
            if d == "s":
                continue
            reason = input("  причина (обов'язкова для відхилення і для високого ризику): ").strip()
            print("  ->", review(rec["id"], "approve" if d == "a" else "reject", a.reviewer, reason))
    elif a.cmd == "metrics":
        print(json.dumps(metrics(), ensure_ascii=False, indent=2))
    elif a.cmd == "verify-audit":
        ok, msg = verify_audit(); print(msg); sys.exit(0 if ok else 1)
    elif a.cmd == "expire":
        print("закрито:", expire_stale(a.days))


if __name__ == "__main__":
    main()
