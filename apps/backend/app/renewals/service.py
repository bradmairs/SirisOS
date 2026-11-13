"""Documents and renewals (9.3): what expires that never arrives by email (a
passport, a driver's licence, car rego, an insurance policy, a Medicare card,
a warranty), each with its expiry date. Reminders go 60, 30 and 7 days before
and on the day; Life lists them soonest first and the Today timeline shows any
within a week. Kept in renewals.json (SIRISOS_RENEWALS_PATH).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from app.services import json_store
from app.tasks.service import today

KINDS = ["passport", "licence", "rego", "insurance", "medicare", "warranty", "membership", "other"]
REMIND_DAYS = (60, 30, 7, 0)


def _path():
    return json_store.data_path("SIRISOS_RENEWALS_PATH", "renewals.json")


def _load() -> list[dict[str, Any]]:
    return list(json_store.read(_path(), {"items": []}).get("items") or [])


def _save(items: list[dict[str, Any]]) -> None:
    json_store.write(_path(), {"items": items})


def _left(item: dict[str, Any], on: date) -> int:
    return (date.fromisoformat(item["expires"]) - on).days


def _view(item: dict[str, Any], on: date) -> dict[str, Any]:
    left = _left(item, on)
    state = "expired" if left < 0 else "soon" if left <= 30 else "later" if left <= 90 else "fine"
    return {**item, "days_left": left, "state": state}


def listing(on: date | None = None) -> list[dict[str, Any]]:
    """Soonest first."""
    on = on or today()
    return sorted((_view(i, on) for i in _load()), key=lambda i: i["expires"])


def add(name: str, kind: str, expires: str, note: str = "") -> list[dict[str, Any]]:
    items = _load()
    items.append({"id": uuid.uuid4().hex[:12], "name": name.strip(), "kind": kind, "expires": expires, "note": note.strip()})
    _save(items[-200:])
    return listing()


def change(item_id: str, **fields: Any) -> list[dict[str, Any]] | None:
    items = _load()
    found = next((i for i in items if i["id"] == item_id), None)
    if found is None:
        return None
    for k, v in fields.items():
        if v is not None:
            found[k] = v.strip() if isinstance(v, str) else v
    _save(items)
    return listing()


def remove(item_id: str) -> bool:
    items = _load()
    kept = [i for i in items if i["id"] != item_id]
    if len(kept) == len(items):
        return False
    _save(kept)
    return True


def push_messages(now: datetime) -> list[dict[str, Any]]:
    """A reminder 60, 30 and 7 days before, and on the day, from 9am. Each goes once (its key holds the date)."""
    from app.push.notifier import message

    if now.hour < 9:
        return []
    out = []
    for i in listing(now.date()):
        left = i["days_left"]
        if left not in REMIND_DAYS:
            continue
        when = "today" if left == 0 else f"in {left} days ({date.fromisoformat(i['expires']).strftime('%-d %b')})"
        out.append(message(f"renewal:{i['id']}:{i['expires']}:{left}", "brief", f"{i['name']} expires {when}",
                           "Renew it, then update the date in Life." if left else "Renewed? Update the date in Life.", url="/life"))
    return out
