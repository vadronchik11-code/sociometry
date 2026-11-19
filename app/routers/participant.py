from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.deps import current_member, survey_service
from app.services.survey import SurveyService

router = APIRouter(tags=["participant"])


class RegisterIn(BaseModel):
    full_name: str
    email: str
    password: str | None = None


class AnswerIn(BaseModel):
    targets: list[int] = Field(default_factory=list)
    none: bool = False
    text: str | None = None


@router.post("/register")
def register(body: RegisterIn, svc: SurveyService = Depends(survey_service)):
    m = svc.register(body.full_name, body.email, body.password)
    return {"member_id": m["id"], "token": m["token"], "role": m["role"], "full_name": m["full_name"]}


@router.get("/survey/current")
def current_survey(member: dict = Depends(current_member), svc: SurveyService = Depends(survey_service)):
    period = svc.current_period()
    svc._require_survey_role(member, period)
    return {
        "period": {"id": period["id"], "title": period["title"]},
        "questions": [{**{k: q[k] for k in ("id", "text", "polarity", "criterion", "pair_with")},
                       "answer_type": q.get("answer_type", "people"), "kind": q["kind"],
                       "anonymous": q["anonymous"], "visibility": q.get("visibility", "management")}
                      for q in svc.period_questions(period)],
        "answers": svc.my_answers(period, member),
        "submitted": svc._is_submitted(period["id"], member["id"]),
    }


@router.get("/members")
def members(question_id: int, q: str = "", member: dict = Depends(current_member),
            svc: SurveyService = Depends(survey_service)):
    return svc.members_for_question(svc.current_period(), member, question_id, q)


@router.put("/survey/answers/{question_id}")
def put_answer(question_id: int, body: AnswerIn, member: dict = Depends(current_member),
               svc: SurveyService = Depends(survey_service)):
    return svc.save_answer(svc.current_period(), member, question_id, body.targets, body.none, body.text)


@router.post("/survey/submit")
def submit(member: dict = Depends(current_member), svc: SurveyService = Depends(survey_service)):
    return svc.submit(svc.current_period(), member)
