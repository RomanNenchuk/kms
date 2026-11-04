"""Тести ключів, ролей і ліміту (без FastAPI): pytest tests/test_security.py"""
import pytest
from api.security import KeyStore, RateLimiter, hash_key, Principal


def store():
    return KeyStore(",".join(f"{hash_key(k)}:{r}" for k, r in [("k-view", "viewer"), ("k-an", "analyst"), ("k-adm", "admin")]))


def test_authenticate_roles():
    s = store()
    assert s.authenticate("k-view").role == "viewer"
    assert s.authenticate("k-adm").level == "restricted"
    assert s.authenticate("wrong") is None and s.authenticate(None) is None and s.authenticate("") is None


def test_levels_and_graph():
    v, a, d = (store().authenticate(k) for k in ("k-view", "k-an", "k-adm"))
    assert [p.may_read(x) for p in (v, a, d) for x in ("public", "internal", "restricted")] == \
           [True, False, False, True, True, False, True, True, True]
    assert not v.may_read("unknown") and d.may_read("unknown")            # невідома чутливість = restricted
    assert (v.can_graph, a.can_graph, d.can_graph) == (False, True, True)


def test_bad_config_fails_fast():
    for bad in ["", "abc:viewer", f"{hash_key('x')}:root", f"{hash_key('x')}"]:
        with pytest.raises(ValueError):
            KeyStore(bad)


def test_plaintext_not_stored():
    s = store()
    assert all("k-" not in h for h, _ in s.entries)


def test_rate_limiter_window():
    r = RateLimiter(window_s=60)
    assert [r.hit("a", 3, now=t)[0] for t in (0, 1, 2)] == [True, True, True]
    ok, rem, retry = r.hit("a", 3, now=3)
    assert (ok, rem) == (False, 0) and 55 <= retry <= 60
    assert r.hit("b", 3, now=3)[0]                                         # інший ключ незалежний
    assert r.hit("a", 3, now=61)[0]                                        # вікно зсунулось
