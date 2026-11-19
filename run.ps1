# Запуск сайта. Впишите свои почты (несколько через запятую) и придумайте пароли.
$env:ANALYST_EMAILS = "analyst@example.com"
$env:MANAGEMENT_EMAILS = "boss@example.com"

# Пароли нужны только аналитику и руководству. Участники входят по почте без пароля.
# Если оставить пустыми, сотрудники тоже войдут без пароля: так можно только при разработке.
$env:ANALYST_PASSWORD = "change-me-analyst"
$env:MANAGEMENT_PASSWORD = "change-me-boss"

.\.venv\Scripts\python -m uvicorn app.main:app --reload
