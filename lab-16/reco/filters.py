"""Фільтри якості та прав доступу. Застосовуються ДО ранжування (як pre-filter у vector_search ЛР 11)."""
import datetime as dt
from . import config as C


def apply_filters(user, item_ids, ds, as_of: str, p: C.FilterParams, seen=frozenset()):
    """Повертає (kept, dropped): dropped = {doc_id: причина}. Причини: not_published_yet, not_verified, stale, access_denied, seen."""
    today = dt.date.fromisoformat(as_of)
    kept, dropped = [], {}
    for d in item_ids:
        it = ds.items[d]
        if dt.date.fromisoformat(it["published_at"]) > today:
            dropped[d] = "not_published_yet"
        elif p.require_verified and not it["verified"]:
            dropped[d] = "not_verified"
        elif (today - dt.date.fromisoformat(it["last_reviewed"])).days > p.max_age_days:
            dropped[d] = "stale"
        elif p.enforce_access and C.ACCESS_RANK[it["sensitivity"]] > C.ACCESS_RANK[user["access_level"]]:
            dropped[d] = "access_denied"
        elif p.exclude_seen and d in seen:
            dropped[d] = "seen"
        else:
            kept.append(d)
    return kept, dropped
