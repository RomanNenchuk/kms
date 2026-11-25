"""C4: кожен із 5 запитів зі схеми v1 збігається з незалежним обчисленням у pandas."""
import pandas as pd
import pytest

from run_queries import run_all


@pytest.fixture(scope="module")
def res(con):
    return run_all(con)


@pytest.fixture(scope="module")
def wide(frames):
    f = frames["fact_flight"]
    f = f.merge(frames["dim_date"], on="date_key")
    f = f.merge(frames["dim_airline"], on="airline_key", suffixes=("", "_al"))
    f = f.merge(frames["dim_aircraft"], on="aircraft_key", suffixes=("", "_ac"))
    f = f.merge(frames["dim_delay_cause"], on="delay_cause_key")
    return f


def test_q1_load_factor(res, wide):
    exp = (wide[wide.cancelled == 0].groupby(["airline_type", "quarter"])
           .agg(p=("passengers", "sum"), s=("seats", "sum")).reset_index())
    exp["lf"] = (100 * exp.p / exp.s).round(2)
    got = res["q1_load_factor"]
    assert len(got) == len(exp) == 12
    m = got.merge(exp, on=["airline_type", "quarter"])
    assert (m.load_factor_pct - m.lf).abs().max() < 1e-9
    assert ((got.load_factor_pct > 0) & (got.load_factor_pct <= 100)).all()


def test_q2_delay_causes(res, wide):
    got = res["q2_delay_causes"]
    d = wide[wide.class_label != "No delay"]
    sub = got[got.class_label.notna() & got.subclass_label.notna()]
    exp = d.groupby(["class_label", "subclass_label"]).delay_minutes.sum().reset_index()
    m = sub.merge(exp, on=["class_label", "subclass_label"])
    assert len(m) == len(exp) and (m.delay_min == m.delay_minutes).all()
    cls = got[got.class_label.notna() & got.subclass_label.isna()].set_index("class_label").delay_min
    assert (cls == d.groupby("class_label").delay_minutes.sum()).all()
    total = got[got.class_label.isna()].delay_min.iloc[0]
    assert total == d.delay_minutes.sum()                                   # ROLLUP: підсумки сходяться


def test_q3_top_routes(res, frames):
    f = frames["fact_flight"]
    a = frames["dim_airport"].set_index("airport_key")
    f = f.assign(o=f.origin_airport_key.map(a.iata), d=f.dest_airport_key.map(a.iata))
    exp = f.groupby(["o", "d"]).revenue_usd.sum().sort_values(ascending=False).head(10)
    got = res["q3_top_routes"]
    assert list(zip(got.origin, got.destination)) == list(exp.index)
    assert ((got.revenue_usd - exp.values.round()).abs() < 1).all()


def test_q4_on_time_by_hub(res, wide, frames):
    a = frames["dim_airport"].set_index("airport_key")
    w = wide.assign(is_hub_o=wide.origin_airport_key.map(a.is_hub),
                    ok=((wide.cancelled == 0) & (wide.delay_minutes <= 14)).astype(int))
    exp = w.groupby(["month", "is_hub_o"]).agg(n=("ok", "size"), ok=("ok", "sum")).reset_index()
    got = res["q4_on_time_hub"]
    assert len(got) == len(exp) == 24
    m = got.merge(exp, left_on=["month", "is_hub"], right_on=["month", "is_hub_o"])
    assert (m.flights == m.n).all() and (m.on_time == m.ok).all()
    assert ((m.on_time_pct - (100 * m.ok / m.n).round(1)).abs() < 1e-9).all()
    assert got.flights.sum() == 5000


def test_q5_scd2_seats(res, wide, frames):
    ac = frames["dim_aircraft"]
    cur = ac[ac.is_current].set_index("registration").seats
    w = wide.assign(cur_seats=wide.registration.map(cur))
    exp = w.groupby(["manufacturer", "aircraft_type"]).agg(fl=("seats", "size"), h=("seats", "sum"), c=("cur_seats", "sum")).reset_index()
    got = res["q5_seats_scd2"]
    leaf = got[got.manufacturer.notna() & got.aircraft_type.notna()]
    m = leaf.merge(exp, on=["manufacturer", "aircraft_type"])
    assert len(m) == len(exp)
    assert (m.flights == m.fl).all() and (m.seats_at_flight_date == m.h).all() and (m.seats_if_current == m.c).all()
    assert got[got.manufacturer.isna()].seats_at_flight_date.iloc[0] == w.seats.sum()
    assert (got.error_if_current != 0).any(), "SCD2 має давати відмінність від «лише поточної версії»"
