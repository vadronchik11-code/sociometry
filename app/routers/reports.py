from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.deps import current_member, require_role, survey_service
from app.services import reports, scoring
from app.services.survey import SurveyService

router = APIRouter(tags=["reports"])


class ReportIn(BaseModel):
    text: str | None = None
    published: bool | None = None


# --- публично ----------------------------------------------------------------
@router.get("/public/periods")
def public_periods(svc: SurveyService = Depends(survey_service)):
    out = []
    for p in reversed(reports.published_periods(svc)):
        r = reports.build_group_report(svc, p)
        out.append({"id": p["id"], "title": p["title"], "date": p.get("date"), "n": r["n"],
                    "respondents": r["respondents"],
                    "gg_work": (r["criteria"].get("teamwork") or {}).get("Gg")})
    return out


@router.get("/public/summary")
def public_summary(svc: SurveyService = Depends(survey_service)):
    series = reports.build_series(svc)
    latest = reports.build_group_report(svc, svc.get_period(series[-1]["id"])) if series else None
    survey_open = any(p["status"] == "open" for p in svc.s.open.read()["periods"])
    return {"series": series, "latest": latest, "survey_open": survey_open,
            "labels": reports.CRITERIA, "order": reports.ORDER}


@router.get("/public/report/{period_id}")
def public_report(period_id: int, svc: SurveyService = Depends(survey_service)):
    p = svc.get_period(period_id)
    if not p.get("published"):
        raise HTTPException(404, "Отчёт не опубликован")
    return reports.build_group_report(svc, p) | {"labels": reports.CRITERIA, "order": reports.ORDER,
                                                  "categories": scoring.CATEGORY_TITLES}


# --- аналитик ------------------------------------------------------------------
@router.get("/analyst/report/{period_id}")
def analyst_report(period_id: int, _: dict = Depends(require_role("analyst")),
                   svc: SurveyService = Depends(survey_service)):
    return reports.build_group_report(svc, svc.get_period(period_id)) | {
        "labels": reports.CRITERIA, "order": reports.ORDER, "categories": scoring.CATEGORY_TITLES}


@router.post("/analyst/periods/{period_id}/report/draft")
def report_draft(period_id: int, _: dict = Depends(require_role("analyst")),
                 svc: SurveyService = Depends(survey_service)):
    p = svc.get_period(period_id)
    return {"text": reports.draft_text(svc, p, reports.build_group_report(svc, p),
                                       reports.previous_report(svc, p))}


@router.put("/analyst/periods/{period_id}/report")
def save_report(period_id: int, body: ReportIn, _: dict = Depends(require_role("analyst")),
                svc: SurveyService = Depends(survey_service)):
    p = svc.set_report(period_id, body.text, body.published)
    return {"published": p["published"], "text": p["report_text"]}


@router.get("/analyst/overview/{period_id}")
def overview(period_id: int, _: dict = Depends(require_role("analyst")),
             svc: SurveyService = Depends(survey_service)):
    """Всё для экрана аналитика: кто что выбрал, показатели, флаги с именами."""
    period = svc.get_period(period_id)
    members = svc.participants(period)
    names = {m["id"]: m["full_name"] for m in members}
    answers = svc.submitted_answers(period)
    questions = svc.period_questions(period)
    stats = svc.stats(period)
    flags = []
    for f in svc.flags(period):
        flags.append(f | {"member": names.get(f["member_id"]),
                          "target": names.get(f.get("target_id"))})
    by_q: dict[int, dict[int, list[int]]] = {}
    for q in questions:
        if q["kind"] == "permanent" or q.get("answer_type", "people") == "people":
            by_q[q["id"]] = {m: sorted(a[q["id"]]) for m, a in answers.items() if q["id"] in a}
    history: dict[int, list] = {m["id"]: [] for m in members}
    for p in sorted(svc.s.open.read()["periods"], key=lambda x: (x.get("date") or "", x["id"])):
        # Идущие опросы (кроме выбранного) искажают динамику: в них ещё не все ответили.
        if p["status"] == "open" and p["id"] != period["id"]:
            continue
        subs = svc.submitted_answers(p)
        if not subs:
            continue
        ps = svc.stats(p)
        for mid, v in ps["members"].items():
            if mid in history:
                history[mid].append({"period_id": p["id"], "title": p["title"], "date": p.get("date"),
                                     "S": v["S"], "category": v.get("category"), "participated": mid in subs})
    # Сильный ярлык подтверждён, если в предыдущем закрытом опросе была та же категория.
    confirmed = {}
    for mid, h in history.items():
        before = [x for x in h if x["period_id"] != period["id"]]
        cur = stats["members"].get(mid, {}).get("category")
        prev_cat = before[-1]["category"] if before else None
        confirmed[mid] = {"previous": prev_cat, "confirmed": bool(prev_cat) and prev_cat == cur,
                          "strong": cur in scoring.STRONG_CATEGORIES}
    names = {m["id"]: m["full_name"] for m in members}
    microgroups = {}
    for key in ("teamwork", "organizing", "trust", "leisure"):
        g = stats["group"].get(key, {}).get("groups")
        if g is not None:
            inside = {m for grp in g for m in grp}
            microgroups[key] = {"title": reports.CRITERIA[key], "groups": [[names[m] for m in grp] for grp in g],
                                "outside": sorted(names[m] for m in names if m not in inside)}
    return {
        "categories": scoring.CATEGORY_TITLES,
        "history": history,
        "confirmed": confirmed,
        "microgroups": microgroups,
        "excluded": [{"id": m["id"], "name": m["full_name"]} for m in svc.excluded(period)],
        "period": {k: period.get(k) for k in ("id", "title", "status", "date", "published")},
        "members": [{"id": m["id"], "name": m["full_name"]} for m in members],
        "submitted": sorted(answers),
        "questions": [{k: q.get(k) for k in ("id", "text", "polarity", "criterion", "pair_with", "kind",
                                             "answer_type", "anonymous", "visibility")} for q in questions],
        "answers": by_q,
        "flags": flags,
        "stats": {"n": stats["n"], "members": {
            m: {"S": v["S"], "E": v["E"], "place": v["place"], "received": v["received"],
                "given": v["given"], "mutual": v["mutual"], "category": v.get("category"),
                "categories": v.get("categories", {}), "pos_total": v.get("pos_total", 0),
                "neg_total": v.get("neg_total", 0), "pref_total": v.get("pref_total", 0),
                "impact_total": v.get("impact_total", 0), "S_classic": v.get("S_classic")}
            for m, v in stats["members"].items()}},
    }


@router.get("/analyst/personal/{period_id}/{member_id}")
def analyst_personal(period_id: int, member_id: int, _: dict = Depends(require_role("analyst")),
                     svc: SurveyService = Depends(survey_service)):
    """Личный отчёт любого участника: аналитик скачивает его и отправляет человеку лично."""
    p = svc.get_period(period_id)
    member = next((m for m in svc.participants(p) if m["id"] == member_id), None)
    if not member:
        raise HTTPException(404, "Этого человека не было в группе на момент опроса")
    return reports.personal_report(svc, p, member_id) | {
        "member": {"id": member_id, "name": member["full_name"]},
        "participated": member_id in svc.submitted_answers(p)}


# --- участник ------------------------------------------------------------------
@router.get("/me/reports")
def my_reports(member: dict = Depends(current_member), svc: SurveyService = Depends(survey_service)):
    out = []
    for p in reversed(reports.published_periods(svc)):
        if member["id"] in svc.submitted_answers(p):
            out.append({"id": p["id"], "title": p["title"], "date": p.get("date")})
    return out


@router.get("/me/report/{period_id}")
def my_report(period_id: int, member: dict = Depends(current_member),
              svc: SurveyService = Depends(survey_service)):
    p = svc.get_period(period_id)
    if not p.get("published"):
        raise HTTPException(404, "Отчёт не опубликован")
    if member["id"] not in svc.submitted_answers(p):
        raise HTTPException(404, "Вы не участвовали в этом исследовании")
    return reports.personal_report(svc, p, member["id"])
