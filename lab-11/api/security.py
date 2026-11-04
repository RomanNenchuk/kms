"""Автентифікація за API-ключем, ролі та ліміти запитів. Без залежностей від FastAPI (тестується окремо).

Ключі зберігаються в .env як SHA-256 хеші: API_KEYS="<sha256hex>:<role>,<sha256hex>:<role>".
Відкритий ключ знає лише клієнт; його можна згенерувати командою `python scripts/gen_api_keys.py`.
Рівень доступу до документів визначається РОЛЛЮ ключа на сервері, клієнт передати його не може.
"""
import hashlib
import hmac
import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

LEVELS = {"public": 0, "internal": 1, "restricted": 2}                 # узгоджено з src/rag.py
ROLE_LEVEL = {"viewer": "public", "analyst": "internal", "admin": "restricted"}
GRAPH_ROLES = {"analyst", "admin"}          # операційні дані рейсів з графа — не для публічної ролі
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Principal:
    role: str
    key_id: str                              # перші 8 символів хеша: для журналу, не секрет

    @property
    def level(self) -> str:
        return ROLE_LEVEL[self.role]

    @property
    def can_graph(self) -> bool:
        return self.role in GRAPH_ROLES

    def may_read(self, sensitivity: str) -> bool:
        return LEVELS.get(sensitivity, 2) <= LEVELS[self.level]      # невідома чутливість = restricted


class KeyStore:
    def __init__(self, spec: str):
        self.entries = []                                            # [(hash, role)]
        for part in filter(None, (p.strip() for p in (spec or "").split(","))):
            h, _, role = part.partition(":")
            if not _HASH_RE.match(h) or role not in ROLE_LEVEL:
                raise ValueError(f"API_KEYS: некоректний запис (очікую <sha256hex>:<{'|'.join(ROLE_LEVEL)}>)")
            self.entries.append((h, role))
        if not self.entries:
            raise ValueError("API_KEYS порожній: сервіс без ключів не запускаємо")

    def authenticate(self, key: str | None) -> Principal | None:
        if not key or len(key) > 200:
            return None
        h, found = hash_key(key), None
        for stored, role in self.entries:                            # перебираємо всі, щоб час не залежав від збігу
            if hmac.compare_digest(h, stored):
                found = Principal(role=role, key_id=stored[:8])
        return found


class RateLimiter:
    """Ковзне вікно в пам'яті процесу (достатньо для одного воркера; для кількох потрібен Redis)."""

    def __init__(self, window_s: float = 60.0):
        self.window = window_s
        self.hits = defaultdict(deque)
        self.lock = threading.Lock()

    def hit(self, identity: str, limit: int, now: float | None = None):
        """-> (дозволено, залишок, секунд до наступного дозволеного запиту)."""
        now = time.monotonic() if now is None else now
        with self.lock:
            q = self.hits[identity]
            while q and now - q[0] >= self.window:
                q.popleft()
            if len(q) >= limit:
                return False, 0, max(1, int(self.window - (now - q[0]) + 0.999))
            q.append(now)
            return True, limit - len(q), 0
