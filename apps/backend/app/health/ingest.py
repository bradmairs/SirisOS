"""Everything Health Auto Export sends, kept by SirisOS (5.7) for the Health
section: far more than SirisAI's eight metrics, plus the night's sleep
times and stages, and each workout.

Readings are combined per day the way each adds up: counts and energy are
summed, rates and heart figures averaged, body measurements are the last of
the day. The day is the reading's own local date, as the phone wrote it;
sleep belongs to the morning you woke up.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

from app.services import json_store

# Health Auto Export name -> (metric, how a day adds up)
METRICS: dict[str, tuple[str, str]] = {
    "step_count": ("steps", "sum"),
    "active_energy": ("active_energy_kcal", "sum"),
    "basal_energy_burned": ("basal_energy_kcal", "sum"),
    "apple_exercise_time": ("exercise_minutes", "sum"),
    "apple_stand_hour": ("stand_hours", "sum"),
    "walking_running_distance": ("walk_run_km", "sum"),
    "flights_climbed": ("flights", "sum"),
    "mindful_minutes": ("mindful_minutes", "sum"),
    "time_in_daylight": ("daylight_minutes", "sum"),
    "resting_heart_rate": ("resting_heart_rate", "mean"),
    "heart_rate_variability": ("heart_rate_variability", "mean"),
    "heart_rate_variability_sdnn": ("heart_rate_variability", "mean"),
    "walking_heart_rate_average": ("walking_heart_rate", "mean"),
    "respiratory_rate": ("respiratory_rate", "mean"),
    "blood_oxygen_saturation": ("blood_oxygen", "mean"),
    "oxygen_saturation": ("blood_oxygen", "mean"),
    "apple_sleeping_wrist_temperature": ("wrist_temperature", "mean"),
    "vo2_max": ("vo2_max", "last"),
    "weight_body_mass": ("weight_kg", "last"),
    "body_mass": ("weight_kg", "last"),
    "body_fat_percentage": ("body_fat_pct", "last"),
    "body_mass_index": ("bmi", "last"),
    "lean_body_mass": ("lean_mass_kg", "last"),
}
SLEEP_FIELDS = {"totalSleep": "sleep_hours", "asleep": "sleep_hours", "deep": "sleep_deep_h", "rem": "sleep_rem_h",
                "core": "sleep_core_h", "awake": "sleep_awake_h", "inBed": "in_bed_h"}
KEEP_DAYS = 800


def _day(value: Any) -> str | None:
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 and text[4] == "-" and text[7] == "-" else None


def _num(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("qty")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _convert(metric: str, units: str, qty: float) -> float:
    u = units.lower()
    if metric.endswith("_kcal") and u in ("kj", "kilojoule", "kilojoules"):
        return qty / 4.184
    if metric in ("weight_kg", "lean_mass_kg") and u in ("lb", "lbs"):
        return qty * 0.45359237
    if metric == "walk_run_km" and u in ("mi", "miles"):
        return qty * 1.609344
    if metric == "blood_oxygen" and qty <= 1.0:
        return qty * 100
    if metric == "body_fat_pct" and qty <= 1.0:
        return qty * 100
    if metric == "wrist_temperature" and u in ("degf", "°f", "f"):
        return (qty - 32) * 5 / 9
    return qty


def parse(body: dict[str, Any]) -> dict[str, Any]:
    """{"metrics": {day: {metric: value}}, "sleep": {day: {start, end}}, "workouts": {day: [...]}}"""
    data = body.get("data") or {}
    readings: dict[tuple[str, str], list[float]] = defaultdict(list)
    how: dict[str, str] = {"heart_rate_min": "min", "heart_rate_max": "max", "heart_rate_avg": "mean"}
    sleep_times: dict[str, dict[str, str]] = {}
    for m in data.get("metrics") or []:
        if not isinstance(m, dict):
            continue
        name = str(m.get("name") or "").strip().lower()
        units = str(m.get("units") or "")
        for r in m.get("data") or []:
            if not isinstance(r, dict) or not (day := _day(r.get("date"))):
                continue
            if name == "sleep_analysis":
                for field, metric in SLEEP_FIELDS.items():
                    v = _num(r.get(field))
                    if v is not None and not (metric == "sleep_hours" and field == "asleep" and r.get("totalSleep") is not None):
                        readings[(day, metric)].append(v / 60 if units.lower().startswith("min") else v)
                        how[metric] = "sum"
                if r.get("sleepStart") or r.get("sleepEnd"):
                    sleep_times[day] = {"start": str(r.get("sleepStart") or "")[:25], "end": str(r.get("sleepEnd") or "")[:25]}
            elif name == "heart_rate":
                for field, metric in (("Avg", "heart_rate_avg"), ("Min", "heart_rate_min"), ("Max", "heart_rate_max")):
                    v = _num(r.get(field))
                    if v is not None:
                        readings[(day, metric)].append(v)
            elif name in METRICS:
                metric, combine = METRICS[name]
                how[metric] = combine
                v = _num(r.get("qty"))
                if v is not None:
                    readings[(day, metric)].append(_convert(metric, units, v))
    workouts: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for w in data.get("workouts") or []:
        if not isinstance(w, dict) or not (day := _day(w.get("start"))):
            continue
        dist = w.get("distance")
        km = _num(dist)
        if km is not None and isinstance(dist, dict) and str(dist.get("units") or "").lower() in ("mi", "miles"):
            km *= 1.609344
        energy = w.get("activeEnergyBurned") or w.get("activeEnergy")
        kcal = _num(energy)
        if kcal is not None and isinstance(energy, dict) and str(energy.get("units") or "").lower() == "kj":
            kcal /= 4.184
        duration = _num(w.get("duration"))
        entry = {"name": str(w.get("name") or "Workout")[:60], "start": str(w.get("start") or "")[:25],
                 "minutes": round(duration / 60) if duration and duration > 300 else round(duration) if duration else None,
                 "km": round(km, 2) if km else None, "kcal": round(kcal) if kcal else None,
                 "avg_hr": _num(w.get("avgHeartRate") or w.get("heartRateAvg")), "max_hr": _num(w.get("maxHeartRate"))}
        workouts[day].append(entry)
        if "run" in entry["name"].lower() and km:
            readings[(day, "running_km")].append(km)
            how["running_km"] = "sum"
    metrics: dict[str, dict[str, float]] = defaultdict(dict)
    for (day, metric), values in readings.items():
        combine = how.get(metric, "mean")
        v = sum(values) if combine == "sum" else min(values) if combine == "min" else max(values) if combine == "max" \
            else values[-1] if combine == "last" else mean(values)
        metrics[day][metric] = round(v, 2)
    return {"metrics": dict(metrics), "sleep": sleep_times, "workouts": dict(workouts)}


def _path():
    return json_store.data_path("SIRISOS_HEALTH_PATH", "health-days.json")


def load() -> dict[str, Any]:
    doc = json_store.read(_path(), {})
    doc = doc if isinstance(doc, dict) else {}
    for k in ("metrics", "sleep", "workouts"):
        doc.setdefault(k, {})
    return doc


def store(parsed: dict[str, Any]) -> int:
    """Merge one export in; a later export of the same day replaces that day's values."""
    doc = load()
    for day, m in parsed["metrics"].items():
        doc["metrics"][day] = {**doc["metrics"].get(day, {}), **m}
    doc["sleep"].update(parsed["sleep"])
    for day, ws in parsed["workouts"].items():
        doc["workouts"][day] = ws
    for k in ("metrics", "sleep", "workouts"):
        if len(doc[k]) > KEEP_DAYS:
            doc[k] = dict(sorted(doc[k].items())[-KEEP_DAYS:])
    json_store.write(_path(), doc)
    return len(parsed["metrics"])
