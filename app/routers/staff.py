from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.deps import require_role, survey_service
from app.services.survey import SurveyService

router = APIRouter(tags=["staff"])


class PeriodIn(BaseModel):
    title: str
    question_ids: list[int] | None = None
    date: str | None = None


class QuestionIn(BaseModel):
    text: str
    answer_type: str = "people"
    anonymous: bool = False
    visibility: str = "management"
    period_id: int | None = None


@router.post("/staff/questions")
def create_question(body: QuestionIn, _: dict = Depends(require_role("management", "analyst")),
                    svc: SurveyService = Depends(survey_service)):
    return svc.create_custom_question(body.text, body.answer_type, body.anonymous, body.period_id, body.visibility)


@router.get("/staff/periods/{period_id}/questions")
def period_questions(period_id: int, _: dict = Depends(require_role("management", "analyst")),
                     svc: SurveyService = Depends(survey_service)):
    return svc.period_custom_questions(svc.get_period(period_id))


@router.delete("/staff/periods/{period_id}/questions/{question_id}")
def remove_question(period_id: int, question_id: int, _: dict = Depends(require_role("management", "analyst")),
                    svc: SurveyService = Depends(survey_service)):
    return svc.remove_question_from_period(period_id, question_id)


@router.get("/staff/questions")
def list_questions(_: dict = Depends(require_role("management", "analyst")),
                   svc: SurveyService = Depends(survey_service)):
    return svc.list_custom_questions()


@router.post("/staff/periods/{period_id}/questions/{question_id}")
def add_question(period_id: int, question_id: int,
                 _: dict = Depends(require_role("management", "analyst")),
                 svc: SurveyService = Depends(survey_service)):
    return svc.add_question_to_period(period_id, question_id)


@router.get("/management/custom-answers/{period_id}")
def custom_answers(period_id: int, _: dict = Depends(require_role("management", "analyst")),
                   svc: SurveyService = Depends(survey_service)):
    return svc.custom_answers_report(svc.get_period(period_id))


@router.get("/analyst/custom-answers/{period_id}")
def analyst_custom_answers(period_id: int, _: dict = Depends(require_role("analyst")),
                           svc: SurveyService = Depends(survey_service)):
    return svc.custom_answers_report(svc.get_period(period_id), include_private=True)


@router.post("/staff/periods")
def create_period_staff(body: PeriodIn, _: dict = Depends(require_role("management", "analyst")),
                        svc: SurveyService = Depends(survey_service)):
    return svc.create_period(body.title, body.question_ids, body.date)


@router.get("/staff/periods")
def periods(_: dict = Depends(require_role("management", "analyst")),
            svc: SurveyService = Depends(survey_service)):
    return [{"id": p["id"], "title": p["title"], "status": p["status"]}
            for p in svc.s.open.read()["periods"]]


@router.get("/analyst/members")
def members(_: dict = Depends(require_role("analyst")), svc: SurveyService = Depends(survey_service)):
    return {m["id"]: m["full_name"] for m in svc.participants()}


@router.get("/management/completion/{period_id}")
def completion(period_id: int, _: dict = Depends(require_role("management", "analyst")),
               svc: SurveyService = Depends(survey_service)):
    """Только кто прошёл, без ответов."""
    return svc.completion(svc.get_period(period_id))


@router.post("/analyst/periods")
def create_period(body: PeriodIn, _: dict = Depends(require_role("analyst")),
                  svc: SurveyService = Depends(survey_service)):
    return svc.create_period(body.title, body.question_ids, body.date)


@router.post("/analyst/periods/{period_id}/close")
def close_period(period_id: int, _: dict = Depends(require_role("analyst")),
                 svc: SurveyService = Depends(survey_service)):
    return svc.close_period(period_id)


@router.post("/analyst/periods/{period_id}/exclude/{member_id}")
def exclude_member(period_id: int, member_id: int, _: dict = Depends(require_role("analyst")),
                   svc: SurveyService = Depends(survey_service)):
    p = svc.set_excluded(period_id, member_id, True)
    return {"excluded": p["excluded"]}


@router.post("/analyst/periods/{period_id}/include/{member_id}")
def include_member(period_id: int, member_id: int, _: dict = Depends(require_role("analyst")),
                   svc: SurveyService = Depends(survey_service)):
    p = svc.set_excluded(period_id, member_id, False)
    return {"excluded": p["excluded"]}


@router.get("/analyst/flags/{period_id}")
def flags(period_id: int, _: dict = Depends(require_role("analyst")),
          svc: SurveyService = Depends(survey_service)):
    return svc.flags(svc.get_period(period_id))


@router.get("/analyst/stats/{period_id}")
def stats(period_id: int, _: dict = Depends(require_role("analyst")),
          svc: SurveyService = Depends(survey_service)):
    return svc.stats(svc.get_period(period_id))
