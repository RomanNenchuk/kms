"""Підходи до рекомендацій. Інтерфейс: fit(ds, train) -> self; score(user_id) -> {doc_id: score}.
Порожній словник = підхід не знає користувача (холодний старт); fallback — у recommend()."""
from __future__ import annotations
import json, math
from collections import Counter, defaultdict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from . import config as C
from .data import graph_rows
from .taxonomy import ROLE_TOPICS, RISK_KIND_TOPICS


def _history(train):
    h = defaultdict(Counter)
    for e in train:
        w = C.EVENT_WEIGHT[e["event"]]
        if w > 0:
            h[e["user_id"]][e["doc_id"]] += w
    return h


class Random:
    """Нижня межа: детермінований «випадковий» порядок (seed + номер користувача)."""
    name = "random"
    def fit(self, ds, train):
        self.docs = sorted(ds.items); return self
    def score(self, user_id):
        rng = np.random.default_rng(C.SEED + int(user_id[1:]))
        return dict(zip(self.docs, rng.random(len(self.docs))))


class Popularity:
    """Зважена сума позитивних подій у train; однакова для всіх."""
    name = "pop"
    def fit(self, ds, train):
        self.cnt = Counter()
        for e in train:
            self.cnt[e["doc_id"]] += C.EVENT_WEIGHT[e["event"]]
        self.docs = sorted(ds.items); return self
    def score(self, user_id):
        return {d: float(self.cnt.get(d, 0.0)) for d in self.docs}
    def probs(self):
        tot = sum(self.cnt.values()) + len(self.docs)
        return {d: (self.cnt.get(d, 0.0) + 1.0) / tot for d in self.docs}


class RolePopularity:
    """Популярність серед користувачів тієї ж ролі (рішення холодного старту за атрибутом користувача)."""
    name = "role_pop"
    def fit(self, ds, train):
        self.ds, self.docs = ds, sorted(ds.items)
        self.cnt = defaultdict(Counter)
        for e in train:
            w = C.EVENT_WEIGHT[e["event"]]
            if w > 0:
                self.cnt[ds.users[e["user_id"]]["role"]][e["doc_id"]] += w
        return self
    def score(self, user_id):
        c = self.cnt[self.ds.users[user_id]["role"]]
        return {d: float(c.get(d, 0.0)) for d in self.docs} if c else {}


class ContentTfidf:
    """Контентний підхід: TF-IDF по тексту документів; профіль = зважена сума векторів документів з історії."""
    name = "content"
    def fit(self, ds, train):
        text = defaultdict(list)
        for line in open(C.KB_CORPUS, encoding="utf-8"):
            r = json.loads(line)
            text[r["doc_id"]].append(r["text"])
        self.docs = sorted(ds.items)
        txt = {d: ds.items[d]["title"] + ". " + " ".join(text[d]) for d in self.docs}
        known = [d for d in self.docs if ds.items[d]["published_at"] <= ds.cutoff]   # IDF лише з опублікованих до cutoff
        vec = TfidfVectorizer(stop_words="english", sublinear_tf=True, min_df=2, max_df=0.8).fit([txt[d] for d in known])
        M = vec.transform([txt[d] for d in self.docs])                              # L2-нормовані рядки
        self.vec = dict(zip(self.docs, M.toarray()))
        self.hist = _history(train); return self
    def score(self, user_id):
        h = self.hist.get(user_id)
        if not h:
            return {}
        p = sum(w * self.vec[d] for d, w in h.items()); n = np.linalg.norm(p)
        if n == 0:
            return {}
        p = p / n
        return {d: float(self.vec[d] @ p) for d in self.docs}


class EmbedE5:
    """Додатковий контентний підхід: вектор документа = нормоване середнє e5-векторів фрагментів (з ЛР 10/11)."""
    name = "embed"
    def fit(self, ds, train):
        d = json.loads(C.E5_JSON.read_text(encoding="utf-8"))
        emb = np.load(C.E5_NPY).astype("float32")
        by = defaultdict(list)
        for ch, v in zip(d["chunks"], emb):
            by[ch["doc_id"]].append(v)
        self.docs = sorted(ds.items)
        M = np.stack([np.mean(by[x], axis=0) for x in self.docs])
        M /= np.linalg.norm(M, axis=1, keepdims=True)
        self.vec = dict(zip(self.docs, M))
        self.hist = _history(train); return self
    def score(self, user_id):
        h = self.hist.get(user_id)
        if not h:
            return {}
        p = sum(w * self.vec[d] for d, w in h.items()); p = p / np.linalg.norm(p)
        return {d: float(self.vec[d] @ p) for d in self.docs}


class GraphReco:
    """Граф-базований підхід: вага теми = роль + (експозиція авіакомпанії до ризиків) + власна історія;
    оцінка документа = середня вага його тем (шляхи User→Role→Topic←Doc тощо).
    use_exposure=False — лише факти, відомі на момент cutoff. У графі ЛР 16 зв'язки «рейс—ризик» мають
    validFrom = 2026-11-02/03, тобто ПІЗНІШЕ за cutoff 2026-10-26, тому варіант з експозицією містить інформацію з майбутнього."""
    def __init__(self, use_exposure=False):
        self.use_exposure = use_exposure
        self.name = "graph_expo" if use_exposure else "graph"
    def fit(self, ds, train):
        self.ds = ds
        self.risks = {r["riskId"]: r for r in graph_rows("risks.csv")}
        fl_air = {r["startId"]: r["endId"] for r in graph_rows("rel_operated_by.csv")}
        self.expo = defaultdict(Counter)
        for r in graph_rows("rel_affected_by.csv"):
            self.expo[fl_air[r["startId"]]][r["endId"]] += 1
        self.hist = _history(train); return self
    def topic_weights(self, user_id):
        u = self.ds.users[user_id]
        comps = {"role": {t: 1.0 for t in ROLE_TOPICS[u["role"]]}, "history": defaultdict(float)}
        for doc, w in self.hist.get(user_id, {}).items():
            for t in self.ds.items[doc]["topics"]:
                comps["history"][t] += w
        if self.use_exposure:
            ex = Counter()
            for risk, n in self.expo[u["airline"]].items():
                for t in RISK_KIND_TOPICS[self.risks[risk]["kind"]]:
                    ex[t] += n
            comps["exposure"] = ex
        tw = Counter()
        for raw in comps.values():
            mx = max(raw.values(), default=0)
            for t, v in raw.items():
                tw[t] += v / mx if mx else 0.0
        return tw
    def score(self, user_id):
        tw = self.topic_weights(user_id)
        return {d: sum(tw[t] for t in it["topics"]) / len(it["topics"]) for d, it in self.ds.items.items()}


def rank(model, user_id, cands, k=10, fallback=None):
    """Упорядкований top-k серед кандидатів. Якщо модель не знає користувача — fallback (або порожній список)."""
    s = model.score(user_id)
    if not s and fallback is not None:
        s = fallback.score(user_id)
    order = sorted((d for d in cands if d in s), key=lambda d: (-s[d], d))
    return order[:k]


def build(ds, train):
    """Усі моделі, навчені на train."""
    return {m.name: m.fit(ds, train) for m in
            (Random(), Popularity(), RolePopularity(), ContentTfidf(), EmbedE5(), GraphReco(False), GraphReco(True))}
