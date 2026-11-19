import json
from pathlib import Path

from app.services import scoring

QUESTIONS = json.loads((Path(__file__).parent.parent / "app" / "seed" / "questions.json").read_text(encoding="utf-8"))


def test_formulas_match_personal_report():
    # Цифры из персонального отчёта: март 2026, n = 68, 5 критериев.
    assert round(scoring.status_index(141, 5, 68), 2) == 0.42
    assert round(scoring.expansiveness_index(180, 5, 68), 2) == 0.54
    # Gg за март 2026: 624 взаимных пары из 2278.
    assert round(scoring.group_index(624, 68) * 100, 1) == 27.4
    # Y: среднее число взаимных минусов 0,6 на человека даёт около 0,9 %.
    assert round(scoring.group_index(round(68 * 0.6 / 2), 68) * 100, 1) == 0.9


def test_mutual_pairs():
    choices = {1: {2, 3}, 2: {1}, 3: {2}}
    assert scoring.mutual_pairs(choices) == 1


def test_ranges():
    assert scoring.received_range(0) == "0"
    assert scoring.received_range(3) == "1-5"
    assert scoring.received_range(36) == "31+"
    assert scoring.place_range(11) == "11-20"
    assert scoring.place_range(10) == "1-10"


def test_compute_stats_small_group():
    members = [1, 2, 3]
    # Вопрос 5 (+, teamwork): 1<->2 взаимно, 3 выбрал 1. Вопрос 6 (-): 2 и 3 отвергли друг друга.
    answers = {
        1: {5: {2}},
        2: {5: {1}, 6: {3}},
        3: {5: {1}, 6: {2}},
    }
    stats = scoring.compute_stats(members, QUESTIONS, answers)
    assert stats["n"] == 3 and stats["k"] == 5
    teamwork = stats["group"]["teamwork"]
    assert teamwork["mutual_positive_pairs"] == 1
    assert teamwork["mutual_negative_pairs"] == 1
    assert round(teamwork["Gg"], 3) == round(1 / 3, 3)
    # Участник 1 получил два положительных выбора.
    assert stats["members"][1]["received"][5] == 2
    assert stats["members"][1]["mutual"][5] == 1
    assert stats["members"][1]["place"] == 1


def test_self_choice_and_unknown_ignored():
    answers = {1: {5: {1, 99}}}
    stats = scoring.compute_stats([1, 2], QUESTIONS, answers)
    assert stats["members"][1]["given"][5] == 0


def test_classify_categories():
    # Среднее «за» = 5 (sd 2), «против» = 1 (sd 1).
    c = lambda p, n: scoring.classify(p, n, 5, 2, 1, 1)
    assert c(0, 0) == "isolated"
    assert c(9, 0) == "star"
    assert c(6, 1) == "preferred"
    assert c(5, 1) == "accepted"
    assert c(3, 3) == "rejected"
    assert c(8, 3) == "controversial"


def test_stats_have_categories():
    answers = {1: {1: {2}, 2: {3}}, 2: {1: {1}}, 3: {1: {1, 2}}}
    st = scoring.compute_stats([1, 2, 3], QUESTIONS, answers)
    assert st["members"][3]["categories"]["leisure"] in scoring.CATEGORY_TITLES
    assert st["members"][1]["pos_total"] == 2


def test_mutual_hidden_only_when_it_reveals_people():
    v = scoring.mutual_visible
    # Ноль показываем всегда, как в прошлых отчётах: выбрал 8, взаимных 0.
    assert v(8, 0, 10, 60) and v(3, 0, 10, 60)
    # Выбрал 3, и все трое ответили взаимностью: про каждого ясно — скрываем.
    assert not v(3, 3, 10, 60)
    # Выбрал 5, взаимных 4 (как у Ковалёва по организаторским): скрываем.
    assert not v(5, 4, 36, 68)
    # Выбрал 20, взаимных 10 — угадать нельзя, показываем; выбрал 57, взаимных 45 — тоже.
    assert v(20, 10, 25, 60) and v(57, 45, 52, 68)
    # Выбрал 20, взаимных 19: про единственного «невзаимного» всё ясно — скрываем.
    assert not v(20, 19, 30, 60)
    # Почти все, кого он не выбирал, выбрали его: вместе с точным числом это раскрыло бы их — скрываем.
    assert not v(20, 10, 48, 60)
    # Сам никого не выбрал — взаимных нет, раскрывать нечего.
    assert v(0, 0, 5, 60)


def test_popular_with_usual_negatives_is_not_controversial():
    # Очень много «за» и «против» чуть выше среднего (z = +0,4) — это не противоречивый.
    assert scoring.classify_z(2.5, 0.4, 1.4, 2.0, 59, 9) != "controversial"
    # «Против» заметно выше среднего — противоречивый.
    assert scoring.classify_z(1.5, 1.6, 0.0, 2.2, 34, 17) == "controversial"
