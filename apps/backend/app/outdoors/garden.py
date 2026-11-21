"""Garden and rain (10.4): water only when no rain is coming.

Each morning, from the hourly forecast and the rain that's fallen over the last three days:
- **Water today** when under 5 mm has fallen and under 2 mm is coming in the next two days (and the chance
  stays under 50%); on a day of 30°C or more, early or in the evening.
- **Skip it** when 5 mm or more is forecast, or you watered in the last two days (unless it's hot).

On Home in the morning, and a 7am notification on a day to water. "Water now" runs the SirisAI protocol you pick
(e.g. one that turns the irrigation on); "Done" records it. Kept in garden.json (SIRISOS_GARDEN_PATH).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from app.hub.service import Hub
from app.outdoors import weather
from app.services import json_store

PUSH_HOUR = 7
HOT_C = 30


def _path():
    return json_store.data_path("SIRISOS_GARDEN_PATH", "garden.json")


def load() -> dict[str, Any]:
    doc = json_store.read(_path(), {}) or {}
    doc.setdefault("on", False)
    doc.setdefault("protocol", None)
    doc.setdefault("last_watered", None)
    return doc


def save_settings(on: bool | None = None, protocol: str | None = None) -> dict[str, Any]:
    doc = load()
    if on is not None:
        doc["on"] = on
    if protocol is not None:
        doc["protocol"] = protocol.strip()[:80] or None
    json_store.write(_path(), doc)
    return doc


def watered(on: date) -> dict[str, Any]:
    doc = load()
    doc["last_watered"] = on.isoformat()
    json_store.write(_path(), doc)
    return doc


def decide(past_mm: float, hours: list[dict[str, Any]], today: date, last_watered: str | None) -> dict[str, Any]:
    end = (datetime.combine(today, datetime.min.time()) + timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M")
    ahead = [h for h in hours if h["time"] < end]
    coming = round(sum(h.get("rain_mm") or 0 for h in ahead), 1)
    chance = max((h.get("rain_chance_percent") or 0 for h in ahead), default=0)
    high = max((h.get("temperature_c") or 0 for h in hours if h["time"][:10] == today.isoformat()), default=None)
    hot = high is not None and high >= HOT_C
    recently = last_watered and (today - date.fromisoformat(last_watered)).days < 2
    if coming >= 5 or chance >= 60:
        return {"water": False, "why": f"Rain's coming ({coming:g} mm in the next two days): no need to water.", "coming_mm": coming, "past_mm": past_mm, "high_c": high}
    if past_mm >= 5:
        return {"water": False, "why": f"{past_mm:g} mm has fallen in the last three days.", "coming_mm": coming, "past_mm": past_mm, "high_c": high}
    if recently and not hot:
        return {"water": False, "why": "Watered in the last two days.", "coming_mm": coming, "past_mm": past_mm, "high_c": high}
    why = f"Dry: {past_mm:g} mm in the last three days and {coming:g} mm coming."
    if hot:
        why += f" It's {round(high)}° today: water early or in the evening."
    return {"water": True, "why": why, "coming_mm": coming, "past_mm": past_mm, "high_c": high, "hot": hot}


async def today_check(hub: Hub, today: date) -> dict[str, Any]:
    doc = load()
    out: dict[str, Any] = {"on": doc["on"], "protocol": doc["protocol"], "last_watered": doc["last_watered"]}
    if not doc["on"]:
        return out
    wx = await weather.hourly(hub, days=3, past_days=3)
    if wx is None:
        return {**out, "unavailable": True}
    return {**out, **decide(float(wx.get("past_rain_mm") or 0), wx["hours"], today, doc["last_watered"])}


async def push_message(hub: Hub, local_now: datetime) -> list[dict[str, Any]]:
    from app.push import store

    # 7 to 8am only, and once: the forecast is fetched in that hour, not all day.
    if local_now.hour != PUSH_HOUR or not load()["on"] or f"garden:{local_now.date().isoformat()}" in store.sent():
        return []
    c = await today_check(hub, local_now.date())
    if not c.get("water") or c.get("last_watered") == local_now.date().isoformat():
        return []
    return [{"key": f"garden:{local_now.date().isoformat()}", "topic": "brief", "title": "Water the garden today", "body": c["why"],
             "url": "/", "urgency": "normal"}]
