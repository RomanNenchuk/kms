import pathlib

p = pathlib.Path("src/rag_eval.py")
s = p.read_text(encoding="utf-8")
if "н/д (немає негативних" in s:
    raise SystemExit("вже застосовано")
repl = [
    # 1) аркуш показує джерела повністю (раніше різалось до 900 символів, суддя ж бачив усе)
    ("{r['contexts'][i][:900]}", "{r['contexts'][i]}"),
    # 2) κ не визначений, якщо в одному з рядів усі оцінки однакові (парадокс каппи): не підміняємо його 0 чи 1
    ("k = 1.0 if pe == 1 and a == 1 else (0.0 if pe == 1 else (a - pe) / (1 - pe))",
     "k = None if pe == 1 else (a - pe) / (1 - pe)"),
    ('κ={k:.2f} {conf}")', 'κ={"н/д" if k is None else format(k, ".2f")} {conf}")'),
    ("Cohen κ = %.2f; матриця", "Cohen κ = %s; матриця"),
    ("kap['kappa'], kap['confusion'])",
     "('н/д (немає негативних оцінок: κ не визначений)' if kap['kappa'] is None else '%.2f' % kap['kappa']), kap['confusion'])"),
]
for old, new in repl:
    assert s.count(old) == 1, f"якір знайдено {s.count(old)} раз(и), очікувалось 1: {old[:50]}"
    s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
print("патч застосовано")