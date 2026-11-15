"""Streamlit-інтерфейс демонстратора Aviation Knowledge Hub (ЛР 16)."""
import json, os, pathlib
import httpx
import streamlit as st

API = os.getenv("RECO_API_URL", "http://localhost:8000")
ROOT = pathlib.Path(__file__).resolve().parent.parent
st.set_page_config(page_title="Aviation Knowledge Hub", layout="wide")
st.title("Aviation Knowledge Hub")
st.caption("Управління авіаційними перевезеннями · рекомендації, пошук у базі знань, граф · дані синтетичні")


def call(method, path, **kw):
    try:
        r = httpx.request(method, f"{API}{path}", timeout=60, **kw)
        return r.status_code, r.json()
    except Exception as e:  # noqa: BLE001
        return 0, {"error": f"API недоступне: {e}"}


code, users = call("GET", "/users")
if code != 200:
    st.error(users); st.stop()
by_id = {u["user_id"]: u for u in users}
tab1, tab2, tab3, tab4 = st.tabs(["Рекомендації", "Питання до бази знань", "Граф і Cypher", "Результати оцінки"])

with tab1:
    c1, c2, c3, c4 = st.columns(4)
    uid = c1.selectbox("Користувач", list(by_id), format_func=lambda x: f"{x} · {by_id[x]['role']} · {by_id[x]['cohort']} · {by_id[x]['access_level']}")
    method = c2.selectbox("Підхід", ["hybrid", "graph", "embed", "pop"])
    k = c3.slider("Скільки", 1, 10, 5)
    flt = c4.checkbox("Фільтри якості й прав", True)
    llm = st.checkbox("Перефразувати пояснення через Gemini (потрібен ключ; з автоперевіркою)", False)
    code, out = call("GET", f"/recommend/{uid}", params={"method": method, "k": k, "filters": flt, "llm": llm})
    if code != 200:
        st.error(out)
    else:
        u = by_id[uid]
        st.write(f"**{uid}** · роль: {u['role']} · авіакомпанія: {u['airline']} · доступ: {u['access_level']} · "
                 f"{'є історія' if out['has_history'] else '**новий користувач (холодний старт)**'}")
        for it in out["items"]:
            with st.container(border=True):
                st.markdown(f"**{it['rank']}. {it['title']}** · оцінка {it['score']}")
                if it.get("explanation"):
                    ex = it["explanation"]
                    st.write(ex["text"] + ("" if ex["check_ok"] else "  ⚠️ автоперевірка не пройдена"))
                    st.caption(f"джерело пояснення: {ex['source']}")
                if it.get("path") and it["path"].get("steps"):
                    st.code(" → ".join([it["path"]["steps"][0][0]] + [s[2] for s in it["path"]["steps"]]), language=None)
        if out["dropped"]:
            with st.expander(f"Відфільтровано {len(out['dropped'])} документів"):
                st.json(out["dropped"])

with tab2:
    st.write("Пошук у базі знань (36 статей, англійською). Відповідь — уривок документа з цитатою; якщо теми немає — «не знаю».")
    q = st.text_input("Питання", "What is an airport slot?")
    uid2 = st.selectbox("Від імені користувача (визначає рівень доступу)", [""] + list(by_id), key="ask_user")
    if st.button("Запитати"):
        code, r = call("GET", "/ask", params={"q": q, **({"user_id": uid2} if uid2 else {})})
        status = r.get("status")
        if status == "ANSWER":
            st.success(r["answer"]); st.caption("Цитати: " + ", ".join(c["id"] for c in r["citations"]))
        elif status == "NO_ANSWER":
            st.warning(f"Не знаю: у базі знань немає відповіді (причина: {r['reason']}).")
        elif status == "REFUSED":
            st.error(f"Запит відхилено: ознаки prompt injection ({', '.join(r['flags'])}).")
        else:
            st.json(r)
        with st.expander("Сира відповідь API"):
            st.json(r)

with tab3:
    ent = st.text_input("Сутність у графі", "Lviv")
    if st.button("Знайти в графі"):
        code, r = call("GET", "/graph", params={"entity": ent})
        st.json({k: r.get(k) for k in ("found", "seeds", "direct_relations")} if r.get("found") else r)
    st.divider()
    st.write("Cypher лише для читання; Passenger/Pilot недоступні рівню `public`.")
    cy = st.text_area("Cypher", "MATCH (a:Airline)<-[:OPERATED_BY]-(f:Flight) RETURN a.name AS airline, count(f) AS flights ORDER BY flights DESC")
    uid3 = st.selectbox("Від імені користувача", [""] + list(by_id), key="cy_user")
    if st.button("Виконати"):
        code, r = call("POST", "/cypher", json={"query": cy, "user_id": uid3 or None})
        (st.error(f"Заблоковано: {r['error']}") if r.get("blocked") else st.json(r))

with tab4:
    for name, title in [("eval_table.md", "Офлайн-оцінка (Результат 2)"), ("cold_start_table.md", "Холодний старт (Результат 3)")]:
        p = ROOT / "reports" / name
        if p.exists():
            st.subheader(title); st.markdown(p.read_text(encoding="utf-8"))
    for img in ("fig_accuracy.png", "fig_diversity.png", "fig_cold_start.png"):
        if (ROOT / "reports" / img).exists():
            st.image(str(ROOT / "reports" / img))
