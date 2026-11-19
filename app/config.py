import os
from dataclasses import dataclass, field
from pathlib import Path


def _emails(name: str) -> set[str]:
    raw = os.environ.get(name, "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


@dataclass
class Config:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("DATA_DIR", "data")))
    analyst_emails: set[str] = field(default_factory=lambda: _emails("ANALYST_EMAILS"))
    management_emails: set[str] = field(default_factory=lambda: _emails("MANAGEMENT_EMAILS"))
    # Пароли для входа сотрудников. Если не заданы, вход по одной почте (только для разработки).
    analyst_password: str | None = field(default_factory=lambda: os.environ.get("ANALYST_PASSWORD") or None)
    management_password: str | None = field(default_factory=lambda: os.environ.get("MANAGEMENT_PASSWORD") or None)
    # Быстрый вход под ролью (/dev/as/...) для проверки на своём компьютере. Не включать на сервере для людей.
    dev_autologin: bool = field(default_factory=lambda: os.environ.get("DEV_AUTOLOGIN") == "1")
    dev_participant_email: str = field(default_factory=lambda: os.environ.get("DEV_PARTICIPANT_EMAIL", "demo1@example.com"))
    # Ответ считается подозрительным, если в вопросе выбрано больше этой доли участников.
    suspicious_share: float = 0.8
