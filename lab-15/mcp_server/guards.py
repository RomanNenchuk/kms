"""Захисти, які не залежать від LLM: перевірка Cypher, права за мітками, сканування недовіреного тексту.

Це базовий рівень. У Результаті 4 вони є «захистом»: вимкніть через DEFENSES=off, щоб виміряти стан «до»."""
import re
from . import config

# --- Cypher ------------------------------------------------------------------
FORBIDDEN_CYPHER = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|FOREACH|LOAD\s+CSV|CALL|START|GRANT|DENY|REVOKE|ALTER|RENAME|TERMINATE)\b"
    r"|apoc\.|dbms\.", re.I)
DEFAULT_LIMIT = 50


def _strip_strings(q: str) -> str:
    return re.sub(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"", "''", q)   # не шукати ключові слова всередині рядків


def check_cypher(query: str, level: str | None = None) -> tuple[bool, str, str]:
    """Повертає (ok, reason, cypher_з_LIMIT). Лише читання, один оператор, RETURN обов'язковий."""
    level = level or config.ACCESS_LEVEL
    q = (query or "").strip().rstrip(";").strip()
    if not q:
        return False, "empty_query", q
    if ";" in _strip_strings(q):
        return False, "multiple_statements", q
    bare = _strip_strings(q)
    if config.DEFENSES:
        m = FORBIDDEN_CYPHER.search(bare)
        if m:
            return False, f"forbidden_keyword:{m.group(0).upper()}", q
    if not re.search(r"\bRETURN\b", bare, re.I):
        return False, "no_return", q
    if config.DEFENSES:
        for label, need in config.LABEL_LEVEL.items():                      # мітки з обмеженим доступом
            if re.search(rf":\s*`?{label}`?\b", bare) and config.LEVELS[level] < config.LEVELS[need]:
                return False, f"label_forbidden:{label}", q
        for rel, need in config.REL_LEVEL.items():
            if re.search(rf"\b{rel}\b", bare, re.I) and config.LEVELS[level] < config.LEVELS[need]:
                return False, f"relationship_forbidden:{rel}", q
        if not re.search(r"\bLIMIT\b", bare, re.I):
            q = f"{q}\nLIMIT {DEFAULT_LIMIT}"
    return True, "ok", q


def rows_allowed(rows, level: str | None = None) -> bool:
    """Пост-фільтр результату Cypher: у рядках не має бути ключів властивостей, закритих для цього рівня."""
    level = level or config.ACCESS_LEVEL
    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                yield from keys(v)
    bad = {k for k, need in config.PROP_LEVEL.items() if config.LEVELS[level] < config.LEVELS[need]}
    return not (bad & set(keys(rows)))


def label_allowed(label: str, level: str | None = None) -> bool:
    level = level or config.ACCESS_LEVEL
    need = config.LABEL_LEVEL.get(label, "public")
    return config.LEVELS[level] >= config.LEVELS[need]


# --- недовірений текст (непрямий prompt injection) -------------------------------
INJECTION_PATTERNS = [
    r"ignore (all |any )?(the )?(previous|prior|above) (instructions|prompts?)",
    r"disregard (all |any )?(the )?(previous|prior|above|system)",
    r"(reveal|print|show|repeat) (your |the )?(system )?(prompt|instructions)",
    r"you are now\b",
    r"\bnew (system )?instructions?\s*:",
    r"(call|invoke|use|run) the (tool|function)\b",
    r"ігноруй (усі |всі )?(попередні|вищевказані) (інструкції|команди)",
    r"забудь (усі |всі )?(попередні )?інструкції",
    r"(покажи|виведи|розкрий) (свій )?(системний )?(промпт|підказку)",
    r"<\s*/?\s*(system|tool_call|function_call)\s*>",
]
_INJ = re.compile("|".join(INJECTION_PATTERNS), re.I)


def scan_untrusted(text: str) -> list[str]:
    """Повертає знайдені ознаки ін'єкції (порожній список = нічого не знайдено). Евристика, не гарантія."""
    return sorted({m.group(0).lower()[:60] for m in _INJ.finditer(text or "")})


def wrap_untrusted(text: str, source_id: str) -> str:
    """Ізоляція контексту: модель бачить цей текст як ДАНІ, а не як інструкції (див. system-промпт агента)."""
    return f'<untrusted_document id="{source_id}">\n{text}\n</untrusted_document>'


# --- вихідний фільтр (витік даних і системної підказки) ---------------------------------
CANARY = "CANARY-4417-LVIV"          # службовий маркер у системній підказці: його поява у відповіді = витік підказки
_names_cache: dict | None = None


def _restricted_values() -> dict[str, set[str]]:
    """рівень -> значення, які не можна показувати нижчим рівням (імена пасажирів і пілотів)."""
    global _names_cache
    if _names_cache is None:
        import csv
        out = {"restricted": set(), "internal": set()}
        for fname, lvl, col in (("passengers.csv", "restricted", "name"), ("pilots.csv", "internal", "name")):
            f = config.GRAPH_DIR / fname
            if f.exists():
                with open(f, encoding="utf-8") as fh:
                    out[lvl] = {r[col].strip() for r in csv.DictReader(fh) if r.get(col, "").strip()}
        _names_cache = out
    return _names_cache


def _shingles(text: str, n: int = 8) -> set[tuple]:
    w = re.findall(r"\w+", text.lower())
    return {tuple(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


def output_leak(answer: str, level: str | None = None, system_text: str = "") -> list[str]:
    """Перевіряє ФІНАЛЬНУ відповідь перед віддачею користувачу. Повертає список причин (порожній = можна віддавати).
    Незалежний від LLM шар: ловить маркер підказки, 8-слівні уривки системної підказки, імена, закриті для рівня."""
    level = level or config.ACCESS_LEVEL
    reasons = []
    if CANARY.lower() in (answer or "").lower():
        reasons.append("system_prompt_canary")
    if system_text and _shingles(answer) & _shingles(system_text):
        reasons.append("system_prompt_fragment")
    vals = _restricted_values()
    for lvl, names in vals.items():
        if config.LEVELS[level] < config.LEVELS[lvl]:
            low = (answer or "").lower()
            hit = [n for n in names if n.lower() in low]
            if hit:
                reasons.append(f"restricted_value:{lvl}")
    return reasons
