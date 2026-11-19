import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    cfg = Config(data_dir=tmp_path, analyst_emails={"analyst@x.ru"}, management_emails={"boss@x.ru"})
    return TestClient(create_app(cfg))


def reg(client, name, email):
    r = client.post("/register", json={"full_name": name, "email": email})
    assert r.status_code == 200
    d = r.json()
    return d["member_id"], {"X-Token": d["token"]}


def setup(client):
    _, analyst = reg(client, "Аналитик", "analyst@x.ru")
    people = [reg(client, f"Участник {i}", f"p{i}@x.ru") for i in range(1, 5)]
    client.post("/analyst/periods", json={"title": "Тест"}, headers=analyst)
    return analyst, people


def complete_all(client, people, choices=None):
    """Все участники проходят опрос (социометрия считается только при 100%)."""
    for i, (mid, h) in enumerate(people):
        fill(client, h, (choices or {}).get(mid, {}))
        assert client.post("/survey/submit", headers=h).status_code == 200


def test_register_is_idempotent(client):
    a = client.post("/register", json={"full_name": "А Б", "email": "A@x.ru"}).json()
    b = client.post("/register", json={"full_name": "А Б", "email": "a@x.ru"}).json()
    assert a["token"] == b["token"]


def test_roles_protected(client):
    analyst, people = setup(client)
    _, h = people[0]
    assert client.get("/analyst/stats/1", headers=h).status_code == 403
    assert client.get("/analyst/stats/1", headers=analyst).status_code == 200


def test_grey_cards_and_conflict_warning(client):
    analyst, people = setup(client)
    (me, h), (b, _), (c, _), _ = people
    r = client.put("/survey/answers/3", json={"targets": [b, c]}, headers=h)
    assert r.json()["warnings"] == []
    lst = client.get("/members", params={"question_id": 4}, headers=h).json()
    states = {m["id"]: m["state"] for m in lst}
    assert states[b] == "grey" and states[c] == "grey"
    # Выбрать серого можно, но приходит предупреждение.
    r = client.put("/survey/answers/4", json={"targets": [b]}, headers=h)
    assert r.status_code == 200
    assert r.json()["warnings"][0]["target_id"] == b


def test_validation(client):
    analyst, people = setup(client)
    (me, h), (b, _), _, _ = people
    assert client.put("/survey/answers/1", json={"targets": [me]}, headers=h).status_code == 400
    assert client.put("/survey/answers/1", json={"targets": [999]}, headers=h).status_code == 400
    assert client.put("/survey/answers/1", json={"targets": [b], "none": True}, headers=h).status_code == 400


def fill(client, h, targets_by_q):
    for q in range(1, 10):
        t = targets_by_q.get(q, [])
        r = client.put(f"/survey/answers/{q}", json={"targets": t, "none": not t}, headers=h)
        assert r.status_code == 200


def test_submit_flow_flags_and_completion(client):
    analyst, people = setup(client)
    (a, ha), (b, hb), (c, hc), (d, hd) = people
    # Нельзя отправить неполную анкету.
    assert client.post("/survey/submit", headers=ha).status_code == 400
    fill(client, ha, {5: [b], 3: [b], 4: [b]})     # конфликт по паре 3/4
    fill(client, hb, {5: [a]})
    fill(client, hc, {})                            # «Никто» везде
    for h in (ha, hb, hc):
        assert client.post("/survey/submit", headers=h).status_code == 200
    # Повторная отправка и правка после отправки закрыты.
    assert client.post("/survey/submit", headers=ha).status_code == 409
    assert client.put("/survey/answers/5", json={"targets": []}, headers=ha).status_code == 409

    boss = reg(client, "Руководитель", "boss@x.ru")[1]
    comp = client.get("/management/completion/1", headers=boss).json()
    # Руководство тоже часть группы и должно пройти опрос, аналитик — нет.
    assert len(comp["done"]) == 3 and sorted(comp["not_done"]) == ["Руководитель", "Участник 4"]
    # Руководству нельзя в аналитику.
    assert client.get("/analyst/flags/1", headers=boss).status_code == 403

    kinds = {(f["kind"], f["member_id"]) for f in client.get("/analyst/flags/1", headers=analyst).json()}
    assert ("conflict", a) in kinds
    assert ("individualist", c) in kinds

    stats = client.get("/analyst/stats/1", headers=analyst).json()
    assert stats["group"]["teamwork"]["mutual_positive_pairs"] == 1


def test_custom_questions_flow(client):
    analyst, people = setup(client)
    (a, ha), (b, hb), _, _ = people
    boss = reg(client, "Руководитель", "boss@x.ru")[1]
    # Участнику создавать вопросы нельзя.
    assert client.post("/staff/questions", json={"text": "?"}, headers=ha).status_code == 403
    q = client.post("/staff/questions", headers=boss,
                    json={"text": "Что улучшить?", "answer_type": "text", "period_id": 1}).json()
    q2 = client.post("/staff/questions", headers=boss,
                     json={"text": "Кого наградить?", "answer_type": "people", "period_id": 1}).json()
    survey = client.get("/survey/current", headers=ha).json()
    ids = [x["id"] for x in survey["questions"]]
    # Частные стоят перед постоянными.
    assert ids[:2] == [q["id"], q2["id"]] and ids[2] == 1
    assert client.put(f"/survey/answers/{q['id']}", json={"text": "Больше встреч"}, headers=ha).status_code == 200
    assert client.put(f"/survey/answers/{q2['id']}", json={"targets": [b]}, headers=ha).status_code == 200
    # Пока анкета не отправлена, руководство черновик не видит.
    assert client.get("/management/custom-answers/1", headers=boss).json()[0]["answers"] == []
    # Частные вопросы не обязательны для отправки.
    for i in range(1, 10):
        client.put(f"/survey/answers/{i}", json={"targets": [], "none": True}, headers=ha)
    assert client.post("/survey/submit", headers=ha).status_code == 200
    rep = client.get("/management/custom-answers/1", headers=boss).json()
    assert rep[0]["answers"][0] == {"member": "Участник 1", "targets": [], "none": False, "text": "Больше встреч"}
    assert rep[1]["answers"][0]["targets"] == ["Участник 2"]
    # Участнику ответы руководства недоступны.
    assert client.get("/management/custom-answers/1", headers=ha).status_code == 403


def test_role_updates_for_existing_member(tmp_path):
    plain = TestClient(create_app(Config(data_dir=tmp_path)))
    assert plain.post("/register", json={"full_name": "Б", "email": "boss@x.ru"}).json()["role"] == "participant"
    with_roles = TestClient(create_app(Config(data_dir=tmp_path, management_emails={"boss@x.ru"})))
    assert with_roles.post("/register", json={"full_name": "Б", "email": "boss@x.ru"}).json()["role"] == "management"


def test_visibility_of_custom_questions(client):
    analyst, people = setup(client)
    (a, ha), (b, _), _, _ = people
    boss = reg(client, "Руководитель", "boss@x.ru")[1]
    mk = lambda **kw: client.post("/staff/questions", headers=boss,
                                  json={"answer_type": "text", "period_id": 1, **kw}).json()
    open_q = mk(text="Открытый")
    priv_q = mk(text="Только аналитик", visibility="analyst")
    anon_q = mk(text="Анонимный", anonymous=True)
    hidden_q = mk(text="Скрытый", anonymous=True, visibility="analyst")
    assert anon_q["visibility"] == "management"
    for q in (open_q, priv_q, anon_q, hidden_q):
        assert client.put(f"/survey/answers/{q['id']}", json={"text": "ответ"}, headers=ha).status_code == 200
    for i in range(1, 10):
        client.put(f"/survey/answers/{i}", json={"targets": [], "none": True}, headers=ha)
    client.post("/survey/submit", headers=ha)
    boss_view = {r["text"]: r for r in client.get("/management/custom-answers/1", headers=boss).json()}
    # Руководство видит именной вопрос с автором и анонимный без автора.
    assert set(boss_view) == {"Открытый", "Анонимный"}
    assert boss_view["Открытый"]["answers"][0]["member"] == "Участник 1"
    # Анонимных ответов меньше 5: руководство их пока не видит, только число.
    assert boss_view["Анонимный"]["answers"] == [] and boss_view["Анонимный"]["hidden"] == 1
    assert "Участник 1" not in str(boss_view["Анонимный"])
    analyst_view = {r["text"]: r for r in client.get("/analyst/custom-answers/1", headers=analyst).json()}
    assert set(analyst_view) == {"Открытый", "Только аналитик", "Анонимный", "Скрытый"}
    assert analyst_view["Анонимный"]["answers"][0]["member"] == "Участник 1"
    assert client.get("/analyst/custom-answers/1", headers=boss).status_code == 403


def test_reports_and_overview(client):
    analyst, people = setup(client)
    (a, ha), (b, hb), (c, hc), (d, hd) = people
    for h, t in ((ha, {5: [b], 1: [c]}), (hb, {5: [a]}), (hc, {5: [a, b]}), (hd, {})):
        fill(client, h, t)
        assert client.post("/survey/submit", headers=h).status_code == 200
    client.post("/analyst/periods/1/close", headers=analyst)
    # Неопубликованный отчёт публично недоступен.
    assert client.get("/public/report/1").status_code == 404
    assert client.get("/public/summary").json()["series"] == []
    draft = client.post("/analyst/periods/1/report/draft", headers=analyst).json()["text"]
    assert "## Общее состояние" in draft and "## Приоритетные сигналы" in draft
    assert client.put("/analyst/periods/1/report", json={"text": draft, "published": True}, headers=analyst).status_code == 200
    rep = client.get("/public/report/1").json()
    assert rep["respondents"] == 4 and rep["text"] == draft
    # В публичном отчёте нет имён.
    assert "Участник" not in str(rep)
    assert len(rep["sociograms"]["teamwork"]["nodes"]) == 4
    assert client.get("/public/summary").json()["series"][0]["title"] == "Тест"
    ov = client.get("/analyst/overview/1", headers=analyst).json()
    assert len(ov["members"]) == 4 and len(ov["submitted"]) == 4
    # Личный отчёт: диапазон вместо числа и никаких взаимных выборов.
    mine = client.get("/me/report/1", headers=ha).json()
    # Видимые взаимные — только ноль или когда среди выбранных осталось не меньше трёх невзаимных.
    assert all(r["mutual"] is None or r["mutual"] == 0 or r["given"] - r["mutual"] >= 3 for r in mine["rows"])
    assert any(r["mutual"] == 0 for r in mine["rows"])
    assert "received" in mine["rows"][0]
    assert client.get("/analyst/overview/1", headers=ha).status_code == 403


def test_personal_report_and_categories(client):
    analyst, people = setup(client)
    (a, ha), (b, hb), (c, hc), (d, hd) = people
    for h, t in ((ha, {5: [b, c], 7: [b]}), (hb, {5: [a]}), (hc, {5: [a, b]}), (hd, {6: [a]})):
        fill(client, h, t)
        client.post("/survey/submit", headers=h)
    client.post("/analyst/periods/1/close", headers=analyst)
    client.put("/analyst/periods/1/report", json={"text": "x", "published": True}, headers=analyst)
    mine = client.get("/me/report/1", headers=ha).json()
    assert {x["criterion"] for x in mine["criteria"]} == {"teamwork", "organizing", "trust", "leisure", "referent"}
    assert mine["overall"]["level"] in ("high", "mid", "low") and mine["overall"]["text"]
    assert len(mine["history"]) == 1
    rep = client.get("/public/report/1").json()
    # Числа меньше 3 в публичной структуре скрыты (None), остальные показаны.
    assert all(v is None or v == 0 or v >= 3 for v in rep["structure"].values())
    assert mine["profile"]["key"] in ("business", "personal", "even")
    ov = client.get("/analyst/overview/1", headers=analyst).json()
    assert ov["stats"]["members"][str(a)]["category"] in ov["categories"]
    assert len(ov["history"][str(a)]) == 1


def test_management_takes_survey_analyst_does_not(client):
    analyst, people = setup(client)
    boss_id, boss = reg(client, "Руководитель", "boss@x.ru")
    (a, ha), _, _, _ = people
    ids = {m["id"] for m in client.get("/members", params={"question_id": 1}, headers=ha).json()}
    analyst_id = client.post("/register", json={"full_name": "Аналитик", "email": "analyst@x.ru"}).json()["member_id"]
    assert boss_id in ids and analyst_id not in ids
    fill(client, boss, {5: [a]})
    assert client.post("/survey/submit", headers=boss).status_code == 200
    stats = client.get("/analyst/stats/1", headers=analyst).json()
    assert str(boss_id) in stats["members"] and str(analyst_id) not in stats["members"]


def test_members_after_close_do_not_change_old_reports(client):
    analyst, people = setup(client)
    svc = client.app.state.survey
    complete_all(client, people)
    assert client.post("/analyst/periods/1/close", headers=analyst).status_code == 200
    assert len(svc.participants(svc.get_period(1))) == 4
    svc.s.open.update(lambda d: d["members"].append({"id": 99, "full_name": "Новичок", "email": "new@x.ru",
                                                     "token": "t99", "role": "participant",
                                                     "registered_at": "2999-01-01T00:00:00+00:00"}))
    assert len(svc.participants(svc.get_period(1))) == 4
    assert client.get("/analyst/stats/1", headers=analyst).json()["n"] == 4


def test_staff_password_required(tmp_path):
    cfg = Config(data_dir=tmp_path, analyst_emails={"an@x.ru"}, management_emails={"b@x.ru"},
                 analyst_password="secret-a", management_password="secret-b")
    c = TestClient(create_app(cfg))
    assert c.post("/register", json={"full_name": "А", "email": "an@x.ru"}).status_code == 403
    assert c.post("/register", json={"full_name": "А", "email": "an@x.ru", "password": "no"}).status_code == 403
    assert c.post("/register", json={"full_name": "А", "email": "an@x.ru", "password": "secret-a"}).json()["role"] == "analyst"
    assert c.post("/register", json={"full_name": "Б", "email": "b@x.ru", "password": "secret-a"}).status_code == 403
    # Участникам пароль не нужен.
    assert c.post("/register", json={"full_name": "В", "email": "v@x.ru"}).status_code == 200


def test_only_one_open_period_and_analyst_cannot_answer(client):
    analyst, people = setup(client)
    r = client.post("/analyst/periods", json={"title": "Второй"}, headers=analyst)
    assert r.status_code == 409 and "Тест" in r.json()["detail"]
    assert client.put("/survey/answers/1", json={"targets": [], "none": True}, headers=analyst).status_code == 403
    assert client.get("/survey/current", headers=analyst).status_code == 403
    complete_all(client, people)
    client.post("/analyst/periods/1/close", headers=analyst)
    assert client.post("/analyst/periods", json={"title": "Второй"}, headers=analyst).status_code == 200


def test_search_ignores_yo_and_remove_question(client):
    analyst, people = setup(client)
    (a, ha), _, _, _ = people
    reg(client, "Зайцев Фёдор", "f@x.ru")
    found = client.get("/members", params={"question_id": 1, "q": "федор"}, headers=ha).json()
    assert [m["full_name"] for m in found] == ["Зайцев Фёдор"]
    q = client.post("/staff/questions", headers=analyst, json={"text": "?", "answer_type": "text", "period_id": 1}).json()
    q2 = client.post("/staff/questions", headers=analyst, json={"text": "??", "answer_type": "text", "period_id": 1}).json()
    client.put(f"/survey/answers/{q2['id']}", json={"text": "ответ"}, headers=ha)
    listed = {x["id"]: x["answers"] for x in client.get("/staff/periods/1/questions", headers=analyst).json()}
    assert listed == {q["id"]: 0, q2["id"]: 1}
    assert client.delete(f"/staff/periods/1/questions/{q2['id']}", headers=analyst).status_code == 409
    assert client.delete(f"/staff/periods/1/questions/{q['id']}", headers=analyst).status_code == 200
    assert q["id"] not in [x["id"] for x in client.get("/survey/current", headers=ha).json()["questions"]]


def test_survey_counts_only_when_everyone_completed(client):
    analyst, people = setup(client)
    (a, ha), (b, hb), (c, hc), (d, hd) = people
    for mid, h in people[:3]:
        fill(client, h, {5: [x for x, _ in people if x != mid]})
        client.post("/survey/submit", headers=h)
    # Прошли трое из четырёх: закрыть и опубликовать нельзя.
    r = client.post("/analyst/periods/1/close", headers=analyst)
    assert r.status_code == 409 and "Участник 4" in r.json()["detail"]
    assert client.put("/analyst/periods/1/report", json={"published": True}, headers=analyst).status_code == 409
    assert client.get("/management/completion/1", headers=analyst).json()["complete"] is False
    # Участник 4 ушёл из группы: аналитик исключает его, и опрос можно закрыть.
    assert client.post(f"/analyst/periods/1/exclude/{d}", headers=analyst).status_code == 200
    assert client.get("/survey/current", headers=hd).status_code == 403
    assert d not in [m["id"] for m in client.get("/members", params={"question_id": 1}, headers=ha).json()]
    comp = client.get("/management/completion/1", headers=analyst).json()
    assert comp["complete"] is True and comp["excluded"] == ["Участник 4"]
    assert client.post("/analyst/periods/1/close", headers=analyst).status_code == 200
    rep = client.get("/analyst/report/1", headers=analyst).json()
    assert rep["n"] == 3 and rep["respondents"] == 3
    nodes = rep["sociograms"]["teamwork"]["nodes"]
    assert sorted(n["id"] for n in nodes) == [1, 2, 3]


def test_analyst_can_open_any_personal_report(client):
    analyst, people = setup(client)
    (a, ha), (b, hb), _, (d, hd) = people
    fill(client, ha, {5: [b]})
    client.post("/survey/submit", headers=ha)
    r = client.get(f"/analyst/personal/1/{a}", headers=analyst).json()
    assert r["member"]["name"] == "Участник 1" and r["participated"] is True and r["k"] == 5
    # Не прошедший тоже получает отчёт (по выборам о нём), но с пометкой.
    assert client.get(f"/analyst/personal/1/{d}", headers=analyst).json()["participated"] is False
    assert client.get(f"/analyst/personal/1/{a}", headers=ha).status_code == 403
    assert client.get("/analyst/personal/1/999", headers=analyst).status_code == 404


def test_anonymous_answers_shown_from_five(client):
    analyst, people = setup(client)
    extra = [reg(client, f"Доп {i}", f"x{i}@x.ru") for i in range(2)]
    boss = reg(client, "Руководитель", "boss@x.ru")[1]
    q = client.post("/staff/questions", headers=boss, json={"text": "Анон", "answer_type": "text", "anonymous": True, "period_id": 1}).json()
    for mid, h in people + extra:
        client.put(f"/survey/answers/{q['id']}", json={"text": f"ответ {mid}"}, headers=h)
        fill(client, h, {})
        client.post("/survey/submit", headers=h)
    r = {x["text"]: x for x in client.get("/management/custom-answers/1", headers=boss).json()}["Анон"]
    assert len(r["answers"]) == 6 and all(a["member"] is None for a in r["answers"])


def test_interpretation_levels_and_negatives():
    from app.services import reports
    assert reports.level_of(0.95, 60, 10) == "top"
    assert reports.level_of(0.70, 60, 10) == "high"
    assert reports.level_of(0.50, 60, 10) == "mid"
    assert reports.level_of(0.20, 60, 10) == "low"
    assert reports.level_of(0.05, 60, 10) == "min"
    assert reports.level_of(0.95, 60, 0) == "min"
    assert reports.level_of(0.95, 8, 3) == "high"  # маленькая группа: три уровня
    text = " ".join(t for c in reports.TEXTS.values() for lv in c.values() for t in lv)
    for banned in ("жесток", "честн", "чувство юмора"):
        assert banned not in text.lower()


def test_dev_autologin_is_off_by_default_and_local_only(tmp_path):
    off = TestClient(create_app(Config(data_dir=tmp_path, analyst_emails={"an@x.ru"})))
    assert off.get("/dev/as/analyst").status_code == 404
    on_cfg = Config(data_dir=tmp_path, analyst_emails={"an@x.ru"}, dev_autologin=True)
    # Запрос не с этого компьютера (у TestClient адрес «testclient») — закрыто.
    assert TestClient(create_app(on_cfg)).get("/dev/as/analyst").status_code == 404
    # С локального адреса — страница, которая сохраняет вход и открывает панель.
    local = TestClient(create_app(on_cfg), client=("127.0.0.1", 50000))
    r = local.get("/dev/as/analyst")
    assert r.status_code == 200 and "#/analyst" in r.text and "localStorage" in r.text
    assert local.get("/dev/as/hacker").status_code == 404
