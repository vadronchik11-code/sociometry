import hmac
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import Config
from app.storage import Storage

SEED = Path(__file__).resolve().parent.parent / "seed" / "questions.json"


# Кто проходит социометрию и кого можно выбрать. Руководство — часть группы, аналитик нет.
SURVEY_ROLES = ("participant", "management")


class ServiceError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SurveyService:
    def __init__(self, storage: Storage, config: Config):
        self.s = storage
        self.config = config
        self._seed_questions()

    def _seed_questions(self) -> None:
        def seed(d: dict):
            if not d["questions"]:
                d["questions"] = json.loads(SEED.read_text(encoding="utf-8"))
        self.s.open.update(seed)

    # --- участники ---------------------------------------------------------
    def role_for(self, email: str) -> str:
        e = email.lower()
        if e in self.config.analyst_emails:
            return "analyst"
        if e in self.config.management_emails:
            return "management"
        return "participant"

    def register(self, full_name: str, email: str, password: str | None = None) -> dict:
        email = email.strip().lower()
        full_name = " ".join(full_name.split())
        if not full_name or "@" not in email:
            raise ServiceError(400, "Укажите ФИО и почту")
        role = self.role_for(email)
        required = {"analyst": self.config.analyst_password,
                    "management": self.config.management_password}.get(role)
        if required and not hmac.compare_digest((password or "").encode(), required.encode()):
            raise ServiceError(403, "Для этой почты нужен пароль сотрудника" if not password else "Неверный пароль")

        def op(d: dict):
            for m in d["members"]:
                if m["email"] == email:
                    m["role"] = self.role_for(email)  # роль берётся из настроек при каждом входе
                    return m
            m = {
                "id": max((x["id"] for x in d["members"]), default=0) + 1,
                "full_name": full_name,
                "email": email,
                "token": uuid.uuid4().hex,
                "role": self.role_for(email),
                "registered_at": _now(),
                "joined_at": None,
            }
            d["members"].append(m)
            return m
        return self.s.open.update(op)

    def anon_secret(self) -> str:
        """Ключ для случайных номеров узлов в публичных социограммах. Хранится в закрытой базе."""
        secret = self.s.closed.read().get("anon_secret")
        if secret:
            return secret

        def op(d: dict):
            d.setdefault("anon_secret", uuid.uuid4().hex + uuid.uuid4().hex)
            return d["anon_secret"]
        return self.s.closed.update(op)

    def member_by_token(self, token: str) -> dict | None:
        return next((m for m in self.s.open.read()["members"] if m["token"] == token), None)

    def participants(self, period: dict | None = None) -> list[dict]:
        """Члены группы. Для закрытого опроса — только те, кто был в группе на момент закрытия,
        чтобы новые аккаунты не меняли старые отчёты."""
        ms = [m for m in self.s.open.read()["members"] if m["role"] in SURVEY_ROLES]
        if period and period.get("closed_at"):
            ms = [m for m in ms if (m.get("registered_at") or "") <= period["closed_at"]]
        if period and period.get("excluded"):
            ms = [m for m in ms if m["id"] not in period["excluded"]]
        return ms

    def excluded(self, period: dict) -> list[dict]:
        ids = set(period.get("excluded") or [])
        return [m for m in self.s.open.read()["members"] if m["id"] in ids]

    def set_excluded(self, period_id: int, member_id: int, excluded: bool) -> dict:
        """Исключить из опроса человека, который ушёл из группы (или вернуть его)."""
        def op(d: dict):
            p = next((x for x in d["periods"] if x["id"] == period_id), None)
            if not p:
                raise ServiceError(404, "Период не найден")
            if p["status"] != "open":
                raise ServiceError(409, "Опрос уже закрыт")
            if not any(m["id"] == member_id for m in d["members"]):
                raise ServiceError(404, "Нет такого участника")
            ex = set(p.get("excluded") or [])
            ex.add(member_id) if excluded else ex.discard(member_id)
            p["excluded"] = sorted(ex)
            return p
        return self.s.open.update(op)

    def not_submitted(self, period: dict) -> list[dict]:
        subs = self.s.closed.read()["submissions"].get(str(period["id"]), {})
        return [m for m in self.participants(period) if subs.get(str(m["id"]), {}).get("status") != "submitted"]

    # --- периоды -----------------------------------------------------------
    def create_period(self, title: str, question_ids: list[int] | None = None,
                      date: str | None = None) -> dict:
        def op(d: dict):
            running = next((p for p in d["periods"] if p["status"] == "open"), None)
            if running:
                raise ServiceError(409, f"Сейчас идёт опрос «{running['title']}». Сначала закройте его, "
                                        "иначе у участников пропадёт незаконченная анкета.")
            qids = question_ids or [q["id"] for q in d["questions"] if q["kind"] == "permanent"]
            known = {q["id"] for q in d["questions"]}
            if not set(qids) <= known:
                raise ServiceError(400, "Неизвестные вопросы")
            p = {
                "id": max((x["id"] for x in d["periods"]), default=0) + 1,
                "title": title,
                "status": "open",
                "question_ids": qids,
                "date": date or datetime.now(timezone.utc).strftime("%Y-%m"),
                "published": False,
                "report_text": "",
                "created_at": _now(),
            }
            d["periods"].append(p)
            return p
        return self.s.open.update(op)

    def close_period(self, period_id: int) -> dict:
        def op(d: dict):
            p = next((x for x in d["periods"] if x["id"] == period_id), None)
            if not p:
                raise ServiceError(404, "Период не найден")
            left = self.not_submitted(p)
            if left:
                names = ", ".join(m["full_name"] for m in left[:5]) + (" и др." if len(left) > 5 else "")
                raise ServiceError(409, f"Опрос прошли не все: осталось {len(left)} ({names}). "
                                        "Социометрия считается, только когда пройдут все. Ушедших из группы можно исключить из опроса.")
            p["status"] = "closed"
            p["closed_at"] = _now()
            return p
        return self.s.open.update(op)

    def set_report(self, period_id: int, text: str | None = None, published: bool | None = None) -> dict:
        def op(d: dict):
            p = next((x for x in d["periods"] if x["id"] == period_id), None)
            if not p:
                raise ServiceError(404, "Период не найден")
            if published and p["status"] != "closed":
                raise ServiceError(409, "Публиковать можно только закрытый опрос, а закрыть его можно, когда пройдут все")
            if text is not None:
                p["report_text"] = text
            if published is not None:
                p["published"] = published
            return p
        return self.s.open.update(op)

    def get_period(self, period_id: int) -> dict:
        p = next((x for x in self.s.open.read()["periods"] if x["id"] == period_id), None)
        if not p:
            raise ServiceError(404, "Период не найден")
        return p

    def current_period(self) -> dict:
        open_ = [p for p in self.s.open.read()["periods"] if p["status"] == "open"]
        if not open_:
            raise ServiceError(404, "Нет открытого опроса")
        return open_[-1]

    def period_questions(self, period: dict) -> list[dict]:
        by_id = {q["id"]: q for q in self.s.open.read()["questions"]}
        return [by_id[i] for i in period["question_ids"]]

    # --- частные вопросы ---------------------------------------------------
    def create_custom_question(self, text: str, answer_type: str = "people",
                               anonymous: bool = False, period_id: int | None = None,
                               visibility: str = "management") -> dict:
        text = text.strip()
        if not text:
            raise ServiceError(400, "Введите текст вопроса")
        if answer_type not in ("people", "text"):
            raise ServiceError(400, "Тип ответа: people или text")
        if visibility not in ("management", "analyst"):
            raise ServiceError(400, "Видимость: management или analyst")
        # anonymous=True: руководство (если visibility=management) видит ответы, но не авторов.

        def op(d: dict):
            q = {
                "id": max((x["id"] for x in d["questions"]), default=0) + 1,
                "kind": "custom", "text": text, "answer_type": answer_type,
                "criterion": None, "polarity": None, "pair_with": None,
                "anonymous": anonymous, "visibility": visibility, "created_at": _now(),
            }
            d["questions"].append(q)
            return q
        q = self.s.open.update(op)
        if period_id is not None:
            self.add_question_to_period(period_id, q["id"])
        return q

    def list_custom_questions(self) -> list[dict]:
        return [q for q in self.s.open.read()["questions"] if q["kind"] == "custom"]

    def add_question_to_period(self, period_id: int, question_id: int) -> dict:
        def op(d: dict):
            p = next((x for x in d["periods"] if x["id"] == period_id), None)
            q = next((x for x in d["questions"] if x["id"] == question_id), None)
            if not p or not q:
                raise ServiceError(404, "Период или вопрос не найден")
            if p["status"] != "open":
                raise ServiceError(409, "Опрос закрыт")
            if question_id in p["question_ids"]:
                return p
            by_id = {x["id"]: x for x in d["questions"]}
            if q["kind"] == "custom":  # частные идут перед постоянными
                pos = next((i for i, qid in enumerate(p["question_ids"])
                            if by_id[qid]["kind"] == "permanent"), len(p["question_ids"]))
                p["question_ids"].insert(pos, question_id)
            else:
                p["question_ids"].append(question_id)
            return p
        return self.s.open.update(op)

    def period_custom_questions(self, period: dict) -> list[dict]:
        """Частные вопросы опроса с числом ответов (из всех анкет, включая черновики)."""
        open_raw = self.s.open.read()["custom_answers"].get(str(period["id"]), {})
        closed_raw = self.s.closed.read()["answers"].get(str(period["id"]), {})
        out = []
        for q in self.period_questions(period):
            if q["kind"] != "custom":
                continue
            raw = closed_raw if self.is_private(q) else open_raw
            n = sum(1 for qs in raw.values() if str(q["id"]) in qs)
            out.append({k: q.get(k) for k in ("id", "text", "answer_type", "anonymous", "visibility")} | {"answers": n})
        return out

    def remove_question_from_period(self, period_id: int, question_id: int) -> dict:
        period = self.get_period(period_id)
        if period["status"] != "open":
            raise ServiceError(409, "Опрос закрыт")
        q = next((x for x in self.period_custom_questions(period) if x["id"] == question_id), None)
        if not q:
            raise ServiceError(404, "В этом опросе нет такого частного вопроса")
        if q["answers"]:
            raise ServiceError(409, "На вопрос уже отвечали, удалить его нельзя")

        def op(d: dict):
            p = next(x for x in d["periods"] if x["id"] == period_id)
            p["question_ids"] = [i for i in p["question_ids"] if i != question_id]
        self.s.open.update(op)
        return {"removed": question_id}

    def custom_answers_report(self, period: dict, include_private: bool = False) -> list[dict]:
        """Ответы на частные вопросы (только из отправленных анкет).

        Руководство (include_private=False) получает вопросы с visibility=management;
        у анонимных из них авторы убраны, а порядок ответов не совпадает с порядком отправки.
        Аналитик (include_private=True) видит всё с именами.
        """
        data = self.s.open.read()
        closed_db = self.s.closed.read()
        closed = closed_db["answers"].get(str(period["id"]), {})
        subs = closed_db["submissions"].get(str(period["id"]), {})
        names = {m["id"]: m["full_name"] for m in data["members"]}
        open_raw = data["custom_answers"].get(str(period["id"]), {})
        report = []
        for q in self.period_questions(period):
            if q["kind"] != "custom":
                continue
            vis = q.get("visibility", "management")
            if vis != "management" and not include_private:
                continue
            hide_names = q["anonymous"] and not include_private
            raw = closed if self.is_private(q) else open_raw
            rows = []
            for mid, qs in raw.items():
                a = qs.get(str(q["id"]))
                if not a or subs.get(mid, {}).get("status") != "submitted":
                    continue
                if not (a.get("targets") or a.get("none") or (a.get("text") or "").strip()):
                    continue
                rows.append({"member": None if hide_names else names.get(int(mid), mid),
                             "targets": [names.get(t, t) for t in a.get("targets", [])],
                             "none": a.get("none", False), "text": a.get("text")})
            rows.sort(key=lambda r: (r["member"] or "", r["text"] or "", r["targets"]))
            hidden = 0
            if hide_names and len(rows) < 5:  # меньше 5 ответов без имён — авторов легко угадать
                hidden, rows = len(rows), []
            report.append({"question_id": q["id"], "text": q["text"], "anonymous": q["anonymous"],
                           "visibility": vis, "answer_type": q.get("answer_type", "people"), "answers": rows,
                           "hidden": hidden})
        return report

    # --- ответы ------------------------------------------------------------
    def _question(self, period: dict, question_id: int) -> dict:
        q = next((x for x in self.period_questions(period) if x["id"] == question_id), None)
        if not q:
            raise ServiceError(404, "Вопроса нет в этом опросе")
        return q

    @staticmethod
    def is_private(q: dict) -> bool:
        """Закрытые ответы (анонимные или без доступа руководства) лежат в закрытой БД."""
        return q["anonymous"] or q.get("visibility", "management") == "analyst"

    def _answers_store(self, q: dict):
        if self.is_private(q):
            return self.s.closed, "answers"
        return self.s.open, "custom_answers"

    def _my_answers(self, period_id: int, member_id: int, q: dict) -> dict:
        store, key = self._answers_store(q)
        return store.read()[key].get(str(period_id), {}).get(str(member_id), {})

    def _is_submitted(self, period_id: int, member_id: int) -> bool:
        sub = self.s.closed.read()["submissions"].get(str(period_id), {}).get(str(member_id))
        return bool(sub and sub["status"] == "submitted")

    @staticmethod
    def _require_survey_role(member: dict, period: dict | None = None) -> None:
        if member["role"] not in SURVEY_ROLES:
            raise ServiceError(403, "Аналитик не входит в группу и опрос не проходит")
        if period and member["id"] in (period.get("excluded") or []):
            raise ServiceError(403, "Вы исключены из этого опроса. Если это ошибка, напишите аналитику")

    def save_answer(self, period: dict, member: dict, question_id: int,
                    targets: list[int], none: bool = False, text: str | None = None) -> dict:
        self._require_survey_role(member, period)
        if period["status"] != "open":
            raise ServiceError(409, "Опрос закрыт")
        if self._is_submitted(period["id"], member["id"]):
            raise ServiceError(409, "Ответы уже отправлены")
        q = self._question(period, question_id)
        targets = list(dict.fromkeys(targets))
        if none and targets:
            raise ServiceError(400, "Нельзя выбрать «Никто» вместе с людьми")
        if member["id"] in targets:
            raise ServiceError(400, "Нельзя выбрать самого себя")
        known = {m["id"] for m in self.participants(period)}
        if not set(targets) <= known:
            raise ServiceError(400, "Среди выбранных есть неизвестный участник")

        value = {"targets": targets, "none": none}
        if text is not None:
            value["text"] = text
        store, key = self._answers_store(q)

        def op(d: dict):
            d[key].setdefault(str(period["id"]), {}).setdefault(str(member["id"]), {})[str(q["id"])] = value
        store.update(op)

        return {"saved": True, "warnings": self._conflicts_for(period, member, q, targets)}

    def _targets(self, period: dict, member_id: int, q: dict) -> set[int]:
        a = self._my_answers(period["id"], member_id, q).get(str(q["id"]), {})
        return set(a.get("targets", []))

    def _conflicts_for(self, period: dict, member: dict, q: dict, targets: list[int]) -> list[dict]:
        pair_id = q.get("pair_with")
        if not pair_id or pair_id not in period["question_ids"]:
            return []
        pair_q = self._question(period, pair_id)
        both = set(targets) & self._targets(period, member["id"], pair_q)
        return [{"target_id": t, "paired_question_id": pair_id,
                 "message": f"Этот человек уже выбран в вопросе {pair_id}"} for t in sorted(both)]

    def members_for_question(self, period: dict, member: dict, question_id: int, query: str = "") -> list[dict]:
        self._require_survey_role(member, period)
        q = self._question(period, question_id)
        chosen = self._targets(period, member["id"], q)
        blocked: set[int] = set()
        if q.get("pair_with") and q["pair_with"] in period["question_ids"]:
            blocked = self._targets(period, member["id"], self._question(period, q["pair_with"]))
        norm = lambda s: s.lower().replace("ё", "е")
        needle = norm(query.strip())
        out = []
        for m in self.participants(period):
            if m["id"] == member["id"] or (needle and needle not in norm(m["full_name"])):
                continue
            state = "chosen" if m["id"] in chosen else "grey" if m["id"] in blocked else "available"
            out.append({"id": m["id"], "full_name": m["full_name"], "state": state})
        return sorted(out, key=lambda x: x["full_name"])

    def my_answers(self, period: dict, member: dict) -> dict:
        res = {}
        for q in self.period_questions(period):
            a = self._my_answers(period["id"], member["id"], q).get(str(q["id"]))
            if a is not None:
                res[q["id"]] = a
        return res

    def submit(self, period: dict, member: dict) -> dict:
        self._require_survey_role(member, period)
        if period["status"] != "open":
            raise ServiceError(409, "Опрос закрыт")
        if self._is_submitted(period["id"], member["id"]):
            raise ServiceError(409, "Ответы уже отправлены")
        mine = self.my_answers(period, member)
        missing = [q["id"] for q in self.period_questions(period)
                   if q["kind"] == "permanent" and q["id"] not in mine]
        if missing:
            raise ServiceError(400, f"Не отвечено на вопросы: {missing}")

        def close(d: dict):
            d["submissions"].setdefault(str(period["id"]), {})[str(member["id"])] = {
                "status": "submitted", "submitted_at": _now()}
        self.s.closed.update(close)

        def complete(d: dict):
            lst = d["completions"].setdefault(str(period["id"]), [])
            if member["id"] not in lst:
                lst.append(member["id"])
        self.s.open.update(complete)
        return {"submitted": True}

    # --- для руководства и аналитика --------------------------------------
    def completion(self, period: dict) -> dict:
        done = set(self.s.open.read()["completions"].get(str(period["id"]), []))
        people = self.participants(period)
        excluded = [m["full_name"] for m in self.excluded(period)]
        return {
            "excluded": excluded,
            "complete": not self.not_submitted(period),
            "done": [m["full_name"] for m in people if m["id"] in done],
            "not_done": [m["full_name"] for m in people if m["id"] not in done],
        }

    def submitted_answers(self, period: dict) -> dict[int, dict[int, set[int]]]:
        """member_id -> question_id -> выбранные. Только отправленные анкеты."""
        closed = self.s.closed.read()
        subs = closed["submissions"].get(str(period["id"]), {})
        raw = closed["answers"].get(str(period["id"]), {})
        out: dict[int, dict[int, set[int]]] = {}
        for mid, qs in raw.items():
            if subs.get(mid, {}).get("status") != "submitted":
                continue
            out[int(mid)] = {int(qid): set(a.get("targets", [])) for qid, a in qs.items()}
        return out

    def flags(self, period: dict) -> list[dict]:
        answers = self.submitted_answers(period)
        questions = {q["id"]: q for q in self.period_questions(period)}
        n = len(self.participants(period))
        flags = []
        for mid, qs in answers.items():
            for qid, targets in qs.items():
                q = questions.get(qid)
                if not q:
                    continue
                pair = q.get("pair_with")
                if pair and q["polarity"] == "+" and pair in qs:
                    for t in sorted(targets & qs[pair]):
                        flags.append({"kind": "conflict", "member_id": mid,
                                      "question_id": qid, "paired_question_id": pair, "target_id": t})
                if n > 1 and len(targets) > self.config.suspicious_share * (n - 1):
                    flags.append({"kind": "suspicious", "member_id": mid, "question_id": qid,
                                  "chosen": len(targets)})
            perm = [t for qid, t in qs.items() if questions.get(qid, {}).get("kind") == "permanent"]
            if perm and all(not t for t in perm):
                flags.append({"kind": "individualist", "member_id": mid})
        return flags

    def stats(self, period: dict) -> dict:
        from app.services.scoring import compute_stats
        questions = [q for q in self.period_questions(period) if q["kind"] == "permanent"]
        member_ids = [m["id"] for m in self.participants(period)]
        answers = self.submitted_answers(period)
        return compute_stats(member_ids, questions, answers, set(answers))
