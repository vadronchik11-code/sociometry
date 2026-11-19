"""Заполняет сайт случайными демо-данными: участники, опрос, ответы, частные вопросы.

    .venv\\Scripts\\python seed_demo.py                 # 60 участников в папку data
    .venv\\Scripts\\python seed_demo.py --n 40 --seed 7
"""
import argparse
import random

from app.config import Config
from app.services.survey import SurveyService
from app.storage import Storage

MALE = ["Алексей", "Артём", "Борис", "Виктор", "Глеб", "Данил", "Егор", "Илья", "Кирилл", "Максим",
        "Никита", "Олег", "Павел", "Роман", "Сергей", "Тимур", "Фёдор", "Ярослав", "Денис", "Матвей"]
FEMALE = ["Алина", "Анна", "Вера", "Дарья", "Ева", "Ирина", "Карина", "Мария", "Наталья", "Ольга",
          "Полина", "Софья", "Татьяна", "Ульяна", "Юлия", "Яна", "Алиса", "Диана", "Ксения", "Елена"]
SURNAMES = ["Иванов", "Петров", "Сидоров", "Кузнецов", "Смирнов", "Попов", "Волков", "Соколов", "Орлов",
            "Лебедев", "Козлов", "Новиков", "Морозов", "Беляев", "Громов", "Фролов", "Зайцев", "Титов",
            "Крылов", "Васильев", "Макаров", "Фомин", "Ершов", "Белов", "Рогов"]

TEXT_LIKES = ["Атмосфера и люди", "Мероприятия прошли весело", "Много полезных знакомств", "Хорошая организация",
              "Поддержка новичков", "Школа актива", "Свобода делать свои проекты", "Командные выезды"]
TEXT_CHANGE = ["Больше информации заранее", "Чёткие дедлайны", "Меньше собраний, больше дела",
               "Распределять задачи равномернее", "Обратная связь после мероприятий", "Больше внимания новичкам"]
TEXT_WORRY = ["Выгорание к концу семестра", "Не хватает времени на учёбу", "Непонятно, кто за что отвечает",
              "Бывает неловко просить о помощи", "Хочется больше признания"]

CUSTOM = [
    ("Что вам больше всего понравилось в работе студсовета в этом семестре?", "text", False, "management", TEXT_LIKES),
    ("Что стоит изменить в организации мероприятий?", "text", False, "management", TEXT_CHANGE),
    ("Кого вы хотели бы видеть в руководстве в следующем семестре?", "people", False, "analyst", None),
    ("Что вас беспокоит, о чём трудно говорить открыто?", "text", True, "management", TEXT_WORRY),
    ("Кому вы благодарны за поддержку в этом семестре?", "people", True, "management", None),
]


# Сколько человек обычно выбирают в позитивных вопросах (как в реальных отчётах: работа > досуг > доверие).
POS_RANGE = {1: (5, 25), 3: (4, 22), 5: (10, 45), 7: (3, 18), 9: (2, 18)}


def make_people(rng: random.Random, n: int) -> list[str]:
    names: set[str] = set()
    while len(names) < n:
        if rng.random() < 0.5:
            names.add(f"{rng.choice(SURNAMES)} {rng.choice(MALE)}")
        else:
            names.add(f"{rng.choice(SURNAMES)}а {rng.choice(FEMALE)}")
    return sorted(names)


def weighted_sample(rng: random.Random, pool: list[int], weights: dict[int, float], k: int) -> list[int]:
    pool = list(pool)
    chosen: list[int] = []
    for _ in range(min(k, len(pool))):
        pick = rng.choices(pool, weights=[weights[m] for m in pool])[0]
        chosen.append(pick)
        pool.remove(pick)
    return chosen


PERIODS = [  # название, дата, множитель выборов, множитель отвержений, доля прошедших (закрытый опрос — только 100%), закрыт ли
    ("Февраль 2026", "2026-02", 0.75, 0.8, 1.0, True),
    ("Июнь 2026", "2026-06", 0.90, 1.0, 1.0, True),
    ("Сентябрь 2026", "2026-09", 0.85, 1.1, 1.0, True),
    ("Ноябрь 2026", "2026-11", 1.00, 0.9, 1.0, True),
    ("Декабрь 2026", "2026-12", 1.00, 1.0, 0.45, False),
]


def fill_period(svc, rng, period, members, like, dislike, group_of, mult, neg_mult, done_share):
    ids = [m["id"] for m in members]
    noise = {i: rng.lognormvariate(0, 0.15) for i in ids}
    done = rng.sample(members, int(len(members) * done_share))
    for m in done:
        others = [i for i in ids if i != m["id"]]
        pos_w = {t: like[t] * noise[t] * (3.0 if group_of[t] == group_of[m["id"]] else 1.0) for t in others}
        neg_w = {t: dislike[t] * (0.4 if group_of[t] == group_of[m["id"]] else 1.0) for t in others}
        chosen_pos: dict[int, list[int]] = {}
        for q in svc.period_questions(period):
            qid = q["id"]
            if q["kind"] == "permanent":
                if q["polarity"] == "+":
                    lo, hi = POS_RANGE[qid]
                    k = 0 if rng.random() < 0.04 else max(1, round(rng.randint(lo, hi) * mult))
                    t = weighted_sample(rng, others, pos_w, k)
                    chosen_pos[qid] = t
                elif q["polarity"] == "-":
                    k = 0 if rng.random() < 0.25 else max(1, round(rng.randint(1, 8) * neg_mult))
                    banned = set(chosen_pos.get(q["pair_with"], []))
                    pool = [o for o in others if o not in banned]
                    t = weighted_sample(rng, pool, {o: neg_w[o] for o in pool}, k)
                    if t and banned and rng.random() < 0.03:  # редкое противоречие
                        t[0] = rng.choice(sorted(banned))
                else:
                    t = weighted_sample(rng, others, pos_w, round(rng.randint(*POS_RANGE[9]) * mult))
                svc.save_answer(period, m, qid, t, none=not t)
            elif q.get("answer_type") == "text":
                texts = next(c[4] for c in CUSTOM if c[0] == q["text"])
                if rng.random() < 0.8:
                    svc.save_answer(period, m, qid, [], text=rng.choice(texts))
            elif rng.random() < 0.7:
                svc.save_answer(period, m, qid, weighted_sample(rng, others, pos_w, rng.randint(1, 4)), none=False)
        svc.submit(period, m)
    return len(done)


def main() -> None:
    import copy

    from app.services import reports
    from app.storage import CLOSED_DEFAULT, OPEN_DEFAULT

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60, help="число участников")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--reset", action="store_true", help="стереть все данные перед заполнением")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    cfg = Config() if args.data_dir is None else Config(data_dir=args.data_dir)
    storage = Storage(cfg.data_dir)
    if args.reset:
        storage.open.update(lambda d: (d.clear(), d.update(copy.deepcopy(OPEN_DEFAULT))))
        storage.closed.update(lambda d: (d.clear(), d.update(copy.deepcopy(CLOSED_DEFAULT))))
    svc = SurveyService(storage, cfg)

    members = [svc.register(name, f"demo{i + 1}@example.com") for i, name in enumerate(make_people(rng, args.n))]
    ids = [m["id"] for m in members]
    like = {i: rng.lognormvariate(0, 0.8) for i in ids}
    dislike = {i: rng.lognormvariate(0, 0.9) for i in ids}
    shuffled = ids[:]
    rng.shuffle(shuffled)
    group_of = {m: gi for gi in range(6) for m in shuffled[gi::6]}

    custom = [svc.create_custom_question(t, k, anon, None, vis) for t, k, anon, vis, _ in CUSTOM]
    for title, date, mult, neg_mult, done_share, closed in PERIODS:
        period = svc.create_period(title, date=date)
        for q in custom:
            svc.add_question_to_period(period["id"], q["id"])
        period = svc.get_period(period["id"])
        done = fill_period(svc, rng, period, members, like, dislike, group_of, mult, neg_mult, done_share)
        if closed:
            svc.close_period(period["id"])
            period = svc.get_period(period["id"])
            text = reports.draft_text(svc, period, reports.build_group_report(svc, period),
                                      reports.previous_report(svc, period))
            svc.set_report(period["id"], text, True)
        print(f"{title}: прошли {done} из {len(members)}{'' if closed else ' (опрос идёт)'}")
    print(f"Данные в папке: {cfg.data_dir}")


if __name__ == "__main__":
    main()
