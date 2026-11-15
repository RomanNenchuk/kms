"""Графовий підхід: ранжування документів за шляхами у графі знань.
Вузли: User, Role, Airline, Flight, Risk, Topic, Doc. Шляхи до документа через тему:
  роль:        User -HAS_ROLE-> Role -FOCUSES_ON-> Topic <-ABOUT- Doc
  експозиція:  User -WORKS_AT-> Airline <-OPERATED_BY- Flight -AFFECTED_BY-> Risk -RELEVANT_TO-> Topic <-ABOUT- Doc
  історія:     User -OPENED-> Doc' -ABOUT-> Topic <-ABOUT- Doc
Вага теми = alpha*role + beta*exposure + gamma*history (кожна компонента нормована на максимум = 1);
оцінка документа = середня вага його тем. Те саме на Cypher: reco/cypher.py."""
from collections import Counter, defaultdict
from . import config as C
from .data import graph_rows
from .taxonomy import ROLE_TOPICS, RISK_KIND_TOPICS


class GraphReco:
    name = "graph"

    def __init__(self, params: C.GraphParams | None = None):
        self.p = params or C.GraphParams()

    def fit(self, ds, train):
        self.ds = ds
        self.risks = {r["riskId"]: r for r in graph_rows("risks.csv")}
        flight_airline = {r["startId"]: r["endId"] for r in graph_rows("rel_operated_by.csv")}
        self.expo = defaultdict(Counter)          # airline -> Counter(risk_id) за рейсами
        self.example_flight = {}                  # (airline, risk) -> перший рейс (для пояснення шляхом)
        for r in sorted(graph_rows("rel_affected_by.csv"), key=lambda r: r["startId"]):
            a = flight_airline[r["startId"]]
            self.expo[a][r["endId"]] += 1
            self.example_flight.setdefault((a, r["endId"]), r["startId"])
        self.hist = defaultdict(Counter)          # user -> Counter(doc) з вагами подій
        for e in train:
            w = C.EVENT_WEIGHT[e["event"]]
            if w > 0:
                self.hist[e["user_id"]][e["doc_id"]] += w
        return self

    # --- вага тем за компонентами: {component: {topic: raw}}
    def components(self, user_id):
        u = self.ds.users[user_id]
        role = {t: 1.0 for t in ROLE_TOPICS[u["role"]]}
        expo = Counter()
        for risk, n in self.expo[u["airline"]].items():
            for t in RISK_KIND_TOPICS[self.risks[risk]["kind"]]:
                expo[t] += n
        hist = Counter()
        for doc, w in self.hist[user_id].items():
            for t in self.ds.items[doc]["topics"]:
                hist[t] += w
        return {"role": role, "exposure": dict(expo), "history": dict(hist)}

    def topic_weights(self, user_id):
        coef = {"role": self.p.alpha, "exposure": self.p.beta, "history": self.p.gamma}
        comps, tw, parts = self.components(user_id), Counter(), defaultdict(dict)
        for c, raw in comps.items():
            mx = max(raw.values(), default=0)
            for t, v in raw.items():
                parts[t][c] = coef[c] * v / mx
                tw[t] += coef[c] * v / mx
        return tw, parts

    def score(self, user_id, history=None):
        tw, _ = self.topic_weights(user_id)
        return {d: sum(tw[t] for t in it["topics"]) / len(it["topics"]) for d, it in self.ds.items.items()}

    def path(self, user_id, doc_id):
        """Найсильніший шлях до документа: [(src, rel, dst), ...] і компонента, яка його дала."""
        tw, parts = self.topic_weights(user_id)
        u = self.ds.users[user_id]
        best = max(((parts[t][c], c, t) for t in self.ds.items[doc_id]["topics"] for c in parts[t]),
                   default=None)
        if not best:
            return None
        _, comp, t = best
        end = [(f"Topic:{t}", "ABOUT^-1", f"Doc:{doc_id}")]
        if comp == "role":
            steps = [(f"User:{user_id}", "HAS_ROLE", f"Role:{u['role']}"), (f"Role:{u['role']}", "FOCUSES_ON", f"Topic:{t}")]
        elif comp == "exposure":
            risks = [r for r in self.expo[u["airline"]] if t in RISK_KIND_TOPICS[self.risks[r]["kind"]]]
            r = max(risks, key=lambda r: (self.expo[u["airline"]][r], r))
            fl = self.example_flight[(u["airline"], r)]
            steps = [(f"User:{user_id}", "WORKS_AT", f"Airline:{u['airline']}"),
                     (f"Airline:{u['airline']}", "OPERATED_BY^-1", f"Flight:{fl}"),
                     (f"Flight:{fl}", "AFFECTED_BY", f"Risk:{r} ({self.risks[r]['name']})"),
                     (f"Risk:{r}", "RELEVANT_TO", f"Topic:{t}")]
        else:
            src = max((d for d in self.hist[user_id] if t in self.ds.items[d]["topics"]),
                      key=lambda d: (self.hist[user_id][d], d))
            steps = [(f"User:{user_id}", "OPENED", f"Doc:{src}"), (f"Doc:{src}", "ABOUT", f"Topic:{t}")]
        return {"component": comp, "topic": t, "steps": steps + end}
