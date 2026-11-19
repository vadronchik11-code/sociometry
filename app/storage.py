import copy
import json
import os
import threading
from pathlib import Path
from typing import Callable


class JsonStore:
    """Один JSON-файл с атомарной записью и блокировкой.

    Позже заменяется на SQL-реализацию с тем же интерфейсом (read / update).
    """

    def __init__(self, path: Path, default: dict):
        self.path = Path(path)
        self.default = default
        self._lock = threading.RLock()
        self._cache: tuple[tuple[int, int], dict] | None = None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(copy.deepcopy(default))

    def _read(self) -> dict:
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def _stamp(self) -> tuple[int, int]:
        st = os.stat(self.path)
        return st.st_mtime_ns, st.st_size

    def _write(self, data: dict) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, self.path)
        self._cache = (self._stamp(), data)

    def read(self) -> dict:
        """Данные только для чтения: результат кешируется, изменять его нельзя (для записи есть update)."""
        with self._lock:
            stamp = self._stamp()
            if self._cache is None or self._cache[0] != stamp:
                self._cache = (stamp, self._read())
            return self._cache[1]

    def update(self, fn: Callable[[dict], object]):
        with self._lock:
            data = self._read()  # свежая копия с диска, кеш не трогаем до успешной записи
            result = fn(data)
            self._write(data)
            return result


OPEN_DEFAULT = {
    "members": [],
    "periods": [],
    "questions": [],
    "completions": {},      # period_id -> [member_id]
    "custom_answers": {},   # period_id -> member_id -> question_id -> {targets, none, text}
}

CLOSED_DEFAULT = {
    "submissions": {},      # period_id -> member_id -> {status, submitted_at}
    "answers": {},          # period_id -> member_id -> question_id -> {targets, none}
}


class Storage:
    def __init__(self, data_dir: Path):
        self.open = JsonStore(Path(data_dir) / "open_db.json", OPEN_DEFAULT)
        self.closed = JsonStore(Path(data_dir) / "closed_db.json", CLOSED_DEFAULT)
