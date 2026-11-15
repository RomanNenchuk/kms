"""SQL через семантичний шар (ЛР 12): модель вибирає ІМЕНА метрик/вимірів із реєстру, SQL будує код.
Вільного SQL від моделі немає. З'єднання DuckDB — read-only."""
import hashlib
import json
import re
import duckdb
import yaml
from . import config

OPS = {"=", "<>", "<", ">", "<=", ">=", "IN", "NOT IN"}


def load_cfg() -> dict:
    return yaml.safe_load(config.METRICS_YML.read_text(encoding="utf-8"))


def list_metrics() -> dict:
    cfg = load_cfg()
    return {"ok": True,
            "metrics": [{"name": m["name"], "definition": m["definition"], "unit": m["unit"], "constraints": m["constraints"]}
                        for m in cfg["metrics"] if m.get("status") == "approved"],
            "dimensions": list(cfg["dimensions"]), "fact_grain": cfg["meta"]["grain"], "year": 2025}


def _lit(v):
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def _parse(v: str):
    s = str(v).strip()
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    return s


def build_sql(metrics, group_by, filters, order_by, limit) -> str:
    cfg = load_cfg()
    approved = {m["name"]: m for m in cfg["metrics"] if m.get("status") == "approved"}
    for n in metrics:
        if n not in approved:
            raise ValueError(f"unknown_or_unapproved_metric:{n}")
    for g in group_by:
        if g not in cfg["dimensions"]:
            raise ValueError(f"unknown_dimension:{g}")
    selects, joins = [], {}

    def use(dim):
        d = cfg["dimensions"][dim]
        if "join" in d:
            joins.setdefault(d["join"]["alias"], d["join"])
        return d["expr"]

    for g in group_by:
        selects.append(f"{use(g)} AS {g}")
    for n in metrics:
        selects.append(f"{approved[n]['formula']} AS {n}")
    where = []
    for f in filters:
        dim, op, raw = f["dim"], f["op"].upper(), f["value"]
        if dim not in cfg["dimensions"]:
            raise ValueError(f"unknown_dimension:{dim}")
        if op not in OPS:
            raise ValueError(f"bad_operator:{op}")
        rhs = "(" + ", ".join(_lit(_parse(x)) for x in str(raw).split(",")) + ")" if op in ("IN", "NOT IN") else _lit(_parse(raw))
        where.append(f"{use(dim)} {op} {rhs}")
    sql = "SELECT " + ", ".join(selects) + f"\nFROM {cfg['meta']['fact_table']} f"
    for j in joins.values():
        sql += f"\nJOIN {j['table']} {j['alias']} ON {j['cond']}"
    if where:
        sql += "\nWHERE " + " AND ".join(where)
    if group_by:
        sql += "\nGROUP BY " + ", ".join(str(i + 1) for i in range(len(group_by)))
    if order_by:
        if order_by not in list(group_by) + list(metrics):
            raise ValueError("order_by_must_be_selected_column")
        sql += f"\nORDER BY {order_by}"
    elif group_by:
        sql += "\nORDER BY " + ", ".join(str(i + 1) for i in range(len(group_by)))
    return sql + f"\nLIMIT {max(1, min(int(limit), config.MAX_ROWS))}"


def query_metric(metrics, group_by=(), filters=(), order_by=None, limit=config.MAX_ROWS) -> dict:
    if not metrics:
        raise ValueError("metrics_required")
    sql = build_sql(list(metrics), list(group_by), [dict(f) for f in filters], order_by, limit)
    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    try:
        con.execute("SET enable_external_access=false")
        df = con.execute(sql).fetchdf()
    finally:
        con.close()
    sid = "sql:" + hashlib.sha1(sql.encode()).hexdigest()[:8]
    rows = json.loads(df.round(2).to_json(orient="records"))   # NaN (SUM по порожній вибірці) -> null: інакше JSON невалідний
    defs = {m["name"]: m["definition"] for m in load_cfg()["metrics"] if m["name"] in metrics}
    return {"ok": True, "id": sid, "metric_definitions": defs, "sql": sql, "columns": list(df.columns), "rows": rows, "row_count": len(rows),
            "citation_ids": [sid]}
