"""Patterns across sections (11.3).

Pairs of your own day-by-day numbers from different parts of SirisOS and SirisAI, compared over the last four months:
drinks and next morning's HRV, caffeine, a busy calendar, a late workout or a big day on your feet against that night's
sleep, a busy day against what you spent, a short night against the next day's spending, HRV against how much you
lifted. A pattern is only said when it's clear and keeps up:

- at least 21 days with both numbers, with at least 7 on each side of the split;
- the difference is meaningful: at least a third of that number's usual day-to-day spread;
- it shows in both the first and the second half of the period, the same way round.

Each comes in plain words with the two averages and one thing to try. A weekly card on Home shows the strongest, and a
new one sends one notification on a Sunday.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from statistics import mean, pstdev
from typing import Any

from app.hub import sirisai_api
from app.hub.service import Hub
from app.services import json_store

DAYS = 120
MIN_PAIRS = 21
MIN_SIDE = 7
MIN_EFFECT = 0.35
CACHE_HOURS = 6

# x on a day, y on the same day (lag 0) or the next (lag 1); "split" is how x is divided: "any" (some vs none) or "median".
PAIRS: list[dict[str, Any]] = [
    {"id": "drinks-hrv", "x": "alcohol_drinks", "y": "heart_rate_variability", "lag": 1, "split": "any",
     "hi": "after drinking", "lo": "after a day without", "y_label": "your HRV next morning", "unit": " ms", "bad": "down",
     "try": "Try a dry week and watch whether HRV comes back up."},
    {"id": "drinks-sleep", "x": "alcohol_drinks", "y": "sleep_hours", "lag": 1, "split": "any",
     "hi": "after drinking", "lo": "after a day without", "y_label": "you slept", "unit": " h", "bad": "down",
     "try": "Stop a couple of hours before bed, with water in between."},
    {"id": "caffeine-sleep", "x": "caffeine_mg", "y": "sleep_hours", "lag": 1, "split": "median",
     "hi": "on more-coffee days", "lo": "on lighter days", "y_label": "you slept", "unit": " h", "bad": "down",
     "try": "Try no coffee after midday for a week."},
    {"id": "busy-sleep", "x": "busy_minutes", "y": "sleep_hours", "lag": 1, "split": "median",
     "hi": "after a busy calendar", "lo": "after a lighter one", "y_label": "you slept", "unit": " h", "bad": "down",
     "try": "On busy days, keep the evening quiet and wind down on time."},
    {"id": "lategym-sleep", "x": "late_workout", "y": "sleep_hours", "lag": 1, "split": "any",
     "hi": "after an evening workout", "lo": "after other days", "y_label": "you slept", "unit": " h", "bad": "down",
     "try": "Move workouts earlier when you can, or keep evening ones lighter."},
    {"id": "steps-sleep", "x": "steps", "y": "sleep_hours", "lag": 1, "split": "median",
     "hi": "after a big day on your feet", "lo": "after a quieter one", "y_label": "you slept", "unit": " h", "bad": "down",
     "try": "A walk on desk days might help you sleep."},
    {"id": "busy-spend", "x": "busy_minutes", "y": "spent", "lag": 0, "split": "median",
     "hi": "on busy days", "lo": "on lighter days", "y_label": "you spent", "unit": "", "money": True, "bad": "up",
     "try": "Plan dinner on busy days so takeaway isn't the default."},
    {"id": "shortsleep-spend", "x": "sleep_hours", "y": "spent", "lag": 0, "split": "median", "flip": True,
     "hi": "after a short night", "lo": "after a good one", "y_label": "you spent", "unit": "", "money": True, "bad": "up",
     "try": "After a bad night, give purchases a day before you buy."},
    {"id": "hrv-lift", "x": "heart_rate_variability", "y": "lifted_kg", "lag": 0, "split": "median",
     "hi": "on high-HRV days", "lo": "on low-HRV days", "y_label": "you lifted", "unit": " kg", "bad": "down",
     "try": "Save heavy sessions for mornings when HRV is up; keep low-HRV days light."},
    {"id": "drinks-mood", "x": "alcohol_drinks", "y": "mood", "lag": 1, "split": "any",
     "hi": "after drinking", "lo": "after a day without", "y_label": "your mood the next day", "unit": "", "bad": "down",
     "try": "Note how you feel the morning after, and see if it's worth it."},
]


def _path():
    return json_store.data_path("SIRISOS_PATTERNS_PATH", "patterns.json")


def find(series: dict[str, dict[str, float]], days: list[str]) -> list[dict[str, Any]]:
    """The pure part: series {name: {date: value}} over `days` (oldest first) -> patterns, strongest first."""
    out = []
    for p in PAIRS:
        xs, ys = series.get(p["x"]) or {}, series.get(p["y"]) or {}
        pairs: list[tuple[str, float, float]] = []
        for i, d in enumerate(days):
            j = i + p["lag"]
            if j >= len(days) or d not in xs or days[j] not in ys:
                continue
            pairs.append((d, xs[d], ys[days[j]]))
        if len(pairs) < MIN_PAIRS:
            continue
        xv = [x for _, x, _ in pairs]
        cut = 0 if p["split"] == "any" else sorted(xv)[len(xv) // 2]

        def side(x: float) -> bool:
            hi = x > cut if p["split"] == "any" else x >= cut
            return not hi if p.get("flip") else hi

        def effect(rows: list[tuple[str, float, float]]) -> tuple[float, float, float, int, int] | None:
            hi = [y for _, x, y in rows if side(x)]
            lo = [y for _, x, y in rows if not side(x)]
            if len(hi) < MIN_SIDE // 2 or len(lo) < MIN_SIDE // 2:
                return None
            spread = pstdev([y for _, _, y in rows]) or 0
            if not spread:
                return None
            return (mean(hi) - mean(lo)) / spread, mean(hi), mean(lo), len(hi), len(lo)

        whole = effect(pairs)
        if not whole or whole[3] < MIN_SIDE or whole[4] < MIN_SIDE or abs(whole[0]) < MIN_EFFECT:
            continue
        half = len(pairs) // 2
        first, second = effect(pairs[:half]), effect(pairs[half:])
        if not first or not second or (first[0] > 0) != (whole[0] > 0) or (second[0] > 0) != (whole[0] > 0):
            continue
        d, hi, lo, n_hi, n_lo = whole
        direction = "up" if hi > lo else "down"
        fmt = (lambda v: f"${v:,.0f}") if p.get("money") else (lambda v: f"{v:,.1f}{p['unit']}" if abs(v) < 20 else f"{v:,.0f}{p['unit']}")
        text = f"{p['hi'][0].upper() + p['hi'][1:]}, {p['y_label']} {fmt(hi)} on average, against {fmt(lo)} {p['lo']}."
        out.append({"id": p["id"], "text": text, "try": p["try"] if direction == p["bad"] else None, "strength": round(abs(d), 2),
                    "worse": direction == p["bad"], "days": len(pairs), "hi": round(hi, 2), "lo": round(lo, 2), "n": [n_hi, n_lo]})
    return sorted(out, key=lambda r: (not r["worse"], -r["strength"]))


async def _series(hub: Hub, today: date) -> tuple[dict[str, dict[str, float]], list[str]]:
    start = today - timedelta(days=DAYS)
    days = [(start + timedelta(days=i)).isoformat() for i in range(DAYS + 1)]
    series: dict[str, dict[str, float]] = {}
    health = await sirisai_api.get(hub, "/siris/hub/v1/health/days", params={"days": DAYS + 1}, timeout=20.0) or {}
    for d in health.get("days") or []:
        for k, v in (d.get("metrics") or {}).items():
            if isinstance(v, (int, float)):
                series.setdefault(k, {})[d["date"]] = float(v)
    cal = await sirisai_api.get(hub, "/siris/hub/v1/calendar", params={"start": start.isoformat(), "end": (today + timedelta(days=1)).isoformat()}, timeout=20.0) or {}
    busy: dict[str, float] = {d: 0.0 for d in days}
    for e in cal.get("events") or []:
        if not isinstance(e, dict) or e.get("all_day") or "T" not in str(e.get("start")) or not e.get("end"):
            continue
        try:
            s = datetime.fromisoformat(str(e["start"]).replace("Z", "+00:00"))
            f = datetime.fromisoformat(str(e["end"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        k = s.date().isoformat()
        if k in busy and timedelta(0) < f - s <= timedelta(hours=10):
            busy[k] += (f - s).total_seconds() / 60
    if cal.get("events"):
        series["busy_minutes"] = busy
    try:
        from app.budget import actuals

        doc = actuals.load()
        if doc["transactions"]:
            first = min(t["date"] for t in doc["transactions"])
            spent = {d: 0.0 for d in days if d >= first}
            for t in doc["transactions"]:
                if t["amount"] < 0 and not t.get("ignored") and t["date"] in spent:
                    spent[t["date"]] += -t["amount"]
            series["spent"] = spent
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.gym import store as gym

        g = gym.load()
        late, lifted = {d: 0.0 for d in days}, {}
        for s in gym.counted(g):
            when = datetime.fromisoformat(s.started_at.replace("Z", "+00:00"))
            k = when.date().isoformat()
            if k in late and when.hour >= 18:
                late[k] = 1.0
            vol = sum((st.weight or 0) * (st.reps or 0) for e in s.entries for st in getattr(e, "sets", []) if getattr(st, "done", True))
            if vol and k in late:
                lifted[k] = lifted.get(k, 0) + vol
        if g.sessions:
            series["late_workout"], series["lifted_kg"] = late, lifted
    except Exception:  # noqa: BLE001
        pass
    return series, days


async def current(hub: Hub, now: datetime, fresh: bool = False) -> dict[str, Any]:
    doc = json_store.read(_path(), {}) or {}
    if not fresh and doc.get("at") and doc["at"] > (now - timedelta(hours=CACHE_HOURS)).isoformat():
        return doc
    series, days = await _series(hub, now.date())
    found = find(series, days)
    doc = {"at": now.isoformat(timespec="minutes"), "patterns": found, "days": DAYS,
           "sources": sorted(k for k in ("sleep_hours", "heart_rate_variability", "busy_minutes", "spent", "lifted_kg", "alcohol_drinks", "caffeine_mg") if series.get(k)),
           "said": doc.get("said", {})}
    json_store.write(_path(), doc)
    return doc


async def push_message(hub: Hub, local_now: datetime) -> list[dict[str, Any]]:
    """Sunday 10am: a pattern that's new (not said in the last eight weeks)."""
    from app.push import store

    key = f"pattern:{local_now.strftime('%G-W%V')}"
    if local_now.weekday() != 6 or local_now.hour != 10 or key in store.sent():
        return []
    doc = await current(hub, local_now, fresh=True)
    said = doc.get("said") or {}
    cutoff = (local_now.date() - timedelta(weeks=8)).isoformat()
    new = [p for p in doc["patterns"] if said.get(p["id"], "") < cutoff]
    if not new:
        return []
    p = new[0]
    said[p["id"]] = local_now.date().isoformat()
    doc["said"] = said
    json_store.write(_path(), doc)
    return [{"key": key, "topic": "brief", "title": "A pattern in your days", "body": p["text"] + (f" {p['try']}" if p["try"] else ""), "url": "/", "urgency": "normal"}]
