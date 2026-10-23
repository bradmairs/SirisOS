"""This week, in one place: every day's events and forecast, plus what's
due (Siris project deadlines and overdue tasks, career goals) and the
week's CPD (hours already in the Engineers Australia import, and calendar
events that look like CPD). Every source fails alone."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

import httpx

from app.calendar import service as calendar
from app.career import suggest
from app.career import store as career_store
from app.hub.connectors.sirisai import SirisAIConnector
from app.hub.service import Hub, shared_client

logger = logging.getLogger(__name__)


def monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


async def _sirisai_get(hub: Hub, path: str, **params: Any) -> Any:
    connector = hub.get("sirisai")
    if not isinstance(connector, SirisAIConnector) or not connector.configured:
        return None
    try:
        response = await shared_client().get(f"{connector.base_url}{path}", headers=connector.headers(), params=params, timeout=20.0)
        return response.json() if response.status_code < 400 else None
    except (httpx.HTTPError, ValueError):
        return None


def _day_of(value: str | None) -> str | None:
    return value[:10] if isinstance(value, str) and len(value) >= 10 else None


async def week(hub: Hub, start: date, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    start = monday(start)
    end = start + timedelta(days=7)
    cal, forecast, insights = await asyncio.gather(
        calendar.events(hub, start, end),
        _sirisai_get(hub, "/siris/hub/v1/forecast", days=7),
        _sirisai_get(hub, "/siris/brain/insights", days=30),
    )
    unavailable: list[str] = []
    if cal["events"] is None and not cal["guest_mode"]:
        unavailable.append("calendar")

    days = [{"date": (start + timedelta(days=i)).isoformat(), "events": [], "forecast": None, "due": [], "cpd_hours": 0.0} for i in range(7)]
    by_date = {d["date"]: d for d in days}

    for event in cal["events"] or []:
        first = _day_of(event.get("start"))
        if not first:
            continue
        # All-day events spanning several days show on each of them.
        last = _day_of(event.get("end")) if event.get("all_day") else first
        d = date.fromisoformat(first)
        stop = date.fromisoformat(last) if last and last > first and event.get("all_day") else d + timedelta(days=1)
        while d < stop:
            if d.isoformat() in by_date:
                by_date[d.isoformat()]["events"].append(event)
            d += timedelta(days=1)

    for f in (forecast or {}).get("days") or []:
        if isinstance(f, dict) and f.get("date") in by_date:
            by_date[f["date"]]["forecast"] = f

    overdue: list[dict[str, Any]] = []
    if isinstance(insights, dict):
        for d in insights.get("deadlines") or []:
            left = d.get("days_left")
            if isinstance(left, int):
                due = (today + timedelta(days=left)).isoformat()
                if due in by_date:
                    by_date[due]["due"].append({"title": d.get("title"), "kind": "project", "source": "Siris"})
        for t in insights.get("overdue_tasks") or []:
            overdue.append({"title": t.get("task"), "detail": f"{t.get('note')} · {t.get('days_late')} days late", "source": "Siris"})
    elif insights is None and hub.get("sirisai") and hub.get("sirisai").configured:
        unavailable.append("brain")

    from app.tasks import store as task_store

    for t in task_store.load().tasks:
        if t.done_at or not t.due:
            continue
        if t.due in by_date:
            by_date[t.due]["due"].append({"title": t.title, "kind": "task", "source": "Tasks"})
        elif t.due < today.isoformat():
            overdue.append({"title": t.title, "detail": f"Was due {t.due}", "source": "Tasks"})

    doc = career_store.load()
    for goal in doc.goals:
        if goal.status == "active" and goal.target_date in by_date:
            by_date[goal.target_date]["due"].append({"title": goal.title, "kind": "goal", "source": "Career"})
    for r in doc.cpd.records:
        if r.date in by_date:
            by_date[r.date]["cpd_hours"] += r.hours
    planned = suggest.suggestions(doc, [e for d in days for e in d["events"]], today) if cal["events"] else []
    planned_keys = {p["key"]: p for p in planned}
    for d in days:
        d["cpd_hours"] = round(d["cpd_hours"], 2)
        for e in d["events"]:
            hit = planned_keys.get(suggest.key(e))
            if hit:
                e["cpd"] = {"hours": hit["hours"], "category": hit["category"]}

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "today": today.isoformat(),
        "days": days,
        "overdue": overdue,
        "focus": _focus(today),
        "cpd": {
            "logged": round(sum(d["cpd_hours"] for d in days), 2),
            "planned": round(sum(p["hours"] for p in planned_keys.values()), 2),
        },
        "guest_mode": cal["guest_mode"],
        "unavailable": unavailable,
    }


def _focus(today: date) -> dict[str, Any] | None:
    """What matters this week, from last Sunday's review (app/review)."""
    from app.review import service as review

    try:
        return review.latest_focus(today)
    except Exception:  # noqa: BLE001 - the week view never fails on it
        return None
