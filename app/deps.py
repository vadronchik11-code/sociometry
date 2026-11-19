from fastapi import Header, HTTPException, Request

from app.services.survey import ServiceError, SurveyService


def survey_service(request: Request) -> SurveyService:
    return request.app.state.survey


def current_member(request: Request, x_token: str = Header(...)) -> dict:
    member = request.app.state.survey.member_by_token(x_token)
    if not member:
        raise HTTPException(401, "Неизвестный токен")
    return member


def require_role(*roles: str):
    def dep(request: Request, x_token: str = Header(...)) -> dict:
        member = current_member(request, x_token)
        if member["role"] not in roles:
            raise HTTPException(403, "Недостаточно прав")
        return member
    return dep


def service_error_handler(_: Request, exc: ServiceError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=exc.status, content={"detail": exc.message})
