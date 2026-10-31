"""Proactive nudges (6.3): one or two well-timed prompts a day, sent as
notifications on their own topic ("nudges", which you can turn off).

- **A free stretch and something due**: when the calendar has 40 minutes or
  more free starting within the hour (8am to 7pm), and a home job or a task
  is due, "You've got 55 free minutes, and Clean the dryer filter is due".
- **Wind down**: half an hour before tonight's suggested bedtime (SirisAI's,
  from tomorrow's first event and your sleep), once a night.

Never more than SIRISOS_NUDGES_PER_DAY (2), never in quiet hours
(SIRISOS_QUIET_HOURS, "22-7": 10pm to 7am; the wind-down one may come in
the half hour before them), and SIRISOS_NUDGES=0 turns them off.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any

FREE_MINUTES = 40
DAY_HOURS = range(8, 19)


def enabled() -> bool:
    return os.getenv("SIRISOS_NUDGES", "1") not in ("0", "false", "no")


def per_day() -> int:
    try:
        return max(0, int(os.getenv("SIRISOS_NUDGES_PER_DAY", "2")))
    except ValueError:
        return 2


def quiet_hours() -> tuple[int, int]:
    try:
        a, b = (int(x) for x in os.getenv("SIRISOS_QUIET_HOURS", "22-7").split("-", 1))
        return a % 24, b % 24
    except ValueError:
        return 22, 7


def is_quiet(hour: int, quiet: tuple[int, int]) -> bool:
    start, end = quiet
    return start <= hour or hour < end if start > end else start <= hour < end


def _when(value: Any, tz) -> datetime | None:
    text = str(value or "")
    if len(text) <= 10:
        return None  # all-day
    try:
        t = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (t if t.tzinfo else t.replace(tzinfo=tz)).astimezone(tz)


def free_stretch(now: datetime, events: list[dict[str, Any]]) -> int | None:
    """Minutes free from now (or from the end of what's on now) when that starts within the hour."""
    busy = sorted((s, e) for ev in events if (s := _when(ev.get("start"), now.tzinfo)) and (e := _when(ev.get("end"), now.tzinfo)) and e > now)
    start = now
    for s, e in busy:
        if s <= start < e:
            start = e
    if start - now > timedelta(hours=1) or start.hour not in DAY_HOURS:
        return None
    nxt = next((s for s, _ in busy if s >= start), None)
    until = min(nxt or start.replace(hour=19, minute=0), start.replace(hour=19, minute=0))
    minutes = int((until - start).total_seconds() // 60)
    return minutes if minutes >= FREE_MINUTES else None


def pick(now: datetime, *, events: list[dict[str, Any]] | None, due: list[str], bedtime: str | None, bedtime_text: str | None,
         sent_today: int, quiet: tuple[int, int] | None = None) -> list[dict[str, Any]]:
    """The nudges that fit right now (pure, for testing). `due` is what's due
    (home jobs first, then tasks); `bedtime` is "HH:MM"."""
    from app.push.notifier import message

    if sent_today >= per_day():
        return []
    quiet = quiet or quiet_hours()
    day = now.date().isoformat()
    out = []
    if bedtime:
        try:
            h, m = (int(x) for x in bedtime.split(":"))
            bed = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if bed < now - timedelta(hours=6):
                bed += timedelta(days=1)
            if timedelta(0) <= bed - now <= timedelta(minutes=30):
                out.append(message(f"nudge:{day}:wind-down", "nudges", "Time to start winding down",
                                   bedtime_text or f"Bed by {bedtime} keeps you on track for tomorrow.", "/health?view=sleep", "normal"))
        except ValueError:
            pass
    if not out and not is_quiet(now.hour, quiet) and events is not None and due:
        free = free_stretch(now, events)
        if free:
            more = f" (and {len(due) - 1} more)" if len(due) > 1 else ""
            out.append(message(f"nudge:{day}:free:{now.hour}", "nudges", f"You've got {free} free minutes",
                               f"{due[0]} is due{more}. A good time for it?", "/tasks", "normal"))
    return out[:1]


async def messages(hub: Any, now: datetime) -> list[dict[str, Any]]:
    if not enabled():
        return []
    from app.calendar import service as calendar
    from app.health import service as health
    from app.maintenance import service as maintenance
    from app.push import store
    from app.tasks import service as tasks

    today: date = now.date()
    sent_today = sum(1 for k in store.sent() if k.startswith(f"nudge:{today.isoformat()}:"))
    if sent_today >= per_day():
        return []
    jobs = [j["title"] for j in maintenance.overview(today)["jobs"] if j["state"] in ("due", "overdue")]
    try:
        listing = await tasks.collect(hub, today)
        due_tasks = [t["title"] for t in listing["groups"]["overdue"] + listing["groups"]["today"]]
    except Exception:  # noqa: BLE001
        due_tasks = []
    cal = await calendar.events(hub, today, today + timedelta(days=1))
    bed, bed_text = None, None
    if now.hour >= 18:
        try:
            b = (await health.overview(hub)).get("bedtime") or {}
            bed, bed_text = b.get("bedtime"), b.get("text")
        except Exception:  # noqa: BLE001
            pass
    return pick(now, events=cal["events"], due=jobs + due_tasks, bedtime=bed, bedtime_text=bed_text, sent_today=sent_today)
