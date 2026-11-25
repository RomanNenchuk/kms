"""Три недоліки чернетки v0 справді проявляються на даних, а v1 їх не має."""
import pytest

import flaws


@pytest.fixture(scope="module")
def r(con):
    return flaws.measure(con)


def test_grain_mixed_rows_double_the_sum(r):
    assert r["grain"]["summary_rows"] > 0
    assert r["grain"]["inflation_x"] == pytest.approx(2.0, abs=1e-9)


def test_natural_key_join_fans_out(r):
    assert r["keys"]["rows_after_join"] > r["keys"]["fact_rows"]
    assert r["keys"]["inflation_pct"] > 20


def test_v1_join_through_surrogate_key_does_not_fan_out(con):
    n, pax = con.execute("""SELECT COUNT(*), SUM(f.passengers) FROM fact_flight f
                            JOIN dim_aircraft a ON f.aircraft_key = a.aircraft_key""").fetchone()
    assert n == 5000 and pax == r_true(con)


def r_true(con):
    return con.execute("SELECT SUM(passengers) FROM fact_flight").fetchone()[0]


def test_semi_additive_counter_is_overcounted_when_summed(r):
    assert r["additivity"]["airframe_overcount_x"] > 10


def test_average_of_ratios_differs_from_ratio_of_sums(r):
    assert max(abs(x["diff_pp"]) for x in r["additivity"]["on_time_by_type"]) > 1.0
