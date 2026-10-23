"""A small daily log for the year view (4.1): what has no history anywhere
else. Per day: the most items the Inbox held, tasks ticked off (from any
source, wherever they were ticked), and whether there was a wrap-up, a
journal line or a weekly review. 400 days are kept."""

from __future__ import annotations

import threading
from datetime import date, timedelta
from typing import Any

from app.services import json_store

KEEP_DAYS = 400
_lock = threading.Lock()


def _path():
    return json_store.data_path("SIRISOS_TRENDS_PATH", "trends.json")


def days() -> dict[str, dict[str, Any]]:
    value = json_store.read(_path(), {})
    return value if isinstance(value, dict) else {}


def _today() -> date:
    from app.tasks import service as tasks

    return tasks.today()


def _update(day: date | None, change) -> None:
    day = day or _today()
    with _lock:
        log = days()
        entry = dict(log.get(day.isoformat()) or {})
        if not change(entry):
            return
        log[day.isoformat()] = entry
        cutoff = (day - timedelta(days=KEEP_DAYS)).isoformat()
        try:
            json_store.write(_path(), {k: v for k, v in sorted(log.items()) if k >= cutoff})
        except OSError:
            pass  # the year view never breaks what's logging to it


def inbox(count: int, day: date | None = None) -> None:
    """The Inbox held `count` items just now; keep the day's most."""
    def change(e: dict[str, Any]) -> bool:
        if count <= e.get("inbox", -1):
            return False
        e["inbox"] = count
        return True

    _update(day, change)


def task_done(day: date | None = None) -> None:
    def change(e: dict[str, Any]) -> bool:
        e["tasks_done"] = e.get("tasks_done", 0) + 1
        return True

    _update(day, change)


def mark(what: str, day: date | None = None) -> None:
    """`wrapup`, `journal` or `review` happened on `day`."""
    def change(e: dict[str, Any]) -> bool:
        if e.get(what):
            return False
        e[what] = True
        return True

    _update(day, change)
