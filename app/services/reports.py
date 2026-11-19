"""Групповой отчёт: цифры и графики считаются автоматически, текст формируется как черновик.

Публичный отчёт анонимен: узлы социограмм получают случайные номера, имён нет.
"""
import hashlib
import hmac
from collections import Counter
from itertools import combinations
from statistics import mean, pstdev

CRITERIA = {
    "teamwork": "Совместная работа",
    "organizing": "Организаторские способности",
    "trust": "Доверие",
    "leisure": "Досуг",
    "referent": "Референтометрия",
}
ORDER = ["teamwork", "organizing", "trust", "leisure", "referent"]
SOCIO = ["teamwork", "organizing", "trust", "leisure"]
# Ниже этой явки индексы занижены, и сравнивать их с другими опросами нельзя.
LOW_TURNOUT = 0.7


# Минимальные размеры групп для показа (анонимность).
MIN_PUBLIC = 3      # числа людей в публичном отчёте
MIN_ANSWERS = 5     # ответов «без имён» для руководства


def small(count: int) -> int | None:
    """None означает «меньше 3»: такие числа не показываем."""
    return None if 0 < count < MIN_PUBLIC else count


def pct(x: float | None, digits: int = 1) -> str:
    if x is None:
        return "—"
    return f"{x * 100:.{digits}f}".replace(".", ",") + "%"


def pp(delta: float) -> str:
    """Изменение в процентных пунктах со знаком."""
    sign = "+" if delta > 0 else "−" if delta < 0 else "±"
    return f"{sign}{abs(delta) * 100:.1f}".replace(".", ",") + " п.п."


def pts(delta: float) -> str:
    """Размер изменения без знака, для фраз вида «выросла на 2,1 п.п.»."""
    return f"{abs(delta) * 100:.1f}".replace(".", ",") + " п.п."


def plural(n: int, one: str, few: str, many: str) -> str:
    n10, n100 = n % 10, n % 100
    if n10 == 1 and n100 != 11:
        return one
    if 2 <= n10 <= 4 and not 12 <= n100 <= 14:
        return few
    return many


def build_group_report(svc, period: dict) -> dict:
    stats = svc.stats(period)
    n = stats["n"]
    answers = svc.submitted_answers(period)
    qs = [q for q in svc.period_questions(period) if q["kind"] == "permanent"]
    pos_q = {q["criterion"]: q["id"] for q in qs if q["polarity"] == "+"}
    ids = sorted(stats["members"])
    idset = set(ids)

    secret = svc.anon_secret().encode()
    order = sorted(ids, key=lambda m: hmac.new(secret, f"{period['id']}:{m}".encode(), hashlib.sha256).hexdigest())
    anon = {m: i + 1 for i, m in enumerate(order)}

    criteria = {}
    for key in ORDER:
        g = stats["group"].get(key)
        if not g:
            continue
        info = {"title": CRITERIA[key], "Gg": g.get("Gg"), "Y": g.get("Y"), "Ag": g.get("Ag"), "U": g.get("U"),
                "mutual_positive": g.get("mutual_positive_pairs"),
                "mutual_negative": g.get("mutual_negative_pairs"), "reciprocity": None}
        qid = pos_q.get(key)
        if qid is not None:
            total = sum(stats["members"][m]["given"][qid] for m in ids)
            info["reciprocity"] = (2 * g.get("mutual_positive_pairs", 0) / total) if total else None
            info["avg_choices"] = total / len(ids) if ids else 0
        criteria[key] = info

    sociograms = {}
    for key in SOCIO:
        qid = pos_q.get(key)
        if qid is None:
            continue
        choices = {m: {t for t in answers.get(m, {}).get(qid, set()) if t in idset and t != m} for m in ids}
        edges = [[anon[a], anon[b]] for a, b in combinations(ids, 2) if b in choices[a] and a in choices[b]]
        nodes = [{"id": anon[m], "s": stats["members"][m]["received"][qid] / (n - 1) if n > 1 else 0} for m in ids]
        sociograms[key] = {"title": CRITERIA[key], "nodes": nodes, "edges": edges}

    s_values = [stats["members"][m]["S"] for m in ids]
    s_mean = mean(s_values) if s_values else 0
    s_std = pstdev(s_values) if len(s_values) > 1 else 0
    bins = [0] * 7
    for v in s_values:
        bins[min(int(v / 0.1), 6)] += 1

    isolated = sum(1 for m in ids
                   if sum(stats["members"][m]["received"].get(pos_q[k], 0) for k in SOCIO if k in pos_q) == 0)
    core = sum(1 for v in s_values if v >= s_mean + s_std) if s_std else 0
    flag_counts = Counter(f["kind"] for f in svc.flags(period))
    structure = Counter(stats["members"][m].get("category", "accepted") for m in ids)
    respondents = len(answers)
    microgroups = {}
    for key in SOCIO:
        g = stats["group"].get(key, {}).get("groups")
        if g is not None:
            in_groups = {m for grp in g for m in grp}
            microgroups[key] = {"title": CRITERIA[key], "sizes": [len(x) for x in g],
                                "outside": sum(1 for m in ids if m not in in_groups)}

    return {
        "period": {"id": period["id"], "title": period["title"], "date": period.get("date"),
                   "status": period["status"]},
        "n": n, "respondents": respondents,
        "participation": respondents / n if n else 0,
        "criteria": criteria, "sociograms": sociograms,
        "status_hist": {"bins": bins, "labels": ["0–0,1", "0,1–0,2", "0,2–0,3", "0,3–0,4", "0,4–0,5", "0,5–0,6", "0,6+"]},
        "s_mean": s_mean, "core": core, "isolated": small(isolated),
        # Числа 1–2 в публичном отчёте скрываем: в группе, где все знают друг друга, это почти имя.
        "structure": {k: small(structure.get(k, 0)) for k in ("star", "preferred", "accepted", "controversial", "rejected", "isolated")},
        "microgroups": microgroups,
        "flags": {"conflict": flag_counts.get("conflict", 0), "suspicious": flag_counts.get("suspicious", 0),
                  "individualist": flag_counts.get("individualist", 0)},
        "text": period.get("report_text", ""),
        "low_turnout": n > 0 and respondents / n < LOW_TURNOUT,
        "published": bool(period.get("published")),
    }


def published_periods(svc) -> list[dict]:
    ps = [p for p in svc.s.open.read()["periods"] if p.get("published")]
    return sorted(ps, key=lambda p: (p.get("date") or p.get("created_at") or "", p["id"]))


def build_series(svc) -> list[dict]:
    series = []
    for p in published_periods(svc):
        r = build_group_report(svc, p)
        series.append({
            "id": p["id"], "title": p["title"], "date": p.get("date"),
            "n": r["n"], "respondents": r["respondents"], "low_turnout": r["low_turnout"],
            "criteria": {k: {x: c.get(x) for x in ("Gg", "Y", "Ag", "U")} for k, c in r["criteria"].items()},
        })
    return series


def previous_report(svc, period: dict) -> dict | None:
    key = (period.get("date") or period.get("created_at") or "", period["id"])
    prev = [p for p in published_periods(svc)
            if (p.get("date") or p.get("created_at") or "", p["id"]) < key and p["id"] != period["id"]]
    return build_group_report(svc, prev[-1]) if prev else None


# --- текст -----------------------------------------------------------------

def _themes(rows: list[dict], total_respondents: int) -> list[str]:
    texts = [r["text"].strip() for r in rows if r.get("text") and r["text"].strip()]
    if not texts:
        return ["Ответов на этот вопрос нет."]
    counts = Counter(t.lower() for t in texts).most_common()
    shown = {t.lower(): t for t in texts}
    repeated = [(shown[k], c) for k, c in counts if c > 1][:5]
    lines = [f"Ответили {len(texts)} {plural(len(texts), 'человек', 'человека', 'человек')}."]
    if repeated:
        lines.append("Чаще всего повторялось:")
        lines += [f"- «{t}» — {c} {plural(c, 'ответ', 'ответа', 'ответов')}" for t, c in repeated]
    else:
        lines.append("Ответы разные, одинаковых формулировок почти нет — их стоит прочитать вручную.")
    return lines


def draft_text(svc, period: dict, report: dict, prev: dict | None) -> str:
    n, resp = report["n"], report["respondents"]
    cr = report["criteria"]
    out: list[str] = []

    # Изменения контекста
    out += ["## Изменения контекста",
            f"В исследовании «{report['period']['title']}» участвовало {resp} из {n} человек "
            f"({pct(report['participation'], 0)} группы)."]
    if prev:
        d = report["participation"] - prev["participation"]
        out.append(f"В прошлый раз («{prev['period']['title']}») прошли {prev['respondents']} из {prev['n']}. "
                   f"Активность {'выросла' if d > 0 else 'снизилась' if d < 0 else 'не изменилась'}"
                   f"{'' if d == 0 else ' на ' + pts(abs(d))}.")
    cmp = prev if prev and not report["low_turnout"] and not prev.get("low_turnout") else None
    if report["low_turnout"]:
        out.append("Анкету заполнили меньше 70% группы. Связи тех, кто не ответил, в расчёт не попали, "
                   "поэтому сплочённость и статусы занижены и сравнивать их с прошлыми опросами нельзя.")
    elif prev and prev.get("low_turnout"):
        out.append("В прошлом опросе явка была низкой, поэтому изменения индексов к нему не приводятся.")

    # Общее состояние
    gg = {k: v["Gg"] for k, v in cr.items() if v.get("Gg") is not None}
    out += ["", "## Общее состояние"]
    if gg:
        hi, lo = max(gg, key=gg.get), min(gg, key=gg.get)
        out.append(f"Сплочённость группы (индекс Gg — доля возможных пар людей, которые выбрали друг друга) "
                   f"выше всего по критерию «{CRITERIA[hi]}» — {pct(gg[hi])}, ниже всего по критерию "
                   f"«{CRITERIA[lo]}» — {pct(gg[lo])}.")
        if cmp:
            out.append("Изменение к прошлому исследованию:")
            for k in SOCIO:
                if k in gg and cmp["criteria"].get(k, {}).get("Gg") is not None:
                    out.append(f"- {CRITERIA[k]}: {pct(gg[k])} ({pp(gg[k] - cmp['criteria'][k]['Gg'])})")
    y = {k: v["Y"] for k, v in cr.items() if v.get("Y") is not None}
    if y:
        ymax = max(y, key=y.get)
        level = ("остаётся низкой: взаимное отвержение — единичные случаи" if y[ymax] < 0.01
                 else "заметна: стоит посмотреть, между кем возникает напряжение" if y[ymax] < 0.02
                 else "высокая: это повод для отдельного разговора с группой")
        txt = (f"Конфликтность (индекс Y — доля пар, где люди взаимно отвергли друг друга) максимальна по критерию "
               f"«{CRITERIA[ymax]}» — {pct(y[ymax], 2)}, и она {level}.")
        prev_y = [v.get("Y") for v in cmp["criteria"].values() if v.get("Y") is not None] if cmp else []
        if prev_y:
            dy = y[ymax] - max(prev_y)
            word = "выросла" if dy > 0 else "снизилась" if dy < 0 else "не изменилась"
            txt += f" Максимальная конфликтность к прошлому разу {word}{'' if dy == 0 else ' на ' + pts(abs(dy))}."
        out.append(txt)
    work, leis = cr.get("teamwork"), cr.get("leisure")
    if work and leis and "avg_choices" in work:
        out.append(f"В среднем участник отмечает около {work['avg_choices']:.0f} человек по критерию совместной "
                   f"работы и около {leis['avg_choices']:.0f} по критерию досуга. "
                   f"Взаимными оказываются {pct(work['reciprocity'], 0)} рабочих и {pct(leis['reciprocity'], 0)} "
                   f"досуговых выборов.")

    # Наблюдения
    out += ["", "## Моменты и наблюдения"]
    if report["core"]:
        out.append(f"- Ядро группы: {report['core']} {plural(report['core'], 'человек', 'человека', 'человек')} "
                   f"({pct(report['core'] / n, 0)}) получили заметно больше выборов, чем в среднем. "
                   f"На них держится значительная часть связей.")
    iso = report["isolated"]
    if iso is None:
        out.append("- Без положительных выборов по всем критериям остались единицы (меньше трёх человек). "
                   "Это не оценка людей, но им полезно уделить внимание, особенно если они недавно пришли.")
    elif iso:
        out.append(f"- Без единого положительного выбора по всем критериям остались {iso} "
                   f"{plural(iso, 'человек', 'человека', 'человек')} ({pct(iso / n, 0)}). "
                   "Это не оценка людей, но им полезно уделить внимание, особенно если они недавно пришли.")
    else:
        out.append("- Изолированных нет: каждого участника хотя бы раз отметили положительно.")
    mg = report.get("microgroups", {}).get("teamwork")
    if mg and mg["sizes"]:
        out.append(f"- По совместной работе группа складывается в {len(mg['sizes'])} "
                   f"{plural(len(mg['sizes']), 'компанию', 'компании', 'компаний')} "
                   f"от {min(mg['sizes'])} до {max(mg['sizes'])} человек, где люди выбирают друг друга взаимно. "
                   + (f"Без взаимных рабочих выборов пока {mg['outside']} {plural(mg['outside'], 'человек', 'человека', 'человек')}."
                      if mg["outside"] >= MIN_PUBLIC else "Почти у всех есть хотя бы один взаимный рабочий выбор."))
    f = report["flags"]
    if f["individualist"]:
        out.append(f"- {f['individualist']} {plural(f['individualist'], 'участник выбрал', 'участника выбрали', 'участников выбрали')} "
                   f"«Никто» во всех вопросах.")
    if f["conflict"]:
        out.append(f"- В {f['conflict']} случаях один и тот же человек одновременно оказался и в положительном, "
                   f"и в отрицательном выборе одного респондента. Такие ответы учтены, но помечены для проверки.")
    if f["suspicious"]:
        out.append(f"- {f['suspicious']} {plural(f['suspicious'], 'ответ выглядит', 'ответа выглядят', 'ответов выглядят')} "
                   f"подозрительно (выбрано очень много людей). Аналитик проверил их до публикации.")

    # Общие вопросы
    custom = [r for r in svc.custom_answers_report(svc.get_period(period["id"]), include_private=True)
              if r["visibility"] != "analyst"]
    if custom:
        out += ["", "## Ответы на общие вопросы"]
        for r in custom:
            out.append(f"**{r['text']}**")
            if r["answer_type"] == "text":
                out += _themes(r["answers"], resp)
            else:
                named = Counter(t for a in r["answers"] for t in a["targets"])
                if named:
                    top = named.most_common(1)[0][1]
                    out.append(f"Назвали {len(named)} разных людей, наибольшее число упоминаний у одного человека — {top}. "
                               f"Имена в публичном отчёте не раскрываются.")
                else:
                    out.append("Ответов на этот вопрос нет.")
            out.append("")
        if out[-1] == "":
            out.pop()

    # Сигналы
    out += ["", "## Приоритетные сигналы"]
    signals = []
    ymax_v = max(y.values()) if y else 0
    if report["participation"] < 0.6:
        signals.append(("Высокий", "Низкая активность: опрос прошли меньше 60% группы. Напомнить не прошедшим и сравнить итоги с осторожностью."))
    if ymax_v >= 0.02:
        signals.append(("Высокий", "Конфликтность выше 2%: нужен разговор с группой."))
    if n and iso and iso / n >= 0.05:
        signals.append(("Высокий", f"Изолированных {pct(iso / n, 0)} группы: поговорить с ними лично."))
    if cmp:
        for k in SOCIO:
            a, b = cr.get(k, {}).get("Gg"), cmp["criteria"].get(k, {}).get("Gg")
            if a is not None and b is not None and a - b <= -0.03:
                signals.append(("Средний", f"Сплочённость по критерию «{CRITERIA[k]}» упала на {pts(abs(a - b))}."))
        yp = max((v.get("Y") or 0) for v in cmp["criteria"].values())
        if ymax_v - yp >= 0.005:
            signals.append(("Средний", f"Конфликтность выросла на {pts(ymax_v - yp)}."))
    if gg and min(gg, key=gg.get) == "trust":
        signals.append(("Средний", "Самая слабая связность — по доверию. Для группы это нормально, но стоит поддерживать неформальное общение."))
    if f["conflict"] > 0.05 * max(resp, 1):
        signals.append(("Средний", "Много противоречивых ответов: возможно, вопросы пары поняли неоднозначно."))
    if cmp:
        for k in SOCIO:
            a, b = cr.get(k, {}).get("Gg"), cmp["criteria"].get(k, {}).get("Gg")
            if a is not None and b is not None and a - b >= 0.03:
                signals.append(("Низкий", f"Сплочённость по критерию «{CRITERIA[k]}» выросла на {pts(a - b)}."))
    if not signals:
        signals.append(("Низкий", "Тревожных сигналов нет, показатели в обычных пределах."))
    order = {"Высокий": 0, "Средний": 1, "Низкий": 2}
    out += [f"- **{lvl}.** {txt}" for lvl, txt in sorted(signals, key=lambda s: order[s[0]])]
    return "\n".join(out).replace("п.п..", "п.п.")


# --- личный отчёт ------------------------------------------------------------
#
# Подача (2026-11-18, по исследованию понятности): на первом листе не индексы S/E и не место,
# а «N человек из 59» по каждому вопросу со средним по группе и полоской; «против» — отдельной
# строкой точными числами; S, E и место — мелко, «для специалистов».
#
# Уровень по критерию — процентиль выборов «за»: ≥ 90 % «один из лидеров группы», 65–90 «выше среднего»,
# 35–65 «на уровне группы», 10–35 «ниже среднего», < 10 или 0 выборов «мало выборов»; в группе < 10
# человек — три уровня. Тексты описывают мнение группы, а не черты характера; никаких «кто выбрал».

LEVELS = [(0.90, "top"), (0.65, "high"), (0.35, "mid"), (0.10, "low"), (0.0, "min")]
LEVEL_TITLES = {"top": "один из лидеров группы", "high": "выше среднего", "mid": "на уровне группы",
                "low": "ниже среднего", "min": "мало выборов"}
LEVEL_CLASS = {"top": "high", "high": "high", "mid": "mid", "low": "low", "min": "low"}

# Подписи к «N из 59» — вопрос, который человек помнит.
POS_LABEL = {
    "teamwork": "хотели бы работать с вами над проектом",
    "organizing": "видят вас руководителем проекта",
    "trust": "обратились бы к вам за советом в трудной ситуации",
    "leisure": "позвали бы вас на праздник",
    "referent": "хотели бы посмотреть ваши ответы",
}
NEG_LABEL = {
    "teamwork": "не хотели бы работать вместе",
    "organizing": "не справится с ролью руководителя",
    "trust": "не хотели бы советоваться",
    "leisure": "не стали бы звать на праздник",
}
# Что именно измеряет вопрос — одной фразой, чтобы число было понятно без методики.
MEANING = {
    "teamwork": "Этот вопрос про дела: с кем люди хотели бы делать общий проект или мероприятие.",
    "organizing": "Этот вопрос про роль: кому группа доверила бы вести проект.",
    "trust": "Этот вопрос про близость: к кому пошли бы в трудной личной ситуации. Здесь люди выбирают очень немногих.",
    "leisure": "Этот вопрос про неформальное общение: кого позвали бы на свой праздник.",
    "referent": "Этот вопрос про интерес к мнению: чьи ответы людям было бы любопытно увидеть.",
}
SHORT = {"teamwork": "работа", "organizing": "руководство", "trust": "доверие", "leisure": "досуг", "referent": "интерес к мнению"}

TEXTS = {
    "teamwork": {
        "top": ["С вами хотят работать больше, чем почти с кем-либо в группе: для совместных проектов вас называют одним из первых. Такой результат обычно складывается, когда люди уже делали с вами дела и хотят повторить.",
                "В совместной работе вы один из самых желанных людей группы. Вас выбирают чаще, чем почти всех остальных, а значит, опыт общей работы с вами у людей хороший."],
        "high": ["С вами охотно работают: в проекты вас зовут чаще, чем большинство участников. Для группы вы надёжный партнёр по делу.",
                 "Группа видит в вас хорошего партнёра по проектам: для совместной работы вас выбирают чаще среднего."],
        "mid": ["В совместной работе вас выбирают примерно так же, как большинство: у вас есть свой круг людей, с которыми вы делаете проекты, и он обычного для группы размера.",
                "С вами готовы работать в обычной для группы мере. Вы не теряетесь в общих делах, но и не выделяетесь среди остальных."],
        "low": ["Для совместной работы вас выбирают реже, чем большинство. Часто так бывает, когда человек работает в одной небольшой команде или группа мало пересекалась с ним в общих проектах.",
                "В общих проектах группа видит вас реже других. Обычно это меняется после нескольких общих задач с новыми людьми."],
        "min": ["Для совместной работы вас почти не называли. Скорее всего, большая часть группы просто не работала с вами в одном проекте.",
                "Совместной работы с вами группа почти не видела: в этом вопросе выборов очень мало."],
    },
    "organizing": {
        "top": ["Многие видят в вас руководителя: по этому вопросу вас называют чаще почти всех в группе. Группа уверена, что вы справитесь с ведением проекта или мероприятия.",
                "Вы среди первых, кого группа называет организатором. Это значит, что люди уже видели, как вы ведёте дела, и доверяют вам роль руководителя."],
        "high": ["Коллектив видит в вас организатора: вас считают способным вести проект чаще, чем большинство участников.",
                 "Вас нередко называют тем, кто справится с ролью руководителя мероприятия: чаще, чем в среднем по группе."],
        "mid": ["В роли организатора группа видит вас примерно так же, как большинство. Вас знают как участника общих дел, а в роли ведущего видели не очень часто.",
                "Ваши организаторские способности группа оценивает на обычном для себя уровне."],
        "low": ["Руководителем вас называют реже, чем большинство. Обычно это значит не то, что вы не справитесь, а то, что группа редко видела вас в этой роли.",
                "В роли руководителя группа представляет вас нечасто: выборов здесь меньше среднего."],
        "min": ["Руководителем проекта вас почти не называли. Чаще всего так бывает, когда человек ещё не вёл общих дел на глазах у группы.",
                "В вопросе про руководство выборов почти нет: группа не видела вас в роли организатора."],
    },
    "trust": {
        "top": ["К вам готовы обратиться в трудной ситуации очень многие: по доверию вы среди первых в группе. Людям спокойно делиться с вами личным.",
                "Вам доверяют личное больше, чем почти кому-либо в группе. Для многих вы человек, к которому можно прийти за советом."],
        "high": ["За советом к вам пришли бы чаще, чем к большинству: вам доверяют личное.",
                 "Многие в группе видят в вас человека, к которому можно обратиться в трудный момент."],
        "mid": ["По доверию у вас обычная для группы позиция: есть люди, которые пришли бы к вам за советом. В этом вопросе люди вообще выбирают немногих, поэтому числа здесь у всех небольшие.",
                "Вам доверяют примерно так же, как большинству. Доверительных выборов в группе в целом немного, и ваш результат в пределах обычного."],
        "low": ["За советом в личных вопросах к вам обращались бы реже, чем к большинству. Доверие обычно складывается со временем и вне общих дел, в неформальном общении.",
                "В доверительных вопросах вас называют реже среднего. В этом вопросе люди выбирают очень немногих, обычно самых близких."],
        "min": ["Среди тех, к кому пойдут в трудной ситуации, вас почти не называли. В этом вопросе люди выбирают одного-двух самых близких, поэтому низкие числа здесь встречаются часто.",
                "В доверительном вопросе выборов почти нет. Это говорит о близости, которая складывается не сразу, а не об отношении к вам."],
    },
    "leisure": {
        "top": ["В неформальной обстановке вы одни из самых популярных: на праздник вас позвали бы очень многие.",
                "Вас зовут на дни рождения и встречи чаще, чем почти всех в группе: с вами хотят проводить время."],
        "high": ["Вне дел студсовета с вами охотно проводят время: на праздник вас позвали бы чаще, чем большинство.",
                 "На праздники и встречи вас приглашали бы чаще среднего."],
        "mid": ["В досуге у вас обычная позиция: есть компания, с которой вы проводите свободное время.",
                "Вне работы вас зовут примерно так же, как большинство участников."],
        "low": ["Вне работы вас зовут реже, чем большинство. Возможно, вы больше сосредоточены на деле или ваша компания находится вне этой группы.",
                "На неформальные встречи вас приглашали бы реже среднего. Это про то, где вы проводите свободное время, а не про отношение к вам в делах."],
        "min": ["Среди тех, кого позвали бы на праздник, вас почти не называли. Скорее всего, ваше свободное время проходит в другой компании.",
                "В вопросе про досуг выборов почти нет: вне дел студсовета группа с вами мало пересекается."],
    },
    "referent": {
        "top": ["Ваше мнение одно из самых интересных для группы: ваши ответы хотели бы увидеть очень многие."],
        "high": ["Многим интересно, что вы думаете: ваши ответы хотят увидеть чаще, чем ответы большинства."],
        "mid": ["Интерес к вашему мнению в группе на обычном уровне."],
        "low": ["Ваши ответы хотели бы увидеть реже, чем у большинства. Интерес к мнению обычно растёт, когда человек заметнее в общих делах."],
        "min": ["Среди тех, чьи ответы интересно увидеть, вас почти не называли."],
    },
}
OVERALL_TEXTS = {
    "top": "Вы один из самых заметных и принятых людей группы: вас выбирают сразу по нескольким вопросам.",
    "high": "Группа выбирает вас чаще, чем большинство, и это не одна сфера: у вас прочные связи по нескольким направлениям.",
    "mid": "Ваша позиция в группе обычная и устойчивая: вы вовлечены в жизнь коллектива, у вас есть свои связи.",
    "low": "Вас выбирают реже, чем большинство. Это не оценка вас как человека: опрос показывает только то, насколько группа вас уже знает и как часто видит рядом.",
    "min": "В этом опросе группа почти вас не выбирала. Чаще всего так бывает, когда группа мало пересекалась с человеком в делах и встречах.",
}
PROFILES = {
    "business": ("Деловой профиль", "Вас ценят прежде всего как партнёра по делу: в работе и организации вас выбирают заметно чаще, чем в личном общении."),
    "personal": ("Неформальный профиль", "К вам тянутся в общении и за поддержкой: в доверии и досуге вас выбирают заметно чаще, чем в делах."),
    "even": ("Ровный профиль", "Группа выбирает вас примерно одинаково и в делах, и в личном общении."),
    "low": ("Профиль ещё не сложился", "Выборов мало и в делах, и в личном общении, поэтому сравнивать сферы между собой рано."),
}
ADVICE = {
    "top": "Если хотите, делитесь опытом: к людям, которых выбирают так часто, обычно и так идут за помощью, и это можно превратить в наставничество для новичков.",
    "high": "Если хотите укрепить позицию, обратите внимание на критерий, где выборов меньше всего: там проще всего заметить изменения к следующему опросу.",
    "mid": "Если хотите, чтобы вас чаще видели в какой-то роли, возьмите одно небольшое дело в этой сфере: например, организацию встречи или задачу вместе с новыми людьми. Результат будет виден в следующем опросе.",
    "low": "Если хочется, чтобы группа знала вас лучше, возьмите небольшую задачу в общей команде или предложите кому-то поработать вместе. Менять в себе ничего не нужно: опрос показывает только то, как группа ответила сейчас.",
    "min": "Если хочется, чтобы группа знала вас лучше, начните с малого: одна общая задача или встреча с людьми, с которыми вы пока мало пересекались. Менять в себе ничего не нужно, опрос показывает только сегодняшние ответы группы.",
}


def level_of(p: float, n: int, received: int) -> str:
    if received == 0:
        return "min"
    if n < 10:  # в маленькой группе процентили грубые: три уровня
        return "high" if p >= 0.65 else "low" if p < 0.35 else "mid"
    return next(lvl for cut, lvl in LEVELS if p >= cut)


def _variant(key: str, options: list[str]) -> str:
    """Вариант формулировки фиксирован для человека, опроса и критерия."""
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
    return options[h % len(options)]


def _q(values: list[float], frac: float) -> float:
    vs = sorted(values)
    if not vs:
        return 0.0
    i = (len(vs) - 1) * frac
    lo = int(i)
    return vs[lo] + (vs[min(lo + 1, len(vs) - 1)] - vs[lo]) * (i - lo)


def _num(x: float) -> str:
    return f"{x:.1f}".replace(".", ",").replace(",0", "")


def _people(n: int) -> str:
    return f"{n} {plural(n, 'человек', 'человека', 'человек')}"


def personal_report(svc, period: dict, member_id: int) -> dict:
    from app.services import scoring
    st = svc.stats(period)
    mine = st["members"][member_id]
    n = st["n"]
    out_of = n - 1
    qs = [q for q in svc.period_questions(period) if q["kind"] == "permanent"]
    by_crit: dict[str, dict] = {}
    for q in qs:
        by_crit.setdefault(q["criterion"], {})[q["polarity"]] = q["id"]
    members = list(st["members"].values())

    rows = []
    for q in qs:
        qid = q["id"]
        g, k, rcv = mine["given"][qid], mine["mutual"][qid], mine["received"][qid]
        rows.append({"question_id": qid, "text": q["text"], "criterion": q["criterion"],
                     "criterion_title": CRITERIA[q["criterion"]], "polarity": q["polarity"],
                     "given": g, "received": rcv, "received_range": scoring.received_range(rcv),
                     "mutual": k if scoring.mutual_visible(g, k, rcv, n) else None,
                     "group_avg": sum(v["given"][qid] for v in members) / n,
                     "group_avg_mutual": sum(v["mutual"][qid] for v in members) / n})

    # Блоки «N из 59» по пяти вопросам «за» (и референтометрии).
    blocks = []
    for c in ORDER:
        pq = by_crit.get(c, {})
        qid = pq.get("+", pq.get(None))
        if qid is None:
            continue
        rec = [v["received"][qid] for v in members]
        own = mine["received"][qid]
        p = mine["pct"].get(c, 0.5)
        lvl = level_of(p, n, own)
        b = {"criterion": c, "title": CRITERIA[c], "label": POS_LABEL[c], "short": SHORT[c],
             "received": own, "avg": sum(rec) / n, "p25": _q(rec, 0.25), "p75": _q(rec, 0.75), "max": max(rec),
             "given": mine["given"][qid], "level": LEVEL_CLASS[lvl], "level_key": lvl,
             "level_title": LEVEL_TITLES[lvl], "percentile": round(p * 100),
             "mutual": rows[[r["question_id"] for r in rows].index(qid)]["mutual"]}
        nid = pq.get("-")
        if nid is not None:
            negs = [v["received"][nid] for v in members]
            nm, nsd = scoring._mean_sd(negs)
            b.update(neg=mine["received"][nid], neg_avg=nm, neg_label=NEG_LABEL[c],
                     neg_high=mine["received"][nid] >= max(3, nm + nsd))
        blocks.append(b)
    above = sum(1 for b in blocks if b["received"] > b["avg"] * 1.1)
    below = sum(1 for b in blocks if b["received"] < b["avg"] * 0.9)
    total = len(blocks)
    if above == total:
        headline = f"В этом опросе вас выбрали многие: по всем {total} вопросам чаще, чем в среднем по группе."
    elif below == total:
        headline = (f"В этом опросе вас выбрали немногие: по всем {total} вопросам реже, чем в среднем по группе. "
                    "Ниже точные числа — что они значат и чего не значат.")
    elif above >= below:
        headline = (f"Вас выбирают как большинство или чаще: по {above} {plural(above, 'вопросу', 'вопросам', 'вопросам')} "
                    f"из {total} чаще среднего" + (f", по {below} реже." if below else "."))
    else:
        headline = (f"Вас выбирают чуть реже большинства: по {below} {plural(below, 'вопросу', 'вопросам', 'вопросам')} "
                    f"из {total} реже среднего" + (f", по {above} чаще." if above else "."))

    socio = [b for b in blocks if b["criterion"] in SOCIO]
    avg_p = sum(mine["pct"][b["criterion"]] for b in socio) / len(socio) if socio else 0.5
    overall_lvl = level_of(avg_p, n, mine.get("pos_total", 0))
    biz, per = mine.get("pct_business", 0.5), mine.get("pct_personal", 0.5)
    if biz < 0.10 and per < 0.10:
        profile = "low"
    else:
        profile = "business" if biz - per >= 0.25 else "personal" if per - biz >= 0.25 else "even"

    # Прошлый опрос для сравнения
    prev_counts = None
    earlier = [p for p in published_periods(svc)
               if (p.get("date") or "", p["id"]) < (period.get("date") or "", period["id"]) and p["id"] != period["id"]]
    prev_title = None
    for p in reversed(earlier):
        if member_id in svc.submitted_answers(p):
            pst = svc.stats(p)
            if member_id in pst["members"]:
                prev_counts = {c: pst["members"][member_id]["received"][by_crit[c].get("+", by_crit[c].get(None))]
                               for c in by_crit}
                prev_title = p["title"]
            break

    # --- интерпретация: 8 блоков ---
    interp = []
    interp.append({"title": "Главное", "text": headline + " " + OVERALL_TEXTS[overall_lvl]})
    ratio = lambda b: (b["received"] + 0.5) / (b["avg"] + 0.5)
    best = max(blocks, key=ratio)
    worst = min(blocks, key=ratio)
    fact = lambda b: f"{b['label'][0].upper()}{b['label'][1:]}: {b['received']} из {out_of} (в среднем по группе {_num(b['avg'])})"
    if best["received"] > best["avg"]:
        interp.append({"title": "Сильнее всего", "text": f"{best['title']}. {fact(best)}. " + _variant(
            f"{period['id']}:{member_id}:{best['criterion']}", TEXTS[best["criterion"]][best["level_key"]])})
    else:
        interp.append({"title": "Сильнее всего", "text": f"Относительно других ваших результатов выше всего {best['title'].lower()}: "
                       f"{fact(best).lower()}. Все числа в этом опросе ниже среднего по группе, но здесь разрыв со средним меньше всего."})
    if worst["criterion"] != best["criterion"]:
        if worst["received"] >= worst["avg"]:
            interp.append({"title": "Где вас видят меньше всего", "text": f"Даже самый скромный ваш результат не ниже среднего: "
                           f"{worst['title'].lower()}. {fact(worst)}."})
        else:
            interp.append({"title": "Где вас видят меньше всего", "text": f"{worst['title']}. {fact(worst)}. "
                           + _variant(f"{period['id']}:{member_id}:{worst['criterion']}", TEXTS[worst["criterion"]][worst["level_key"]])})

    parts = []
    for b in blocks:
        t = f"{b['title']} — {b['level_title']}. {MEANING[b['criterion']]} "
        if b["criterion"] in (best["criterion"], worst["criterion"]):
            t += f"{fact(b)}: подробнее об этом выше."
        else:
            t += f"{fact(b)}. " + _variant(f"{period['id']}:{member_id}:{b['criterion']}", TEXTS[b["criterion"]][b["level_key"]])
        if b.get("neg_high"):
            t += (f" {_people(b['neg'])} {plural(b['neg'], 'отметил', 'отметили', 'отметили')} «{b['neg_label']}» "
                  f"(в среднем по группе {_num(b['neg_avg'])}). Опрос не говорит почему: это ответ на конкретный вопрос, а не оценка вас.")
        parts.append(t)
    interp.append({"title": "По каждому вопросу", "text": "\n".join(parts)})

    mut = []
    for b in socio:
        if b["given"] == 0:
            continue
        if b["mutual"] is None:
            mut.append(f"{b['short']} — число взаимных скрыто, чтобы по нему нельзя было понять, кто именно ответил")
        else:
            mut.append(f"{b['short']} — из {_people(b['given'])}, которых вы выбрали, вас выбрали {b['mutual']}")
    if mut:
        tw = next((b for b in socio if b["criterion"] == "teamwork"), None)
        extra = ""
        if tw and tw["given"] >= 2 * max(tw["avg"], 1) and tw["received"] < tw["avg"]:
            extra = " Вы отметили многих, а вас отметили реже: это просто разница в том, как широко люди выбирают."
        interp.append({"title": "Взаимность", "text": "Взаимный выбор — когда вы выбрали человека и он выбрал вас по тому же вопросу. "
                       + "; ".join(mut).capitalize() + "." + extra})

    if prev_counts:
        diffs = []
        for b in blocks:
            d = b["received"] - prev_counts.get(b["criterion"], 0)
            if abs(d) <= 3:
                diffs.append(f"{b['short']}: {b['received']} (было {prev_counts[b['criterion']]}, в пределах обычных колебаний)")
            else:
                diffs.append(f"{b['short']}: {b['received']} (было {prev_counts[b['criterion']]}, "
                             f"{'больше' if d > 0 else 'меньше'} на {abs(d)})")
        interp.append({"title": f"По сравнению с прошлым опросом ({prev_title})",
                       "text": "; ".join(diffs) + ". Разница в 2–3 человека бывает от опроса к опросу сама по себе, тренд видно только по нескольким опросам подряд."})
    else:
        interp.append({"title": "По сравнению с прошлым опросом", "text": "Сравнить пока не с чем: это ваш первый опубликованный опрос."})

    interp.append({"title": PROFILES[profile][0], "text": PROFILES[profile][1]})
    interp.append({"title": "Что можно сделать, если хочется", "text": ADVICE[overall_lvl]})
    interp.append({"title": "Как читать этот отчёт", "text":
                   f"Это мнение группы из {n} человек в одном опросе. На ответы влияют совместная работа, знакомства и то, кто с кем чаще пересекается. "
                   "Отметка «не хотел бы» — ответ на конкретный вопрос, а не оценка человека. Отчёт не оценивает вас как личность и ничего не требует; советы выше — по желанию."})

    # Динамика: число выборов «за» по опросам
    history = []
    for p in published_periods(svc):
        if member_id in svc.submitted_answers(p):
            ps = svc.stats(p)
            if member_id not in ps["members"]:
                continue
            row = {"title": p["title"], "date": p.get("date")}
            for c in ("teamwork", "leisure"):
                qid = by_crit.get(c, {}).get("+")
                if qid is not None:
                    row[c] = ps["members"][member_id]["received"][qid]
                    row[c + "_avg"] = sum(v["received"][qid] for v in ps["members"].values()) / ps["n"]
            history.append(row)

    criteria = [{"criterion": b["criterion"], "title": b["title"], "level": b["level"], "level_title": b["level_title"],
                 "percentile": b["percentile"], "text": "", "received": b["received"],
                 "received_range": scoring.received_range(b["received"]), "group_avg_received": b["avg"]} for b in blocks]
    return {"period": {"id": period["id"], "title": period["title"], "date": period.get("date")}, "n": n, "k": st["k"],
            "out_of": out_of, "respondents": len(svc.submitted_answers(period)),
            "headline": headline, "above": above, "total": total, "blocks": blocks,
            "specialist": {"S": mine["S"], "S_group": sum(v["S"] for v in members) / n,
                           "E": mine["E"], "E_group": sum(v["E"] for v in members) / n,
                           "place_range": scoring.place_range(mine["place"])},
            "S": mine["S"], "E": mine["E"], "place_range": scoring.place_range(mine["place"]),
            "rows": rows, "criteria": criteria,
            "overall": {"level": LEVEL_CLASS[overall_lvl], "level_title": LEVEL_TITLES[overall_lvl],
                        "text": OVERALL_TEXTS[overall_lvl], "percentile": round(avg_p * 100)},
            "profile": {"key": profile, "title": PROFILES[profile][0], "text": PROFILES[profile][1],
                        "business": round(biz * 100), "personal": round(per * 100)},
            "interpretation": interp, "history": history}
