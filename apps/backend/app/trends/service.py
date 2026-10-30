"""The year at a glance (4.1): the last 12 months, month by month.

- **CPD hours** logged (career records) and the three-year window's total
  against Engineers Australia's 150
- **Running, exercise and steps** from SirisAI's health by day (2.26 gives a
  year; older versions give the last 35 days)
- **Tasks done**: from the daily log, and before it started, the done
  dates SirisOS still keeps (60 days)
- **Inbox**: the average of each day's busiest moment (from the daily log)
- **Journal days**, wrap-ups and weekly reviews, with the journal streak
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.career import cpd
from app.career import store as career_store
from app.hub import sirisai_api
from app.hub.service import Hub
from app.tasks import service as tasks
from app.tasks import store as task_store
from app.trends import log
from app.wrapup import service as wrapup


def months_back(today: date, n: int = 12) -> list[str]:
    out, y, m = [], today.year, today.month
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return list(reversed(out))


def streaks(journal_days: set[str], today: date) -> dict[str, int]:
    """The current streak (counting today or, before tonight's wrap-up, yesterday) and the longest."""
    current, d = 0, today if today.isoformat() in journal_days else today - timedelta(days=1)
    while d.isoformat() in journal_days:
        current, d = current + 1, d - timedelta(days=1)
    longest = run = 0
    prev: date | None = None
    for iso in sorted(journal_days):
        day = date.fromisoformat(iso)
        run = run + 1 if prev and day - prev == timedelta(days=1) else 1
        longest, prev = max(longest, run), day
    return {"current": current, "longest": longest}


async def year(hub: Hub, today: date | None = None) -> dict[str, Any]:
    today = today or tasks.today()
    months = months_back(today)
    first = date.fromisoformat(months[0] + "-01")
    rows = {m: {"month": m, "cpd_hours": 0.0, "running_km": 0.0, "exercise_minutes": 0.0, "steps": [], "tasks_done": 0,
                "inbox": [], "journal_days": 0, "wrapups": 0, "reviews": 0, "energy_kwh": None} for m in months}
    from app.power import service as power

    kwh = power.by_month()
    for m, v in kwh.items():
        if m in rows:
            rows[m]["energy_kwh"] = v

    doc = career_store.load()
    for r in doc.cpd.records:
        if r.date and r.date[:7] in rows:
            rows[r.date[:7]]["cpd_hours"] += r.hours
    window = cpd.summary(doc, today)

    health = await sirisai_api.get(hub, "/siris/hub/v1/health/days", params={"days": (today - first).days + 1})
    health_from = None
    if health is None:  # SirisAI before 2.26 answers 35 days at most
        health = await sirisai_api.get(hub, "/siris/hub/v1/health/days", params={"days": 35})
    for d in (health or {}).get("days") or []:
        row = rows.get(str(d.get("date"))[:7])
        metrics = d.get("metrics") or {}
        if row is None:
            continue
        health_from = health_from or d["date"]
        row["running_km"] += float(metrics.get("running_km") or 0)
        row["exercise_minutes"] += float(metrics.get("exercise_minutes") or 0)
        if metrics.get("steps"):
            row["steps"].append(float(metrics["steps"]))

    daily = log.days()
    log_from = min(daily) if daily else None
    journal: set[str] = set()
    for iso, entry in daily.items():
        row = rows.get(iso[:7])
        if entry.get("journal"):
            journal.add(iso)
        if row is None:
            continue
        row["tasks_done"] += int(entry.get("tasks_done") or 0)
        if "inbox" in entry:
            row["inbox"].append(int(entry["inbox"]))
        row["wrapups"] += bool(entry.get("wrapup"))
        row["reviews"] += bool(entry.get("review"))
    # Before the log: SirisOS tasks' own done dates and the wrap-ups still kept.
    for t in task_store.load().tasks:
        day = (t.done_at or "")[:10]
        if day and (log_from is None or day < log_from) and day[:7] in rows:
            rows[day[:7]]["tasks_done"] += 1
    for iso, entry in wrapup._load().items():
        if log_from is None or iso < log_from:
            if entry.get("journal"):
                journal.add(iso)
            if iso[:7] in rows:
                rows[iso[:7]]["wrapups"] += 1
    for iso in journal:
        if iso[:7] in rows:
            rows[iso[:7]]["journal_days"] += 1

    out = []
    for m in months:
        r = rows[m]
        out.append({**r, "cpd_hours": round(r["cpd_hours"], 1), "running_km": round(r["running_km"], 1),
                    "exercise_minutes": round(r["exercise_minutes"]),
                    "steps": round(sum(r["steps"]) / len(r["steps"])) if r["steps"] else None,
                    "inbox": round(sum(r["inbox"]) / len(r["inbox"]), 1) if r["inbox"] else None})
    return {
        "today": today.isoformat(),
        "months": out,
        "cpd": {"window_total": window["total"], "required": window["required"]},
        "journal": streaks(journal, today),
        "since": {"health": health_from, "log": log_from},
        "available": {"health": health is not None, "energy": bool(kwh)},
    }
