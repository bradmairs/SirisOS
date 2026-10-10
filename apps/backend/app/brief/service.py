"""The daily brief: one call that gathers the start of Brad's day from every
app SirisOS knows about, and decides whether it should open by itself.

Sources (each best-effort, with its own timeout; a dead one blanks only its
own section, and is listed in `unavailable`):

- SirisAI: HUD (weather now, parcels, car), and its read-only tools run
  directly (no LLM, nothing added to a conversation): today's forecast, the
  calendar, Home Assistant to-dos, unread email, health. The `daily_briefing`
  skill is deliberately not used: it clears SirisAI's queued notifications.
- Second Brain (via SirisAI): insights (overdue tasks, deadlines, inbox,
  auto-links) and the notes that shape the news (see news.py).
- Hub: APD PM's due tasks, and any app that's down or needs attention.
- News: see news.py.

Shown automatically from SIRISOS_BRIEF_FROM_HOUR (4) until
SIRISOS_BRIEF_UNTIL_HOUR (9) local time, until dismissed for the day; the
dismissal is stored server-side so dismissing on the phone also clears the
desktop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable
from zoneinfo import ZoneInfo

import httpx

from app.brief.news import news_service
from app.hub.connectors.sirisai import SirisAIConnector
from app.hub.service import Hub, shared_client

logger = logging.getLogger(__name__)

CACHE_SECONDS = 10 * 60
SOURCE_TIMEOUT = 12.0


def zone() -> ZoneInfo:
    try:
        return ZoneInfo(os.getenv("SIRISOS_TIMEZONE", "Australia/Melbourne"))
    except Exception:  # noqa: BLE001 - an unknown zone name falls back rather than breaking the brief
        return ZoneInfo("Australia/Melbourne")


def now_local() -> datetime:
    return datetime.now(zone())


def window() -> tuple[int, int]:
    def hour(key: str, default: int) -> int:
        try:
            return max(0, min(23, int(os.getenv(key, str(default)))))
        except ValueError:
            return default
    return hour("SIRISOS_BRIEF_FROM_HOUR", 4), hour("SIRISOS_BRIEF_UNTIL_HOUR", 9)


def _state_path() -> Path:
    return Path(os.getenv("SIRISOS_BRIEF_STATE_PATH", "/app/data/brief-state.json"))


def _read_state() -> dict[str, Any]:
    try:
        value = json.loads(_state_path().read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def dismiss(day: str | None = None) -> dict[str, Any]:
    day = day or now_local().date().isoformat()
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {**_read_state(), "dismissed": day}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    tmp.replace(path)
    return status()


def status(at: datetime | None = None) -> dict[str, Any]:
    at = at or now_local()
    start, until = window()
    today = at.date().isoformat()
    dismissed = _read_state().get("dismissed") == today
    in_window = start <= at.hour < until
    return {"date": today, "show": in_window and not dismissed, "dismissed_today": dismissed,
            "from": f"{start:02d}:00", "until": f"{until:02d}:00"}


def greeting(at: datetime) -> str:
    h = at.hour
    return "Good night" if h < 5 else "Good morning" if h < 12 else "Good afternoon" if h < 18 else "Good evening"


def _time(value: Any) -> str:
    if not isinstance(value, str) or len(value) <= 10:
        return "All day"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(zone()).strftime("%-I:%M %p").lower()
    except ValueError:
        return value[11:16]


class SirisAISource:
    def __init__(self, connector: SirisAIConnector) -> None:
        self.c = connector

    async def get(self, path: str, **params: Any) -> Any:
        r = await shared_client().get(f"{self.c.base_url}{path}", headers=self.c.headers(), params=params or None,
                                      timeout=SOURCE_TIMEOUT)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    async def tool(self, name: str, **arguments: Any) -> Any:
        """A read-only SirisAI tool, run directly. None when that tool isn't configured."""
        r = await shared_client().post(f"{self.c.base_url}/siris/tools/{name}/run", headers=self.c.headers(),
                                       json={"arguments": arguments}, timeout=SOURCE_TIMEOUT)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        body = r.json()
        if body.get("confirmation_required"):
            return None
        return (body.get("tool_call") or {}).get("result")

    async def note_body(self, title: str) -> str | None:
        try:
            note = await self.get("/siris/brain/note", title=title)
        except httpx.HTTPError:
            return None
        return note.get("body") if isinstance(note, dict) else None


async def _safe(name: str, work: Awaitable[Any], failed: list[str]) -> Any:
    try:
        return await asyncio.wait_for(work, SOURCE_TIMEOUT + 2)
    except Exception as exc:  # noqa: BLE001 - one source never breaks the brief
        logger.info("Brief source %s unavailable: %s", name, exc)
        failed.append(name)
        return None


# Media schedules from Home Assistant aren't Brad's day (SirisAI filters
# them too; this covers an older SirisAI).
MEDIA_CALENDARS = ("sonarr", "radarr", "lidarr", "readarr")


def _calendar(events: Any) -> list[dict[str, Any]]:
    out = []
    for e in events if isinstance(events, list) else []:
        if not isinstance(e, dict):
            continue
        calendar = str(e.get("calendar") or "")
        if any(m in calendar.lower() for m in MEDIA_CALENDARS):
            continue
        title = e.get("summary") or e.get("title") or e.get("message") or "Event"
        start = e.get("start")
        if isinstance(start, dict):  # Home Assistant shape: {"dateTime"} or {"date"}
            start = start.get("dateTime") or start.get("date")
        out.append({"title": str(title), "time": _time(start), "start": start, "location": e.get("location"),
                    "calendar": calendar or None})
    return sorted(out, key=lambda e: (e["time"] != "All day", str(e.get("start") or "")))


def _career() -> dict[str, Any] | None:
    """CPD and the next career step (ADR 110), from SirisOS's own career file."""
    from app.career import api as career_api, store as career_store

    try:
        ov = career_api.overview(career_store.load())
    except Exception as exc:  # noqa: BLE001 - an unreadable file never breaks the brief
        logger.info("Brief career section unavailable: %s", exc)
        return None
    cpd = ov["cpd"]
    return {
        "cpd": {"total": cpd["total"], "required": cpd["required"], "records": cpd["records"], "expiring_90_days": cpd["expiring_90_days"]},
        "next_steps": ov["next_steps"][:3],
        "goals": [{"title": g["title"], "target_date": g["target_date"]} for g in ov["goals"][:3]],
    }


def compose(at: datetime, user: str, parts: dict[str, Any], failed: list[str]) -> dict[str, Any]:
    hud = parts.get("hud") or {}
    forecast = parts.get("forecast")
    today_fc = forecast[0] if isinstance(forecast, list) and forecast else None
    now_wx = hud.get("weather") if isinstance(hud.get("weather"), dict) else None
    events = _calendar(parts.get("calendar"))
    insights = parts.get("insights") or {}
    apps = parts.get("apps") or []
    email = parts.get("email")
    health = parts.get("health") or {}

    tasks: list[dict[str, Any]] = []
    for t in insights.get("overdue_tasks") or []:
        tasks.append({"title": t.get("task"), "detail": f"{t.get('note')} · {t.get('days_late')} days late", "tone": "critical", "source": "Second Brain"})
    for d in insights.get("deadlines") or []:
        left = d.get("days_left", 0)
        if left <= 7:
            when = "due today" if left == 0 else "due tomorrow" if left == 1 else f"overdue by {-left} days" if left < 0 else f"due in {left} days"
            tasks.append({"title": d.get("title"), "detail": f"Project {when}", "tone": "critical" if left <= 0 else "warning", "source": "Second Brain"})
    for app in apps:
        if app.get("id") == "apd-pm" and isinstance(app.get("widget"), dict):
            for item in (app["widget"].get("items") or [])[:4]:
                if item.get("tone") in ("critical", "warning"):
                    tasks.append({"title": item.get("title"), "detail": item.get("subtitle"), "tone": item.get("tone"), "source": "Project Management"})
    todo = []
    for lst in parts.get("todo") or []:
        for item in (lst.get("items") or []) if isinstance(lst, dict) else []:
            if item.get("summary"):
                todo.append(item["summary"])

    important = []
    unread = 0
    if isinstance(email, list):
        unread = len(email)
        important = [{"from": (m.get("from") or "").split("<")[0].strip() or m.get("from"), "subject": m.get("subject")}
                     for m in email if m.get("important")][:5]

    attention = [{"name": a["name"], "state": a["status"]["state"], "detail": a["status"].get("detail", "")}
                 for a in apps if a.get("status", {}).get("state") in ("down", "degraded")]

    home = []
    for p in hud.get("parcels") or []:
        if isinstance(p, dict):
            home.append(f"Parcel: {p.get('label', 'parcel')} {p.get('status_text', '')}".strip())
    car = hud.get("car")
    if isinstance(car, dict) and car.get("summary"):
        home.append(car["summary"] + (" Low and not plugged in." if car.get("low_battery") else ""))

    health_lines = []
    metrics = health.get("metrics") or {}
    if "sleep_hours" in metrics:
        health_lines.append(f"Slept {metrics['sleep_hours']['latest']:.1f} h")
    health_lines += [str(n) for n in (health.get("notes") or [])][:2]

    summary = insights.get("summary") or {}
    brain = {
        "inbox": summary.get("inbox", 0),
        "auto_linked": len(insights.get("auto_linked") or []),
        "pending_links": insights.get("pending_auto_links", 0),
        "unsure_links": len(insights.get("suggested_links") or []),
        "highlights": (insights.get("highlights") or [])[:3],
    }

    # The headline: what Brad would want to know if he read nothing else.
    lines = []
    if today_fc:
        line = f"{round(today_fc['high_c'])}° today, {str(today_fc.get('conditions', '')).lower()}" if today_fc.get("high_c") is not None else str(today_fc.get("conditions", ""))
        if (today_fc.get("rain_chance_percent") or 0) >= 40:
            line += f", {today_fc['rain_chance_percent']}% chance of rain: take a jacket"
        lines.append(line + ".")
    elif now_wx and now_wx.get("temperature_c") is not None:
        lines.append(f"{round(now_wx['temperature_c'])}° and {str(now_wx.get('conditions', '')).lower()} right now.")
    timed = [e for e in events if e["time"] != "All day"]
    if events:
        first = timed[0] if timed else events[0]
        lines.append(f"{len(events)} thing{'s' if len(events) != 1 else ''} on today, starting with {first['title']}"
                     + (f" at {first['time']}." if first["time"] != "All day" else "."))
    else:
        lines.append("Nothing on the calendar today.")
    urgent = [t for t in tasks if t["tone"] == "critical"]
    if urgent:
        lines.append(f"{len(urgent)} task{'s' if len(urgent) != 1 else ''} overdue or due today, starting with {urgent[0]['title']}.")
    if important:
        lines.append(f"{len(important)} important email{'s' if len(important) != 1 else ''}, from {important[0]['from']}.")
    if attention:
        lines.append(f"{attention[0]['name']} needs a look ({attention[0]['state']}).")
    if brain["inbox"]:
        lines.append(f"{brain['inbox']} thing{'s' if brain['inbox'] != 1 else ''} waiting in the Second Brain inbox.")

    return {
        "date": at.date().isoformat(),
        "weekday": at.strftime("%A"),
        "generated_at": at.isoformat(),
        "greeting": f"{greeting(at)}, {user.capitalize()}",
        "headline": lines,
        "weather": {"now": now_wx, "today": today_fc},
        "schedule": events,
        "tasks": tasks[:10],
        "todo": todo[:8],
        "email": {"unread": unread, "important": important} if isinstance(email, list) else None,
        "health": health_lines,
        "home": home,
        "apps_attention": attention,
        "brain": brain,
        "career": parts.get("career"),
        "news": parts.get("news") or {"topics": []},
        "unavailable": sorted(set(failed)),
        "status": status(at),
    }


class BriefService:
    def __init__(self) -> None:
        self._cache: tuple[float, str, dict[str, Any]] | None = None
        self._lock = asyncio.Lock()

    async def build(self, hub: Hub, user: str, fresh: bool = False) -> dict[str, Any]:
        at = now_local()
        async with self._lock:
            if not fresh and self._cache and self._cache[1] == at.date().isoformat() \
                    and time.monotonic() - self._cache[0] < CACHE_SECONDS:
                return {**self._cache[2], "status": status(at)}
            failed: list[str] = []
            connector = hub.get("sirisai")
            ai = SirisAISource(connector) if isinstance(connector, SirisAIConnector) and connector.configured else None
            if ai is None:
                failed.append("SirisAI")

            async def calendar() -> Any:
                found = await ai.tool("calendar_upcoming_events", days_ahead=1)
                return found if found is not None else await ai.tool("home_assistant_get_calendar_events", days=1)

            async def insights() -> Any:
                return await ai.get("/siris/brain/insights", days=7)

            jobs: dict[str, Awaitable[Any]] = {"apps": hub.apps(with_widgets=True)}
            if ai:
                jobs.update({
                    "hud": ai.get("/siris/hud/summary"),
                    "forecast": ai.tool("weather_forecast", days=1),
                    "calendar": calendar(),
                    "todo": ai.tool("home_assistant_get_todo_items"),
                    "email": ai.tool("email_list_unread", since_days=1),
                    "health": ai.tool("health_summary"),
                    "insights": insights(),
                })
            names = list(jobs)
            values = await asyncio.gather(*(_safe(n, jobs[n], failed) for n in names))
            parts = dict(zip(names, values))

            hot = [t["tag"] for t in ((parts.get("insights") or {}).get("topics") or []) if isinstance(t, dict)]

            async def no_note(_: str) -> str | None:
                return None

            parts["career"] = _career()
            parts["news"] = await _safe(
                "news",
                news_service.stories(shared_client(), ai.note_body if ai else no_note, hot, fresh=fresh),
                failed,
            )
            if parts["news"] and parts["news"].get("feeds_failed") == parts["news"].get("feeds_total"):
                failed.append("news")

            brief = compose(at, user, parts, failed)
            self._cache = (time.monotonic(), at.date().isoformat(), brief)
            return brief


brief_service = BriefService()
