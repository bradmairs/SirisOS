"""Trips (10.2): everything for going away, on one card.

Add where and when. SirisOS then puts together:
- **the weather there** (Open-Meteo's forecast, up to 16 days out; nothing is
  sent but the place and dates);
- **a packing list** from how long it is, the weather and whether it's
  overseas, to tick off and add to;
- **bills due while you're away**, from your recurring charges and renewals;
- **the out-of-office**: a reminder on your last work afternoon before you go
  (3pm), until you tick it off;
- **away mode**: the card's button runs your SirisAI away protocol.

The card shows on Home from a week before until you're back. Kept in
trips.json (SIRISOS_TRIPS_PATH).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any

import httpx

from app.hub.service import shared_client
from app.services import json_store

GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"
FORECAST_DAYS = 16
SHOW_FROM_DAYS = 7
OOO_HOUR = 15
HOME_COUNTRY = "AU"

# Open-Meteo's weather codes, in words.
CODES = {0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Cloudy", 45: "Fog", 48: "Fog", 51: "Drizzle", 53: "Drizzle", 55: "Drizzle",
         61: "Rain", 63: "Rain", 65: "Heavy rain", 71: "Snow", 73: "Snow", 75: "Heavy snow", 80: "Showers", 81: "Showers", 82: "Heavy showers",
         95: "Storms", 96: "Storms", 99: "Storms"}


def _path():
    return json_store.data_path("SIRISOS_TRIPS_PATH", "trips.json")


def load() -> list[dict[str, Any]]:
    return list((json_store.read(_path(), {}) or {}).get("trips") or [])


def save(trips: list[dict[str, Any]]) -> None:
    json_store.write(_path(), {"trips": sorted(trips, key=lambda t: t["start"])[-50:]})


def find(trip_id: str) -> dict[str, Any] | None:
    return next((t for t in load() if t["id"] == trip_id), None)


async def geocode(place: str) -> dict[str, Any] | None:
    try:
        r = await shared_client().get(GEOCODE, params={"name": place, "count": 1, "language": "en", "format": "json"}, timeout=10.0)
        found = (r.json().get("results") or [None])[0] if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        return None
    if not found:
        return None
    return {"name": ", ".join(x for x in (found.get("name"), found.get("admin1"), found.get("country")) if x),
            "lat": found["latitude"], "lon": found["longitude"], "country": found.get("country_code") or ""}


async def weather(trip: dict[str, Any], today: date) -> dict[str, Any]:
    """The forecast for the trip's days that are within reach (16 days)."""
    if trip.get("lat") is None:
        return {"days": [], "note": "Couldn't find that place for the weather."}
    start = max(date.fromisoformat(trip["start"]), today)
    end = min(date.fromisoformat(trip["end"]), today + timedelta(days=FORECAST_DAYS - 1))
    if start > end:
        reach = date.fromisoformat(trip["start"]) - timedelta(days=FORECAST_DAYS - 1)
        return {"days": [], "note": f"The forecast reaches it from {reach:%a %d %b}."}
    try:
        r = await shared_client().get(FORECAST, params={
            "latitude": trip["lat"], "longitude": trip["lon"], "timezone": "auto", "start_date": start.isoformat(), "end_date": end.isoformat(),
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max"}, timeout=10.0)
        daily = r.json().get("daily") or {} if r.status_code == 200 else {}
    except (httpx.HTTPError, ValueError):
        return {"days": [], "note": "The forecast isn't available right now."}
    days = []
    for i, d in enumerate(daily.get("time") or []):
        def at(key: str) -> Any:
            vals = daily.get(key) or []
            return vals[i] if i < len(vals) else None
        days.append({"date": d, "conditions": CODES.get(at("weather_code"), ""), "high_c": at("temperature_2m_max"),
                     "low_c": at("temperature_2m_min"), "rain_chance": at("precipitation_probability_max"), "uv": at("uv_index_max")})
    return {"days": days, "note": None}


def packing(trip: dict[str, Any], wx: list[dict[str, Any]]) -> list[str]:
    nights = max(1, (date.fromisoformat(trip["end"]) - date.fromisoformat(trip["start"])).days)
    sets = min(nights + 1, 7)
    items = [f"{sets} sets of clothes", f"{sets} pairs of underwear and socks", "Sleepwear", "Toiletries", "Toothbrush and toothpaste",
             "Medications", "Phone charger", "Wallet and cards", "Keys"]
    if nights >= 5:
        items.append("Laundry bag")
    highs = [d["high_c"] for d in wx if d.get("high_c") is not None]
    lows = [d["low_c"] for d in wx if d.get("low_c") is not None]
    if any((d.get("rain_chance") or 0) >= 40 for d in wx):
        items += ["Rain jacket", "Umbrella"]
    if lows and min(lows) < 10:
        items += ["Warm jacket", "Jumper"]
    if highs and max(highs) >= 27:
        items += ["Shorts", "Swimwear"]
    if any((d.get("uv") or 0) >= 6 for d in wx) or (highs and max(highs) >= 27):
        items += ["Sunscreen", "Hat", "Sunglasses"]
    if trip.get("country") and trip["country"] != HOME_COUNTRY:
        items += ["Passport", "Travel insurance details", "Power adaptor", "Travel card or some local currency"]
    return items


def _last_workday(before: date) -> date:
    d = before - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


async def add(destination: str, start: date, end: date, notes: str = "") -> dict[str, Any]:
    if end < start:
        raise ValueError("The trip ends before it starts.")
    if (end - start).days > 120:
        raise ValueError("That's a long trip: 120 days at most.")
    place = await geocode(destination)
    trip = {"id": uuid.uuid4().hex[:10], "destination": destination.strip()[:80], "place": place["name"] if place else None,
            "lat": place["lat"] if place else None, "lon": place["lon"] if place else None, "country": place["country"] if place else "",
            "start": start.isoformat(), "end": end.isoformat(), "notes": notes.strip()[:500], "ooo_done": False, "packing": []}
    wx = (await weather(trip, date.today()))["days"]  # noqa: DTZ011 (only for the list's first guess)
    trip["packing"] = [{"item": i, "done": False} for i in packing(trip, wx)]
    trips = load()
    trips.append(trip)
    save(trips)
    return trip


def change(trip_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    trips = load()
    trip = next((t for t in trips if t["id"] == trip_id), None)
    if trip is None:
        return None
    if "packing" in fields and fields["packing"] is not None:
        trip["packing"] = [{"item": str(p["item"]).strip()[:80], "done": bool(p.get("done"))} for p in fields["packing"] if str(p.get("item", "")).strip()][:80]
    if fields.get("ooo_done") is not None:
        trip["ooo_done"] = bool(fields["ooo_done"])
    if fields.get("notes") is not None:
        trip["notes"] = str(fields["notes"]).strip()[:500]
    save(trips)
    return trip


def remove(trip_id: str) -> bool:
    trips = load()
    kept = [t for t in trips if t["id"] != trip_id]
    save(kept)
    return len(kept) < len(trips)


def bills_during(trip: dict[str, Any]) -> list[dict[str, Any]]:
    """Recurring charges and renewals that fall due while you're away."""
    start, end = trip["start"], trip["end"]
    out: list[dict[str, Any]] = []
    try:
        from app.budget import forecast

        for r in forecast.recurring():
            if r["status"] in ("ignore", "cancelling"):
                continue
            nxt = date.fromisoformat(r["next"])
            while nxt.isoformat() <= end:
                if nxt.isoformat() >= start:
                    out.append({"date": nxt.isoformat(), "name": r["name"], "amount": r["amount"], "kind": "charge"})
                nxt += timedelta(days=r["days"])
    except Exception:  # noqa: BLE001 - the card works without the bank imports
        pass
    try:
        from app.renewals import service as renewals

        for r in renewals.listing():
            due = str(r.get("expires") or "")[:10]
            if due and start <= due <= end:
                out.append({"date": due, "name": f"{r.get('name') or 'Renewal'} renewal", "amount": None, "kind": "renewal"})
    except Exception:  # noqa: BLE001
        pass
    return sorted(out, key=lambda b: b["date"])


def ooo_day(trip: dict[str, Any]) -> str:
    return _last_workday(date.fromisoformat(trip["start"])).isoformat()


async def view(trip: dict[str, Any], today: date) -> dict[str, Any]:
    wx = await weather(trip, today)
    start, end = date.fromisoformat(trip["start"]), date.fromisoformat(trip["end"])
    return {**trip, "days_to_go": (start - today).days, "nights": (end - start).days, "away": start <= today <= end,
            "weather": wx, "bills": bills_during(trip), "ooo_day": ooo_day(trip),
            "packed": sum(1 for p in trip["packing"] if p["done"]), "to_pack": len(trip["packing"])}


def current(today: date) -> dict[str, Any] | None:
    """The trip for Home: from a week before it starts until it ends."""
    for t in load():
        start, end = date.fromisoformat(t["start"]), date.fromisoformat(t["end"])
        if start - timedelta(days=SHOW_FROM_DAYS) <= today <= end:
            return t
    return None


def push_message(local_now: datetime) -> list[dict[str, Any]]:
    """The out-of-office reminder, at 3pm on your last workday before a trip, until it's ticked off."""
    out = []
    for t in load():
        if t.get("ooo_done") or local_now.date().isoformat() != ooo_day(t) or local_now.hour < OOO_HOUR:
            continue
        out.append({"key": f"travel:ooo:{t['id']}", "topic": "brief", "title": "Set your out-of-office",
                    "body": f"You're off to {t['destination']} from {date.fromisoformat(t['start']):%a %d %b}. "
                            "Set your email's automatic reply and calendar before you finish today.",
                    "url": "/travel", "urgency": "normal"})
    return out
