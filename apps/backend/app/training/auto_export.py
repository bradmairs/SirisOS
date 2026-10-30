"""Health Auto Export's JSON (the iPhone app's "REST API" automation), so
Apple Health reaches SirisAI on its own (SirisOS 5.62; the same reading as SirisAI 3.11, so any SirisAI version works).

The app posts {"data": {"metrics": [...], "workouts": [...]}} on a
schedule. Each metric has a `name`, `units` and `data`: readings with a
`date` ("2026-10-28 00:00:00 +1100") and a `qty`. With "Aggregate data:
Day" there's one reading per day; without it there are many, so each
metric is combined per day the way it adds up: steps, active energy and
exercise minutes are summed, heart rates averaged, weight is the last one.
Sleep comes as `sleep_analysis` with `totalSleep` (or `asleep`) in hours.
Running distance comes from the workouts: every run's distance that day.

The day is the reading's own local date, as the phone wrote it.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

# Health Auto Export metric name -> (SirisAI metric, how a day adds up).
METRICS: dict[str, tuple[str, str]] = {
    "step_count": ("steps", "sum"),
    "resting_heart_rate": ("resting_heart_rate", "mean"),
    "heart_rate_variability": ("heart_rate_variability", "mean"),
    "heart_rate_variability_sdnn": ("heart_rate_variability", "mean"),
    "active_energy": ("active_energy_kcal", "sum"),
    "apple_exercise_time": ("exercise_minutes", "sum"),
    "weight_body_mass": ("weight_kg", "last"),
    "body_mass": ("weight_kg", "last"),
    "sleep_analysis": ("sleep_hours", "sum"),
}


def looks_like(body: Any) -> bool:
    data = body.get("data") if isinstance(body, dict) else None
    return isinstance(data, dict) and (isinstance(data.get("metrics"), list) or isinstance(data.get("workouts"), list))


def _day(value: Any) -> str | None:
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 and text[4] == "-" and text[7] == "-" else None


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _convert(metric: str, units: str, qty: float) -> float:
    u = units.lower()
    if metric == "active_energy_kcal" and u in ("kj", "kilojoule", "kilojoules"):
        return qty / 4.184
    if metric == "weight_kg" and u in ("lb", "lbs", "pound", "pounds"):
        return qty * 0.45359237
    if metric == "sleep_hours" and u in ("min", "minutes"):
        return qty / 60
    if metric == "exercise_minutes" and u in ("hr", "h", "hours"):
        return qty * 60
    return qty


def parse(body: dict[str, Any]) -> tuple[dict[str, dict[str, float]], list[str]]:
    """(day -> {metric: value}, metric names it doesn't use)."""
    data = body.get("data") or {}
    readings: dict[tuple[str, str], list[float]] = defaultdict(list)
    how: dict[str, str] = {}
    ignored: set[str] = set()
    for m in data.get("metrics") or []:
        if not isinstance(m, dict):
            continue
        name = str(m.get("name") or "").strip().lower()
        if name not in METRICS:
            if name:
                ignored.add(name)
            continue
        metric, combine = METRICS[name]
        how[metric] = combine
        units = str(m.get("units") or "")
        for r in m.get("data") or []:
            if not isinstance(r, dict):
                continue
            day = _day(r.get("date"))
            qty = _number(r.get("qty"))
            if metric == "sleep_hours" and qty is None:
                qty = _number(r.get("totalSleep")) or _number(r.get("asleep"))
            if day and qty is not None:
                readings[(day, metric)].append(_convert(metric, units, qty))
    for w in data.get("workouts") or []:
        if not isinstance(w, dict) or "run" not in str(w.get("name") or "").lower():
            continue
        day = _day(w.get("start"))
        dist = w.get("distance")
        qty = _number(dist.get("qty")) if isinstance(dist, dict) else _number(dist)
        units = str(dist.get("units") or "km").lower() if isinstance(dist, dict) else "km"
        if day and qty is not None:
            readings[(day, "running_km")].append(qty * 1.609344 if units in ("mi", "mile", "miles") else qty / 1000 if units == "m" else qty)
            how["running_km"] = "sum"
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for (day, metric), values in readings.items():
        combine = how[metric]
        value = sum(values) if combine == "sum" else mean(values) if combine == "mean" else values[-1]
        out[day][metric] = round(value, 2)
    return dict(out), sorted(ignored)
