import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import Config
from app.deps import service_error_handler
from app.routers import participant, reports, staff
from app.services.survey import ServiceError, SurveyService
from app.storage import Storage


STATIC = Path(__file__).resolve().parent / "static"


def create_app(config: Config | None = None) -> FastAPI:
    config = config or Config()
    app = FastAPI(title="Социометрия")
    app.state.config = config
    app.state.survey = SurveyService(Storage(config.data_dir), config)
    app.add_exception_handler(ServiceError, service_error_handler)
    app.include_router(participant.router)
    app.include_router(staff.router)
    app.include_router(reports.router)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        # Версия по времени изменения файлов: после обновления браузер не держит старые скрипты.
        version = int(max(f.stat().st_mtime for f in STATIC.iterdir()))
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        html = html.replace('.js"', f'.js?v={version}"').replace('.css"', f'.css?v={version}"')
        return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

    @app.get("/dev/as/{who}", include_in_schema=False)
    def dev_login(who: str, request: Request):
        """Быстрый вход под ролью для локальной проверки (run.bat открывает три профиля).

        Работает, только если включён DEV_AUTOLOGIN=1 и запрос пришёл с этого же компьютера.
        """
        client = request.client.host if request.client else ""
        if not config.dev_autologin or client not in ("127.0.0.1", "::1"):
            raise HTTPException(404)
        svc: SurveyService = app.state.survey
        first = lambda emails: sorted(emails)[0] if emails else None
        if who == "analyst":
            email, name, pwd, page = first(config.analyst_emails), "Аналитик", config.analyst_password, "analyst"
        elif who == "management":
            email, name, pwd, page = first(config.management_emails), "Руководство", config.management_password, "manage"
        elif who == "participant":
            email, name, pwd, page = config.dev_participant_email, "Участник", None, "personal"
        else:
            raise HTTPException(404)
        if not email:
            raise HTTPException(404, "Почта для этой роли не задана")
        m = svc.register(name, email, pwd)
        me = {"member_id": m["id"], "token": m["token"], "role": m["role"], "full_name": m["full_name"]}
        html = (f"<!doctype html><meta charset='utf-8'><script>localStorage.setItem('sm', {json.dumps(json.dumps(me))});"
                f"location.replace('/#/{page}');</script>")
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    return app


app = create_app()
