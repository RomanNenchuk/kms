"""Будує dashboard/index.html: 5 питань -> 5 візуалізацій з інтерпретаціями (дані через семантичний шар).
Запуск: python dashboard/build.py
"""
import html
import sys
from pathlib import Path

import duckdb
import plotly.express as px
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "semantic"))
from metrics import metric_sql  # noqa: E402

con = duckdb.connect(str(ROOT / "data" / "hub.duckdb"), read_only=True)
SEASONS = ["Winter", "Spring", "Summer", "Autumn"]
UA_SEASON = {"Winter": "зима", "Spring": "весна", "Summer": "літо", "Autumn": "осінь"}
MONTHS_UA = ["січень", "лютий", "березень", "квітень", "травень", "червень", "липень", "серпень", "вересень", "жовтень", "листопад", "грудень"]


def n(x):
    return f"{int(x):,}".replace(",", "\u00a0")


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
LAYOUT = dict(margin=dict(l=50, r=20, t=30, b=50), height=380, font=dict(family="system-ui, sans-serif", size=13),
              plot_bgcolor="white", paper_bgcolor="white")
panels = []  # (питання, SQL, фігура, інтерпретація)

# 1. Вчасність за авіакомпаніями
sql1 = metric_sql(["on_time_rate", "flights_count"], group_by=["airline_type", "airline"])
d = con.execute(sql1).df().sort_values("on_time_rate")
fig = px.bar(d, x="on_time_rate", y="airline", color="airline_type", orientation="h", text=d["on_time_rate"].round(1),
             labels={"on_time_rate": "Вчасні рейси, %", "airline": "", "airline_type": "Тип"})
fig.update_layout(**LAYOUT)
best, worst = d.iloc[-1], d.iloc[0]
panels.append(("Яка частка рейсів виконується вчасно в кожної авіакомпанії?", sql1, fig,
    f"Найвища частка вчасних рейсів у {best['airline']} ({best['on_time_rate']:.1f} %), найнижча у {worst['airline']} "
    f"({worst['on_time_rate']:.1f} %). Різниця {best['on_time_rate'] - worst['on_time_rate']:.1f} п.п. при вибірках "
    f"{int(d['flights_count'].min())}–{int(d['flights_count'].max())} рейсів: вона невелика, тому сильних висновків про якість перевізників робити не варто."))

# 2. Хвилини затримки: сезон × клас причини
sql2 = metric_sql("total_delay_min", group_by=["season", "cause_class"],
                  filters=[("cancelled", "=", 0), ("cause_class", "<>", "No delay")])
d = con.execute(sql2).df()
fig = px.bar(d, x="season", y="total_delay_min", color="cause_class", category_orders={"season": SEASONS},
             labels={"total_delay_min": "Сумарна затримка, хв", "season": "", "cause_class": "Клас причини"})
fig.update_layout(**LAYOUT)
tot = d.groupby("season")["total_delay_min"].sum()
atc_c = d[d.cause_class.str.contains("Air traffic|ATC", case=False)].set_index("season")["total_delay_min"]
extra = f" Внесок ATC літом у {atc_c['Summer'] / atc_c['Winter']:.1f} раза вищий, ніж узимку." if len(atc_c) == 4 else ""
panels.append(("Як розподіляються хвилини затримки за порою року та причинами?", sql2, fig,
    f"Найбільше затримок припадає на сезон «{UA_SEASON[tot.idxmax()]}» ({n(tot.max())} хв), найменше — «{UA_SEASON[tot.idxmin()]}» ({n(tot.min())} хв)."
    f"{extra} Структура причин змінюється за сезонами: погода домінує взимку, завантаженість ATC зростає влітку."))

# 3. Пасажиропотік за місяцями
sql3 = metric_sql("passengers", group_by=["month"])
d = con.execute(sql3).df()
d["cum_pct"] = d["passengers"].cumsum() / d["passengers"].sum() * 100
fig = go.Figure()
fig.add_bar(x=MONTHS, y=d["passengers"], name="Пасажири за місяць")
fig.add_scatter(x=MONTHS, y=d["cum_pct"], name="Накопичено, %", yaxis="y2", mode="lines+markers")
fig.update_layout(**LAYOUT, yaxis=dict(title="Пасажири"), yaxis2=dict(title="Накопичено, %", overlaying="y", side="right", range=[0, 100]),
                  legend=dict(orientation="h", y=1.12))
pk, lo = d.loc[d.passengers.idxmax()], d.loc[d.passengers.idxmin()]
panels.append(("Як змінюється пасажиропотік протягом року?", sql3, fig,
    f"Пік — {MONTHS_UA[int(pk['month']) - 1]} ({n(pk['passengers'])} пасажирів), мінімум — {MONTHS_UA[int(lo['month']) - 1]} ({n(lo['passengers'])}). "
    f"До кінця червня накопичено {d.loc[d.month == 6, 'cum_pct'].iloc[0]:.1f} % річного потоку: навантаження зміщене на другу половину року."))

# 4. Погодні причини: підклас × сезон
sql4 = metric_sql("flights_count", group_by=["cause_subclass", "season"], filters=[("cause_class", "=", "Weather")])
d = con.execute(sql4).df().pivot(index="cause_subclass", columns="season", values="flights_count").fillna(0)[SEASONS]
fig = px.imshow(d, text_auto=True, aspect="auto", color_continuous_scale="Blues",
                labels={"x": "", "y": "", "color": "Рейсів"})
fig.update_layout(**LAYOUT)
top = {s: d[s].idxmax() for s in SEASONS}
panels.append(("Які погодні причини домінують у різні пори року?", sql4, fig,
    "Найчастіша погодна причина за сезонами: " + ", ".join(f"{UA_SEASON[s]} — {top[s]} ({int(d.loc[top[s], s])})" for s in SEASONS) +
    ". Профіль ризику сильно сезонний: влітку грози, взимку сніг/лід і туман, а сильний вітер розподілений рівномірно."))

# 5. Завантаження за типом літака
sql5 = metric_sql(["load_factor", "flights_count"], group_by=["aircraft_type"])
d = con.execute(sql5).df().sort_values("load_factor")
fig = px.bar(d, x="aircraft_type", y="load_factor", text=d["load_factor"].round(1),
             labels={"load_factor": "Завантаження, %", "aircraft_type": ""})
fig.update_layout(**LAYOUT)
panels.append(("Наскільки заповнені літаки різних типів?", sql5, fig,
    f"Найвищий коефіцієнт завантаження у {d.iloc[-1]['aircraft_type']} ({d.iloc[-1]['load_factor']:.1f} %), найнижчий у "
    f"{d.iloc[0]['aircraft_type']} ({d.iloc[0]['load_factor']:.1f} %). Розбіжність між типами {d.iloc[-1]['load_factor'] - d.iloc[0]['load_factor']:.1f} п.п.; "
    "завантаження рахується лише для нескасованих рейсів."))

sections = []
for i, (q, sql, fig, text) in enumerate(panels):
    chart = fig.to_html(full_html=False, include_plotlyjs=True if i == 0 else False, config={"displayModeBar": False})
    sections.append(f"""<section><h2>{i + 1}. {html.escape(q)}</h2>{chart}
<p class="interp"><strong>Інтерпретація.</strong> {html.escape(text)}</p>
<details><summary>SQL із семантичного шару</summary><pre>{html.escape(sql)}</pre></details></section>""")

page = f"""<!doctype html><html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Авіаперевезення: аналітична панель</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:980px;margin:0 auto;padding:24px;color:#1a1a1a;background:#fafafa}}
section{{background:#fff;border:1px solid #e3e3e3;border-radius:10px;padding:16px 20px;margin:18px 0}}
h1{{margin-bottom:4px}} h2{{font-size:1.1rem}} .interp{{background:#f4f7fb;border-left:4px solid #4b7bec;padding:10px 12px;border-radius:4px}}
pre{{overflow-x:auto;background:#f3f3f3;padding:10px;border-radius:6px;font-size:.8rem}} .note{{color:#666}}
</style></head><body>
<h1>Авіаперевезення: аналітична панель</h1>
<p class="note">ЛР 12 · синтетичні дані (5000 рейсів, 2025 рік) · усі показники обчислено через семантичний шар (semantic/metrics.yml).</p>
{''.join(sections)}
</body></html>"""
out = ROOT / "dashboard" / "index.html"
out.write_text(page, encoding="utf-8")
print(f"Збережено {out} ({out.stat().st_size // 1024} КБ), візуалізацій: {len(panels)}")
for q, _, _, t in panels:
    print("-", q, "\n   ", t)
