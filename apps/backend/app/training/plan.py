"""A training plan for a race (5.5), worked out from your recent running.

- **Start** at what you've actually been running: the average of your last
  four weeks (at least 10 km a week), from Apple Health through SirisAI.
- **Build** about 10% a week towards a peak that suits the distance
  (5 km: 25 km a week, 10 km: 35, half: 50, marathon: 65), with every
  fourth week an easier one at 80%, so the body catches up.
- **Taper** before race day: two weeks for 10 km and under (80%, then 55%),
  three for longer (80%, 60%, 40%). Race week carries the race.
- **Each week** has three runs (four from 30 km a week): an easy run on
  Tuesday, a quality session on Thursday, the long run on Saturday, and an
  easy one on Sunday when there are four. The long run is about a third of
  the week, never longer than the race (32 km for a marathon).

It's a guide, not a coach: change the race or your weekly km and it's
worked out again.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

PEAK = [(5.0, 25.0), (10.0, 35.0), (21.1, 50.0), (42.2, 65.0)]
MIN_START = 10.0


def peak_for(distance_km: float) -> float:
    for limit, peak in PEAK:
        if distance_km <= limit + 0.5:
            return peak
    return PEAK[-1][1]


def taper(distance_km: float) -> list[float]:
    return [0.8, 0.55] if distance_km <= 10.5 else [0.8, 0.6, 0.4]


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def weekly_targets(start_km: float, race_day: date, distance_km: float, today: date) -> list[dict[str, Any]]:
    """[{week_of, km, kind}] from this week to race week."""
    first = monday(today)
    last = monday(race_day)
    weeks = max(1, (last - first).days // 7 + 1)
    tapering = taper(distance_km)
    build_weeks = max(0, weeks - len(tapering))
    peak = peak_for(distance_km)
    km = max(MIN_START, start_km)
    out: list[dict[str, Any]] = []
    top = km
    for i in range(build_weeks):
        if i > 0:
            km = min(peak, km * 1.1) if (i % 4) != 3 else km
        easy = (i % 4) == 3
        target = round(km * 0.8 if easy else km, 1)
        top = max(top, km)
        out.append({"week_of": (first + timedelta(weeks=i)).isoformat(), "km": target, "kind": "easier" if easy else "build"})
    for j, share in enumerate(tapering[-weeks:] if weeks < len(tapering) else tapering):
        i = len(out)
        out.append({"week_of": (first + timedelta(weeks=i)).isoformat(), "km": round(top * share, 1),
                    "kind": "race" if i == weeks - 1 else "taper"})
    return out[:weeks]


def sessions(week_km: float, distance_km: float, week_of: date, race_day: date | None = None) -> list[dict[str, Any]]:
    """The week's runs: [{date, kind, km, title}]."""
    four = week_km >= 30
    long_cap = 32.0 if distance_km > 21.6 else distance_km
    long_km = min(long_cap, round(week_km * (0.3 if four else 0.38), 1))
    rest = week_km - long_km
    plan = [(1, "easy", rest * (0.35 if four else 0.5)), (3, "quality", rest * (0.4 if four else 0.5)), (5, "long", long_km)]
    if four:
        plan.append((6, "easy", rest * 0.25))
    out = []
    for offset, kind, km in plan:
        day = week_of + timedelta(days=offset)
        if race_day and day > race_day:
            continue
        if race_day and day == race_day:
            continue
        out.append({"date": day.isoformat(), "kind": kind, "km": max(2.0, round(km)), "title": title(kind, max(2.0, round(km)))})
    # Strength and mobility (5.8): a short mobility session on Monday and
    # strength on Wednesday, left out in race week. They count towards load
    # (exercise minutes) but not distance.
    if not (race_day and monday(race_day) == week_of):
        for offset, kind in ((0, "mobility"), (2, "strength")):
            day = week_of + timedelta(days=offset)
            if not race_day or day < race_day:
                out.append({"date": day.isoformat(), "kind": kind, "km": 0, "title": title(kind, 0)})
        out.sort(key=lambda s: s["date"])
    if race_day and monday(race_day) == week_of:
        out = [s for s in out if s["kind"] != "long"]
        out.append({"date": race_day.isoformat(), "kind": "race", "km": distance_km, "title": f"Race day: {distance_km:g} km"})
        out.sort(key=lambda s: s["date"])
    return out


def title(kind: str, km: float) -> str:
    return {
        "easy": f"Easy run, {km:g} km",
        "quality": f"Tempo run, {km:g} km (warm up, then 20 min at a comfortably hard pace)",
        "long": f"Long run, {km:g} km, easy pace",
        "strength": "Strength, 30 min: squats, lunges, deadlifts, calf raises, core",
        "mobility": "Mobility, 20 min: hips, hamstrings, calves and ankles",
    }.get(kind, f"Run, {km:g} km")
