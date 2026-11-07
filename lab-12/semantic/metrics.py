"""Семантичний шар: генерація SQL за назвою метрики (і вимірів/фільтрів з metrics.yml).

    from metrics import metric_sql
    metric_sql("on_time_rate", group_by=["airline_type"])
    metric_sql(["flights_count", "avg_delay_min"], group_by=["season"],
               filters=[("airline_type", "=", "low-cost")])

CLI: python semantic/metrics.py on_time_rate --by season --by airline_type
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

CFG = Path(__file__).with_name("metrics.yml")
OPS = {"=", "<>", "<", ">", "<=", ">=", "IN", "NOT IN"}


def load_config() -> dict:
    return yaml.safe_load(CFG.read_text(encoding="utf-8"))


def get_metric(name: str, cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    for m in cfg["metrics"]:
        if m["name"] == name:
            if m.get("status") == "deprecated":
                raise ValueError(f"Метрика '{name}' має статус deprecated")
            return m
    raise KeyError(f"Невідома метрика '{name}'. Доступні: {[m['name'] for m in cfg['metrics']]}")


def _dim(name: str, cfg: dict) -> dict:
    if name not in cfg["dimensions"]:
        raise KeyError(f"Невідомий вимір '{name}'. Доступні: {list(cfg['dimensions'])}")
    return cfg["dimensions"][name]


def _lit(v) -> str:
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def metric_sql(metrics, group_by=(), filters=(), order_by: str | None = None, limit: int | None = None) -> str:
    """Будує SELECT для однієї або кількох метрик. Імена беруться лише з реєстру (whitelist)."""
    cfg = load_config()
    names = [metrics] if isinstance(metrics, str) else list(metrics)
    group_by = list(group_by)

    selects, joins = [], {}
    for g in group_by:
        d = _dim(g, cfg)
        selects.append(f"{d['expr']} AS {g}")
        if "join" in d:
            joins.setdefault(d["join"]["alias"], d["join"])
    for n in names:
        selects.append(f"{get_metric(n, cfg)['formula']} AS {n}")

    where = []
    for dim, op, val in filters:
        op = op.upper()
        if op not in OPS:
            raise ValueError(f"Недозволений оператор '{op}'")
        d = _dim(dim, cfg)
        if "join" in d:
            joins.setdefault(d["join"]["alias"], d["join"])
        rhs = "(" + ", ".join(_lit(x) for x in val) + ")" if op in ("IN", "NOT IN") else _lit(val)
        where.append(f"{d['expr']} {op} {rhs}")

    sql = "SELECT " + ", ".join(selects) + f"\nFROM {cfg['meta']['fact_table']} f"
    for j in joins.values():
        sql += f"\nJOIN {j['table']} {j['alias']} ON {j['cond']}"
    if where:
        sql += "\nWHERE " + " AND ".join(where)
    if group_by:
        sql += "\nGROUP BY " + ", ".join(str(i + 1) for i in range(len(group_by)))
    if order_by:
        if order_by not in group_by + names:
            raise ValueError("order_by має бути виміром або метрикою із запиту")
        sql += f"\nORDER BY {order_by}"
    elif group_by:
        sql += "\nORDER BY " + ", ".join(str(i + 1) for i in range(len(group_by)))
    if limit:
        sql += f"\nLIMIT {int(limit)}"
    return sql


def describe(name: str) -> str:
    m = get_metric(name)
    return "\n".join(f"{k}: {v}" for k, v in m.items())


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("metric", nargs="+")
    p.add_argument("--by", action="append", default=[])
    a = p.parse_args()
    print(metric_sql(a.metric, group_by=a.by))
