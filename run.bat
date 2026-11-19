@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Социометрия

rem === Настройки: почты и пароли сотрудников (несколько почт через запятую) ===
set ANALYST_EMAILS=analyst@example.com
set MANAGEMENT_EMAILS=boss@example.com
set ANALYST_PASSWORD=change-me-analyst
set MANAGEMENT_PASSWORD=change-me-boss

rem === Три профиля сразу: аналитик, руководство, обычный участник ===
rem Быстрый вход работает только с этого компьютера. Когда сайт открывают люди, поставьте 0.
set DEV_AUTOLOGIN=1
set DEV_PARTICIPANT_EMAIL=demo1@example.com

rem === Первый запуск: создать окружение и поставить зависимости ===
if not exist ".venv\Scripts\python.exe" (
    echo Первый запуск: устанавливаю зависимости, это займёт минуту...
    python -m venv .venv || (echo Не найден Python. Установите Python 3.11+ с python.org и запустите снова. & pause & exit /b 1)
    ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || (echo Не удалось установить зависимости. & pause & exit /b 1)
)

echo.
echo Сайт запускается: http://127.0.0.1:8000
if "%DEV_AUTOLOGIN%"=="1" (
    echo Откроются три вкладки, у каждой свой вход:
    echo   аналитик     http://analyst.localhost:8000
    echo   руководство  http://boss.localhost:8000
    echo   участник     http://user.localhost:8000
)
echo Чтобы остановить, закройте это окно или нажмите Ctrl+C.
echo.

rem Разные адреса *.localhost — это разные «сайты» для браузера, поэтому входы не мешают друг другу.
if not defined NO_BROWSER (
    if "%DEV_AUTOLOGIN%"=="1" (
        start "" cmd /c "timeout /t 3 >nul & start http://analyst.localhost:8000/dev/as/analyst & start http://boss.localhost:8000/dev/as/management & start http://user.localhost:8000/dev/as/participant"
    ) else (
        start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8000"
    )
)

".venv\Scripts\python.exe" -m uvicorn app.main:app
pause
