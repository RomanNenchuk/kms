#!/usr/bin/env python3
"""Збирає docs/whitepaper.pdf: рисунки -> підстановка таблиці тверджень із claims/claims.csv (+ _append_*.csv) -> pandoc + xelatex.
Запуск: python scripts/build_whitepaper.py   (потрібні pandoc, xelatex, шрифти DejaVu)"""
import csv, glob, pathlib, re, subprocess, sys, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
rows, seen = [], set()
files = [ROOT / "claims/claims.csv"]
main = list(csv.DictReader(open(files[0], encoding="utf-8")))
for r in main:
    seen.add(r["id"]); rows.append(r)
for f in sorted(glob.glob(str(ROOT / "claims/_append_*.csv"))):      # якщо додатки ще не дописані в claims.csv
    for c in csv.reader(open(f, encoding="utf-8")):
        if len(c) >= 7 and c[0] not in seen:
            seen.add(c[0]); rows.append(dict(zip(["id", "claim", "type", "source", "verification_level", "status", "comment"], c[:7])))
rows.sort(key=lambda r: r["id"])
st = collections.Counter(r["status"] for r in rows)
tot = len(rows)
stats = (f"{tot} тверджень: verified — {st.get('verified', 0)} ({st.get('verified', 0) / tot:.0%}), rejected — {st.get('rejected', 0)}, "
         f"pending — {st.get('pending', 0)}") if tot else "таблицю тверджень не знайдено"


def esc(s):
    return re.sub(r"\s+", " ", s.replace("|", "/")).strip()


# топ-20: спершу ті, що вже мають статус verified/rejected, далі за id
pick = sorted(rows, key=lambda r: (r["status"] == "pending", r["id"]))[:20]
pick.sort(key=lambda r: r["id"])
tbl = ["\\begingroup\\footnotesize", "", "| id | Твердження | Тип | Рів. | Статус |", "|----|------------------------------------------|-----------|---|--------|"]
for r in pick:
    tbl.append(f"| {r['id']} | {esc(r['claim'])[:230]} | {r['type']} | {r['verification_level']} | {r['status']} |")
src = (ROOT / "docs/whitepaper.md").read_text(encoding="utf-8")
src = src.replace("{{CLAIMS_STATS}}", stats).replace("{{CLAIMS_TABLE}}", "\n".join(tbl) + "\n\n: Топ-20 тверджень із claims/claims.csv\n\n\\endgroup\n")
subprocess.run([sys.executable, str(ROOT / "scripts/wp_figures.py")], check=True, cwd=ROOT)
tmp = ROOT / "docs/_whitepaper_build.md"; tmp.write_text(src, encoding="utf-8")
cmd = ["pandoc", "-f", "markdown-smart", str(tmp), "-o", str(ROOT / "docs/whitepaper.pdf"), "--pdf-engine=xelatex", "-V", "geometry:a4paper,margin=2.2cm", "--resource-path", str(ROOT / "docs")]
subprocess.run(cmd, check=True, cwd=ROOT / "docs"); tmp.unlink()
print("OK:", ROOT / "docs/whitepaper.pdf", "|", stats)
