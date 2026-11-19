"""Расчёт социометрических индексов.

Формулы подтверждены на цифрах персонального отчёта (март 2026, n = 68, K = 5):
  S = все полученные выборы / (K * (n - 1))        141 / 335 = 0,42
  E = все сделанные выборы / (K * (n - 1))         180 / 335 = 0,54
  Gg = взаимные положительные пары / (n(n-1)/2)    624 / 2278 = 27,4 %
  Y  = взаимные отрицательные пары / (n(n-1)/2)

Опрос считается только когда прошли все, и тогда это ровно формулы выше. Для идущего опроса
знаменатели берутся по ответившим, чтобы промежуточные цифры не «проваливались».
Статусы — по двум осям Коуи, Доджа и Копотелли (1982): предпочтение и заметность.
Ag (экспансивность группы) и U (референтность) пока приближённые.
"""
from itertools import combinations

# Границы диапазонов для «сколько выбрали вас» в личном отчёте.
RECEIVED_BINS = [(0, 0), (1, 5), (6, 10), (11, 20), (21, 30), (31, 10**9)]


def pairs_total(n: int) -> int:
    return n * (n - 1) // 2


def status_index(received_total: int, k: int, n: int) -> float:
    return received_total / (k * (n - 1)) if n > 1 and k else 0.0


def expansiveness_index(given_total: int, k: int, n: int) -> float:
    return given_total / (k * (n - 1)) if n > 1 and k else 0.0


def mutual_pairs(choices: dict[int, set[int]]) -> int:
    """Число неупорядоченных пар (i, j), где i выбрал j и j выбрал i."""
    total = 0
    for i, j in combinations(sorted(choices), 2):
        if j in choices[i] and i in choices.get(j, set()):
            total += 1
    return total


def group_index(pairs: int, n: int) -> float:
    return pairs / pairs_total(n) if n > 1 else 0.0


def received_range(count: int) -> str:
    for lo, hi in RECEIVED_BINS:
        if lo <= count <= hi:
            if lo == hi:
                return str(lo)
            return f"{lo}+" if hi >= 10**9 else f"{lo}-{hi}"
    return str(count)


# Минимальная неопределённость для показа взаимных выборов.
MUTUAL_MIN = 3


def mutual_visible(given: int, mutual: int, received: int, n: int) -> bool:
    """Можно ли показать человеку число взаимных выборов.

    Как в прошлых отчётах: ноль показываем всегда («выбрал 8, взаимных 0» — видно).
    Скрываем, только когда по числу понятно, кто именно ответил взаимностью:
    - среди тех, кого человек выбрал сам, невзаимных меньше 3 (выбрал 3 — взаимных 3,
      выбрал 20 — взаимных 19 или 20): про каждого из выбранных всё ясно;
    - среди тех, кого он не выбирал, почти все (кроме меньше чем 3) его выбрали:
      точное число полученных выборов вместе с взаимными раскрыло бы и их.
    Выбрал 20, взаимных 10 — угадать нельзя, показываем.
    """
    if given == 0 or mutual == 0:
        return True
    outside = n - 1 - given
    from_outside = received - mutual
    inside_ok = given - mutual >= MUTUAL_MIN
    outside_ok = outside == 0 or from_outside == 0 or outside - from_outside >= MUTUAL_MIN
    return inside_ok and outside_ok


def place_range(place: int, width: int = 10) -> str:
    lo = (place - 1) // width * width + 1
    return f"{lo}-{lo + width - 1}"


CATEGORY_TITLES = {
    "star": "Звезда",
    "preferred": "Предпочитаемый",
    "accepted": "Принятый",
    "isolated": "Изолированный",
    "rejected": "Отвергаемый",
    "controversial": "Противоречивый",
}
# Сильные ярлыки показываются как окончательные, только если повторились в прошлом опросе.
STRONG_CATEGORIES = {"star", "isolated", "rejected", "controversial"}


def _mean_sd(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    m = sum(values) / len(values)
    return m, (sum((v - m) ** 2 for v in values) / len(values)) ** 0.5


def classify_z(zlm: float, zll: float, zsp: float, zsi: float, pos: int, neg: int) -> str:
    """Категория по Коуи–Доджу. zlm/zll — z «за»/«против»; zsp/zsi — стандартизованные по группе
    предпочтение (за − против) и заметность (за + против)."""
    if pos == 0 and neg == 0:
        return "isolated"
    # «Против» должно быть заметно выше среднего (≥ 1 ст. откл.), иначе популярный человек
    # с обычным числом недоброжелателей ошибочно попадает в противоречивые.
    if zsi >= 1 and zlm > 0 and zll >= 1:
        return "controversial"
    if zsp <= -1 and zlm < 0 and zll > 0:
        return "rejected"
    if zsi <= -1 and zlm < 0 and zll < 0:
        return "isolated"
    if zsp >= 1.5 and zlm > 0 and zll < 0.5:
        return "star"
    if zsp >= 0.5 and zlm > 0:
        return "preferred"
    if pos == 0:
        return "isolated"
    return "accepted"


def classify(pos: int, neg: int, mp: float, sp: float, mn: float, sn: float) -> str:
    """Упрощённая классификация одного человека (без повторной стандартизации осей по группе)."""
    zp = (pos - mp) / sp if sp else 0.0
    zn = (neg - mn) / sn if sn else 0.0
    return classify_z(zp, zn, zp - zn, zp + zn, pos, neg)


def percentile(values: dict[int, float], m: int) -> float:
    """Какую долю остальных человек опережает (0..1); равные считаются наполовину."""
    v = values[m]
    others = len(values) - 1
    if others <= 0:
        return 0.5
    less = sum(1 for x, val in values.items() if x != m and val < v)
    equal = sum(1 for x, val in values.items() if x != m and val == v)
    return (less + 0.5 * equal) / others


def communities(ids: list[int], choices: dict[int, set[int]]) -> list[list[int]]:
    """Микрогруппы по взаимным выборам: жадная максимизация модулярности (первый шаг Louvain).

    Возвращает группы от 2 человек по убыванию размера. Люди без взаимных выборов не входят.
    """
    adj: dict[int, set[int]] = {m: set() for m in ids}
    for a, b in combinations(ids, 2):
        if b in choices.get(a, set()) and a in choices.get(b, set()):
            adj[a].add(b)
            adj[b].add(a)
    edges = sum(len(v) for v in adj.values()) // 2
    if not edges:
        return []
    com = {m: m for m in ids}
    deg = {m: len(adj[m]) for m in ids}
    tot = dict(deg)
    for _ in range(25):
        moved = False
        for m in sorted(ids):
            if not adj[m]:
                continue
            c0 = com[m]
            tot[c0] -= deg[m]
            links: dict[int, int] = {}
            for nb in adj[m]:
                links[com[nb]] = links.get(com[nb], 0) + 1
            best, gain = c0, links.get(c0, 0) - tot[c0] * deg[m] / (2 * edges)
            for c, k in sorted(links.items()):
                g = k - tot[c] * deg[m] / (2 * edges)
                if g > gain + 1e-9:
                    best, gain = c, g
            com[m] = best
            tot[best] += deg[m]
            moved = moved or best != c0
        if not moved:
            break
    groups: dict[int, list[int]] = {}
    for m in ids:
        if adj[m]:
            groups.setdefault(com[m], []).append(m)
    return sorted((sorted(g) for g in groups.values() if len(g) > 1), key=lambda g: (-len(g), g[0]))


def compute_stats(member_ids: list[int], questions: list[dict],
                  answers: dict[int, dict[int, set[int]]], respondents: set[int] | None = None) -> dict:
    """answers: member_id -> question_id -> множество выбранных member_id.

    Учитываются только участники из member_ids; самовыбор отбрасывается.
    """
    n = len(member_ids)
    ids = set(member_ids)
    resp = (set(answers) if respondents is None else set(respondents)) & ids
    r = len(resp)
    scored = [q for q in questions if q.get("criterion")]
    criteria = sorted({q["criterion"] for q in scored})
    k = len(criteria)

    by_q: dict[int, dict[int, set[int]]] = {}
    for q in scored:
        by_q[q["id"]] = {
            m: {t for t in answers.get(m, {}).get(q["id"], set()) if t in ids and t != m}
            for m in member_ids
        }

    members: dict[int, dict] = {}
    for m in member_ids:
        received = {q["id"]: sum(1 for o in member_ids if m in by_q[q["id"]][o]) for q in scored}
        given = {q["id"]: len(by_q[q["id"]][m]) for q in scored}
        mutual = {
            q["id"]: sum(1 for t in by_q[q["id"]][m] if m in by_q[q["id"]].get(t, set()))
            for q in scored
        }
        could_choose = r - (1 if m in resp else 0)
        members[m] = {
            "received": received,
            "given": given,
            "mutual": mutual,
            "S": sum(received.values()) / (k * could_choose) if k and could_choose > 0 else 0.0,
            "S_classic": status_index(sum(received.values()), k, n),
            "E": expansiveness_index(sum(given.values()), k, n),
        }

    pairs: dict[str, dict] = {}
    for q in scored:
        if q["polarity"] in ("+", "-"):
            pairs.setdefault(q["criterion"], {})[q["polarity"]] = q["id"]
    totals = {m: [0, 0] for m in member_ids}

    def axes(pos: dict, neg: dict) -> dict:
        """Две оси Коуи–Доджа: z «за» и «против», затем предпочтение и заметность, ещё раз стандартизованные."""
        mp, sp = _mean_sd(list(pos.values()))
        mn, sn = _mean_sd(list(neg.values()))
        zl = {m: (pos[m] - mp) / sp if sp else 0.0 for m in member_ids}
        zn = {m: (neg[m] - mn) / sn if sn else 0.0 for m in member_ids}
        raw_sp = {m: zl[m] - zn[m] for m in member_ids}
        raw_si = {m: zl[m] + zn[m] for m in member_ids}
        m1, s1 = _mean_sd(list(raw_sp.values()))
        m2, s2 = _mean_sd(list(raw_si.values()))
        out = {}
        for m in member_ids:
            zsp = (raw_sp[m] - m1) / s1 if s1 else 0.0
            zsi = (raw_si[m] - m2) / s2 if s2 else 0.0
            out[m] = (classify_z(zl[m], zn[m], zsp, zsi, pos[m], neg[m]), zsp, zsi)
        return out

    for c, pq in pairs.items():
        if "+" not in pq or "-" not in pq:
            continue
        pos = {m: members[m]["received"][pq["+"]] for m in member_ids}
        neg = {m: members[m]["received"][pq["-"]] for m in member_ids}
        giv = {m: members[m]["given"][pq["+"]] for m in member_ids}
        for m, (cat, pref, imp) in axes(pos, neg).items():
            mm = members[m]
            mm.setdefault("categories", {})[c] = cat
            mm.setdefault("pref", {})[c] = pref
            mm.setdefault("impact", {})[c] = imp
            mm.setdefault("pct", {})[c] = percentile(pos, m)
            mm.setdefault("pct_neg", {})[c] = percentile(neg, m)
            mm.setdefault("pct_given", {})[c] = percentile(giv, m)
            mm.setdefault("neg_received", {})[c] = neg[m]
            totals[m][0] += pos[m]
            totals[m][1] += neg[m]
    ref = next((q for q in scored if q["polarity"] is None), None)
    if ref:
        rv = {m: members[m]["received"][ref["id"]] for m in member_ids}
        for m in member_ids:
            members[m].setdefault("pct", {})[ref["criterion"]] = percentile(rv, m)

    overall = axes({m: totals[m][0] for m in member_ids}, {m: totals[m][1] for m in member_ids})
    plus = lambda m, cs: sum(members[m]["received"].get(pairs.get(c, {}).get("+"), 0) for c in cs)
    biz = {m: plus(m, ("teamwork", "organizing")) for m in member_ids}
    per = {m: plus(m, ("trust", "leisure")) for m in member_ids}
    for m in member_ids:
        cat, pref, imp = overall[m]
        members[m].update(category=cat, pref_total=pref, impact_total=imp,
                          pos_total=totals[m][0], neg_total=totals[m][1],
                          pct_business=percentile(biz, m), pct_personal=percentile(per, m))

    ranked = sorted(member_ids, key=lambda m: -members[m]["S"])
    for m in member_ids:
        members[m]["place"] = 1 + sum(1 for o in member_ids if members[o]["S"] > members[m]["S"])

    group: dict[str, dict] = {}
    for c in criteria:
        qs = [q for q in scored if q["criterion"] == c]
        pos_q = next((q for q in qs if q["polarity"] == "+"), None)
        neg_q = next((q for q in qs if q["polarity"] == "-"), None)
        ref_q = next((q for q in qs if q["polarity"] is None), None)
        entry: dict = {}
        if pos_q:
            p = mutual_pairs(by_q[pos_q["id"]])
            entry.update(mutual_positive_pairs=p, Gg=group_index(p, r))
            entry["groups"] = communities(member_ids, by_q[pos_q["id"]])
        if neg_q:
            p = mutual_pairs(by_q[neg_q["id"]])
            entry.update(mutual_negative_pairs=p, Y=group_index(p, r))
        if ref_q:
            p = mutual_pairs(by_q[ref_q["id"]])
            entry.update(mutual_pairs=p, U=group_index(p, r))
        given_total = sum(len(s) for q in qs for s in by_q[q["id"]].values())
        entry["Ag"] = given_total / (len(qs) * r * (n - 1)) if r and n > 1 else 0.0
        group[c] = entry

    return {"n": n, "k": k, "respondents": r, "ranked": ranked, "members": members, "group": group}
