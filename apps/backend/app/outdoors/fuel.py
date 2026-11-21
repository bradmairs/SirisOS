"""Fuel on the way to Shepparton (10.4): on Wednesday mornings, before the 6am drive to the GVW secondment, the
cheapest Unleaded 91 within the first 30 km of the route.

- **Prices**: Service Victoria's Fair Fuel Open Data API (free, sign up for a key: SIRISOS_FAIR_FUEL_KEY). Its
  prices are about 24 hours old, so it says "yesterday's price".
- **The route**: driving directions from home (SirisAI's weather location, or the one set here) to Shepparton,
  from the public OSRM router, worked out once and kept. Only servos within 1.5 km of the first 30 km count.
- **When**: on Home from 6pm the evening before until 9am, and a notification at 5:30am on the day.

Settings in fuel.json (SIRISOS_FUEL_PATH): the day and time you leave, fuel type, destination, how far in, how
far off the road, and home if not SirisAI's. Stations are kept for a week and prices for three hours.
"""

from __future__ import annotations

import math
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from app.hub.service import Hub, shared_client
from app.outdoors import weather
from app.services import json_store

API = "https://api.fuel.service.vic.gov.au/open-data/v1"
OSRM = "https://router.project-osrm.org/route/v1/driving"
FUEL_TYPES = ("U91", "E10", "P95", "P98", "DSL", "LPG")
DEFAULTS = {"on": True, "weekday": 2, "leave": "06:00", "fuel_type": "U91", "first_km": 30.0, "off_route_km": 1.5,
            "destination": {"name": "Shepparton", "lat": -36.3806, "lon": 145.3989}, "home": None}
STATIONS_DAYS = 7
PRICES_HOURS = 3


class FuelError(Exception):
    pass


def key() -> str:
    return os.getenv("SIRISOS_FAIR_FUEL_KEY", "").strip()


def _path():
    return json_store.data_path("SIRISOS_FUEL_PATH", "fuel.json")


def _cache_path():
    return json_store.data_path("SIRISOS_FUEL_CACHE_PATH", "fuel-cache.json")


def settings() -> dict[str, Any]:
    doc = json_store.read(_path(), {}) or {}
    return {**DEFAULTS, **{k: v for k, v in doc.items() if k in DEFAULTS}}


def save_settings(changes: dict[str, Any]) -> dict[str, Any]:
    s = settings()
    for k, v in changes.items():
        if k not in DEFAULTS or v is None:
            continue
        if k == "fuel_type" and v not in FUEL_TYPES:
            raise ValueError(f"Fuel type is one of {', '.join(FUEL_TYPES)}.")
        if k == "weekday" and not (isinstance(v, int) and 0 <= v <= 6):
            raise ValueError("The day is 0 (Monday) to 6 (Sunday).")
        s[k] = v
    json_store.write(_path(), s)
    cache = json_store.read(_cache_path(), {}) or {}
    cache.pop("route", None)  # the route is worked out again for a new home or destination
    json_store.write(_cache_path(), cache)
    return s


# -- geometry ---------------------------------------------------------------------------------------------------

def km_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def first_part(path: list[tuple[float, float]], km: float) -> list[tuple[float, float, float]]:
    """The path's points (lat, lon, km from the start) up to `km` along it."""
    out = [(path[0][0], path[0][1], 0.0)]
    done = 0.0
    for a, b in zip(path, path[1:], strict=False):
        step = km_between(a, b)
        if done + step > km:
            f = (km - done) / step if step else 0
            out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, km))
            break
        done += step
        out.append((b[0], b[1], done))
    return out


def off_route(p: tuple[float, float], part: list[tuple[float, float, float]]) -> tuple[float, float]:
    """(km from the road, km along it to the nearest point), on a flat projection (fine at this scale)."""
    best = (math.inf, 0.0)
    kx = 111.32 * math.cos(math.radians(p[0]))
    for a, b in zip(part, part[1:], strict=False):
        ax, ay, bx, by = (a[1] - p[1]) * kx, (a[0] - p[0]) * 110.57, (b[1] - p[1]) * kx, (b[0] - p[0]) * 110.57
        dx, dy = bx - ax, by - ay
        seg = dx * dx + dy * dy
        t = max(0.0, min(1.0, -(ax * dx + ay * dy) / seg)) if seg else 0.0
        d = math.hypot(ax + t * dx, ay + t * dy)
        if d < best[0]:
            best = (d, a[2] + (b[2] - a[2]) * t)
    return best


# -- sources -----------------------------------------------------------------------------------------------------

def _headers() -> dict[str, str]:
    return {"x-consumer-id": key(), "x-transactionid": str(uuid.uuid4()), "User-Agent": "SirisOS/10.4", "Accept": "application/json"}


async def _get(url: str) -> Any:
    try:
        r = await shared_client().get(url, headers=_headers(), timeout=30.0)
    except httpx.HTTPError as exc:
        raise FuelError(f"Fair Fuel can't be reached ({type(exc).__name__}).") from exc
    if r.status_code in (401, 403):
        raise FuelError("Fair Fuel turned down the key (SIRISOS_FAIR_FUEL_KEY): check it in Service Victoria's Servo Saver API page.")
    if r.status_code >= 400:
        raise FuelError(f"Fair Fuel answered {r.status_code}.")
    return r.json()


def _num(*vals: Any) -> float | None:
    for v in vals:
        try:
            if v is not None and v != "":
                return float(v)
        except (TypeError, ValueError):
            continue
    return None


def parse_station(s: dict[str, Any]) -> dict[str, Any] | None:
    """A station from the reference data, reading the location wherever it is (the API's names aren't documented here)."""
    loc = s.get("location") if isinstance(s.get("location"), dict) else {}
    addr = s.get("address")
    addr_text = addr if isinstance(addr, str) else ", ".join(str(addr.get(k)) for k in ("streetAddress", "address", "suburb", "locality", "postcode")
                                                             if isinstance(addr, dict) and addr.get(k)) if isinstance(addr, dict) else ""
    lat = _num(loc.get("latitude"), loc.get("lat"), s.get("latitude"), s.get("lat"), (addr or {}).get("latitude") if isinstance(addr, dict) else None)
    lon = _num(loc.get("longitude"), loc.get("lng"), loc.get("lon"), s.get("longitude"), s.get("lng"), s.get("lon"),
               (addr or {}).get("longitude") if isinstance(addr, dict) else None)
    sid = s.get("id") or s.get("stationId")
    if sid is None or lat is None or lon is None:
        return None
    return {"id": str(sid), "name": str(s.get("name") or s.get("stationName") or "Servo"), "brand": s.get("brandId") or s.get("brand"),
            "address": addr_text[:120], "lat": lat, "lon": lon}


async def stations(force: bool = False) -> list[dict[str, Any]]:
    cache = json_store.read(_cache_path(), {}) or {}
    st = cache.get("stations") or {}
    if not force and st.get("at") and datetime.now(timezone.utc) - datetime.fromisoformat(st["at"]) < timedelta(days=STATIONS_DAYS):
        return st["items"]
    body = await _get(f"{API}/fuel/reference-data/stations")
    raw = body.get("fuelStations") if isinstance(body, dict) else body
    items = [p for p in (parse_station(s) for s in raw or [] if isinstance(s, dict)) if p]
    brands: dict[str, str] = {}
    try:
        b = await _get(f"{API}/fuel/reference-data/brands")
        for x in (b.get("brands") or b.get("fuelBrands") or []) if isinstance(b, dict) else b or []:
            if isinstance(x, dict) and x.get("id") is not None:
                brands[str(x["id"])] = str(x.get("name") or "")
    except FuelError:
        pass
    for i in items:
        if i["brand"] is not None and str(i["brand"]) in brands:
            i["brand"] = brands[str(i["brand"])]
    cache["stations"] = {"at": datetime.now(timezone.utc).isoformat(), "items": items}
    json_store.write(_cache_path(), cache)
    return items


async def prices(fuel_type: str) -> dict[str, dict[str, Any]]:
    cache = json_store.read(_cache_path(), {}) or {}
    pr = cache.get("prices") or {}
    if not (pr.get("at") and datetime.now(timezone.utc) - datetime.fromisoformat(pr["at"]) < timedelta(hours=PRICES_HOURS)):
        body = await _get(f"{API}/fuel/prices")
        pr = {"at": datetime.now(timezone.utc).isoformat(), "items": body.get("fuelPriceDetails") or [] if isinstance(body, dict) else []}
        cache["prices"] = pr
        json_store.write(_cache_path(), cache)
    out: dict[str, dict[str, Any]] = {}
    for d in pr["items"]:
        st = d.get("fuelStation") or {}
        for p in d.get("fuelPrices") or []:
            if p.get("fuelType") == fuel_type and p.get("price") is not None and p.get("isAvailable", True):
                out[str(st.get("id"))] = {"price": float(p["price"]), "updated": p.get("updatedAt")}
    return out


async def route(home: tuple[float, float], dest: tuple[float, float]) -> list[tuple[float, float]]:
    cache = json_store.read(_cache_path(), {}) or {}
    key_ = f"{home[0]:.4f},{home[1]:.4f}>{dest[0]:.4f},{dest[1]:.4f}"
    if (cache.get("route") or {}).get("key") == key_:
        return [tuple(p) for p in cache["route"]["path"]]  # type: ignore[misc]
    url = f"{OSRM}/{home[1]},{home[0]};{dest[1]},{dest[0]}"
    try:
        r = await shared_client().get(url, params={"overview": "full", "geometries": "geojson"}, timeout=30.0)
        coords = r.json()["routes"][0]["geometry"]["coordinates"] if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError, KeyError, IndexError):
        coords = None
    if not coords:
        raise FuelError("Couldn't work out the drive (the OSRM router didn't answer).")
    path = [(c[1], c[0]) for c in coords]
    cache["route"] = {"key": key_, "path": path}
    json_store.write(_cache_path(), cache)
    return path


async def home_point(hub: Hub, s: dict[str, Any]) -> tuple[float, float] | None:
    if s.get("home") and s["home"].get("lat") is not None:
        return float(s["home"]["lat"]), float(s["home"]["lon"])
    wx = await weather.hourly(hub, days=1)
    if wx and wx.get("latitude") is not None:
        return float(wx["latitude"]), float(wx["longitude"])
    return None


async def suggest(hub: Hub) -> dict[str, Any]:
    s = settings()
    base = {"settings": s, "configured": bool(key()), "attribution": "© State of Victoria accessed via the Victorian Government Service Victoria Platform"}
    if not key():
        return {**base, "why": "Add a Fair Fuel key (SIRISOS_FAIR_FUEL_KEY): sign up free at Service Victoria (Servo Saver public API)."}
    home = await home_point(hub, s)
    if home is None:
        return {**base, "why": "Where's home? Set it here, or SirisAI's weather location."}
    try:
        path = await route(home, (s["destination"]["lat"], s["destination"]["lon"]))
        part = first_part(path, float(s["first_km"]))
        found = []
        price = await prices(s["fuel_type"])
        for st in await stations():
            if st["id"] not in price:
                continue
            off, along = off_route((st["lat"], st["lon"]), part)
            if off <= float(s["off_route_km"]):
                found.append({**st, **price[st["id"]], "off_km": round(off, 1), "km_in": round(along, 1),
                              "maps": f"https://maps.apple.com/?daddr={st['lat']},{st['lon']}"})
    except FuelError as exc:
        return {**base, "why": str(exc)}
    found.sort(key=lambda x: (x["price"], x["km_in"]))
    if not found:
        return {**base, "options": [], "why": f"No {s['fuel_type']} prices within {s['first_km']:g} km of the drive."}
    avg = sum(x["price"] for x in found) / len(found)
    best = found[0]
    return {**base, "best": best, "options": found[:5], "average": round(avg, 1), "saving_cents": round(avg - best["price"], 1),
            "route_km": round(part[-1][2], 1), "note": "Prices are about a day old (Fair Fuel's open data)."}


def due(local_now: datetime, s: dict[str, Any]) -> date | None:
    """The drive this card or notification is for: tomorrow's from 6pm, today's until 9am."""
    if not s["on"]:
        return None
    if local_now.weekday() == s["weekday"] and local_now.hour < 9:
        return local_now.date()
    if (local_now.weekday() + 1) % 7 == s["weekday"] and local_now.hour >= 18:
        return local_now.date() + timedelta(days=1)
    return None


async def push_message(hub: Hub, local_now: datetime) -> list[dict[str, Any]]:
    s = settings()
    if not s["on"] or local_now.weekday() != s["weekday"] or not key():
        return []
    h, m = (int(x) for x in s["leave"].split(":"))
    at = local_now.replace(hour=h, minute=m) - timedelta(minutes=30)
    if not (at <= local_now < at + timedelta(hours=2)):
        return []
    from app.push import store

    if f"fuel:{local_now.date().isoformat()}" in store.sent():
        return []
    sug = await suggest(hub)
    best = sug.get("best")
    if not best:
        return []
    saving = f", {sug['saving_cents']:.1f}¢ under the average on the way" if sug.get("saving_cents") else ""
    return [{"key": f"fuel:{local_now.date().isoformat()}", "topic": "brief", "title": f"Fuel on the way: {best['name']}",
             "body": f"{s['fuel_type']} {best['price']:.1f}¢, {best['km_in']:g} km in{saving}. Yesterday's prices.", "url": "/", "urgency": "normal"}]
