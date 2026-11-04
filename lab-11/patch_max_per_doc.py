import pathlib

p = pathlib.Path("src/rag.py")
s = p.read_text(encoding="utf-8")
if "max_per_doc" in s:
    raise SystemExit("вже застосовано")
repl = [
    ('        self.seed = int(os.getenv("SEED", SEED))\n',
     '        self.seed = int(os.getenv("SEED", SEED))\n'
     '        self.max_per_doc = int(os.getenv("MAX_PER_DOC", "0")) or None   # Результат 5: ліміт контекстів з одного документа\n'),
    ('        cands, seen = [], set()\n', '        cands, seen, per_doc = [], set(), {}\n'),
    ('            seen.add(c["context"])\n            cands.append(c)\n',
     '            if self.max_per_doc and per_doc.get(c["doc_id"], 0) >= self.max_per_doc:\n'
     '                continue                                   # ліміт контекстів з одного документа\n'
     '            seen.add(c["context"])\n            per_doc[c["doc_id"]] = per_doc.get(c["doc_id"], 0) + 1\n            cands.append(c)\n'),
    ('"params": {"temperature": self.temperature, "seed": self.seed}',
     '"params": {"temperature": self.temperature, "seed": self.seed, "max_per_doc": self.max_per_doc}'),
]
for old, new in repl:
    assert s.count(old) == 1, f"якір знайдено {s.count(old)} раз(и): {old[:45]!r}"
    s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
print("патч застосовано")
