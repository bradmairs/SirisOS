"""Bedroom ready for sleep (10.4): before you wind down, is the bedroom a good temperature?

Pick the bedroom's temperature (and humidity, if there's one) sensor in Home Assistant. From an hour before your
bedtime (Health's bedtime, else 10:30pm), Home shows the bedroom and suggests a fan, aircon or heater when it's
outside your range (17 to 20°C to start; humidity 40 to 60%), with one notification a night. Each night's reading
is kept, and once there are two weeks of them with your sleep from Apple Health, the card says which bedroom
temperatures go with your best sleep. Kept in bedroom.json (SIRISOS_BEDROOM_PATH).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any

from app.hub import sirisai_api
from app.hub.service import Hub
from app.services import json_store

ENTITY = re.compile(r"(sensor|climate)\.[a-z0-9_]{1,100}")
DEFAULT_BED = "22:30"
MIN_NIGHTS = 14


def _path():
    return json_store.data_path("SIRISOS_BEDROOM_PATH", "bedroom.json")


def load() -> dict[str, Any]:
    doc = json_store.read(_path(), {}) or {}
    doc.setdefault("temp_entity", None)
    doc.setdefault("humidity_entity", None)
    doc.setdefault("low", 17.0)
    doc.setdefault("high", 20.0)
    doc.setdefault("nights", [])
    return doc


def save_settings(temp_entity: str | None, humidity_entity: str | None, low: float | None, high: float | None) -> dict[str, Any]:
    doc = load()
    for name, val in (("temp_entity", temp_entity), ("humidity_entity", humidity_entity)):
        if val is not None:
            if val and not ENTITY.fullmatch(val):
                raise ValueError("Pick a Home Assistant sensor (sensor.something).")
            doc[name] = val or None
    if low is not None and high is not None:
        if not 10 <= low < high <= 30:
            raise ValueError("A range between 10 and 30°C, low first.")
        doc["low"], doc["high"] = float(low), float(high)
    json_store.write(_path(), doc)
    return doc


async def _bedtime(hub: Hub, today: str | None = None) -> str:
    """Health's bedtime, looked up once a day."""
    from app.health import service as health

    doc = load()
    cached = doc.get("bedtime_cache") or {}
    if today and cached.get("date") == today:
        return cached["bed"]
    bed = DEFAULT_BED
    try:
        b = (await health.overview(hub)).get("bedtime") or {}
        t = str(b.get("bedtime") or "")
        if re.fullmatch(r"\d{1,2}:\d{2}", t[:5]):
            bed = t[:5]
    except Exception:  # noqa: BLE001
        pass
    if today:
        doc["bedtime_cache"] = {"date": today, "bed": bed}
        json_store.write(_path(), doc)
    return bed


async def reading(hub: Hub) -> dict[str, Any] | None:
    doc = load()
    ids = [i for i in (doc["temp_entity"], doc["humidity_entity"]) if i]
    if not ids:
        return None
    body = await sirisai_api.get(hub, "/siris/hub/v1/sensors", params={"ids": ",".join(ids)}, timeout=10.0) or {}
    by = {s["entity_id"]: s for s in body.get("sensors") or []}

    def val(eid: str | None) -> float | None:
        try:
            return float(by[eid]["state"]) if eid and eid in by and by[eid].get("state") not in (None, "unknown", "unavailable") else None
        except (TypeError, ValueError):
            return None

    return {"temp": val(doc["temp_entity"]), "humidity": val(doc["humidity_entity"])}


def advice(temp: float | None, humidity: float | None, low: float, high: float) -> str | None:
    if temp is None:
        return None
    if temp > high + 0.5:
        return f"Bedroom is {temp:.1f}°: fan or aircon for half an hour before bed?"
    if temp < low - 0.5:
        return f"Bedroom is {temp:.1f}°: a little heat before bed?"
    if humidity is not None and humidity > 65:
        return f"Bedroom is {temp:.1f}° but {humidity:.0f}% humid: a fan or the dehumidifier?"
    if humidity is not None and humidity < 35:
        return f"Bedroom is {temp:.1f}° and dry ({humidity:.0f}%)."
    return None


def best_range(nights: list[dict[str, Any]], sleep: dict[str, float]) -> dict[str, Any] | None:
    """Your sleep in nights grouped by bedroom temperature (2-degree steps): the band with the most sleep."""
    paired = [(n["temp"], sleep[n["sleep_date"]]) for n in nights if n.get("temp") is not None and n.get("sleep_date") in sleep]
    if len(paired) < MIN_NIGHTS:
        return None
    bands: dict[int, list[float]] = {}
    for t, s in paired:
        bands.setdefault(int(t // 2 * 2), []).append(s)
    good = {b: v for b, v in bands.items() if len(v) >= 3}
    if len(good) < 2:
        return None
    best = max(good, key=lambda b: mean(good[b]))
    worst = min(good, key=lambda b: mean(good[b]))
    return {"low": best, "high": best + 2, "sleep": round(mean(good[best]), 1), "other": round(mean(good[worst]), 1), "nights": len(paired)}


async def card(hub: Hub, local_now: datetime, with_best: bool = True) -> dict[str, Any]:
    doc = load()
    out: dict[str, Any] = {"temp_entity": doc["temp_entity"], "humidity_entity": doc["humidity_entity"], "low": doc["low"], "high": doc["high"], "show": False}
    if not doc["temp_entity"]:
        return out
    bed = await _bedtime(hub, local_now.date().isoformat())
    h, m = (int(x) for x in bed.split(":"))
    bedtime = local_now.replace(hour=h, minute=m, second=0, microsecond=0)
    if bedtime - local_now > timedelta(hours=12):
        bedtime -= timedelta(days=1)
    window = bedtime - timedelta(hours=1) <= local_now <= bedtime + timedelta(hours=1)
    if not window and not with_best:
        return out
    r = await reading(hub) or {}
    out.update({"bedtime": bed, "temp": r.get("temp"), "humidity": r.get("humidity"), "show": window,
                "advice": advice(r.get("temp"), r.get("humidity"), doc["low"], doc["high"])})
    if window and r.get("temp") is not None:
        night = bedtime.date().isoformat() if bedtime.hour >= 12 else (bedtime.date() - timedelta(days=1)).isoformat()
        if not any(n["date"] == night for n in doc["nights"]):
            doc["nights"] = [*doc["nights"], {"date": night, "temp": r["temp"], "humidity": r.get("humidity"),
                                               "sleep_date": (date.fromisoformat(night) + timedelta(days=1)).isoformat()}][-120:]
            json_store.write(_path(), doc)
    if not with_best:
        return out
    days = await sirisai_api.get(hub, "/siris/hub/v1/health/days", params={"days": 120}, timeout=15.0) or {}
    sleep = {d["date"]: d["metrics"]["sleep_hours"] for d in days.get("days") or [] if (d.get("metrics") or {}).get("sleep_hours")}
    out["best"] = best_range(load()["nights"], sleep)
    out["nights"] = len(load()["nights"])
    return out


async def push_message(hub: Hub, local_now: datetime) -> list[dict[str, Any]]:
    from app.push import store

    if not load()["temp_entity"] or local_now.hour < 17 or f"bedroom:{local_now.date().isoformat()}" in store.sent():
        return []
    c = await card(hub, local_now, with_best=False)
    if not c["show"] or not c.get("advice"):
        return []
    return [{"key": f"bedroom:{local_now.date().isoformat()}", "topic": "nudges", "title": "Bedroom before bed", "body": c["advice"],
             "url": "/", "urgency": "normal"}]
