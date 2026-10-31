"""Power use (5.4): what the house is drawing now, room by room, and how
many kWh a day, for the house view and Your year.

SirisAI 3.11's /siris/hub/v1/energy/usage lists every Home Assistant power
sensor (watts now) and energy meter (a kWh total that only goes up). Each
sensor goes in a room in the house the way devices do: by its name, or
where you put it (the house's placements, by entity id).

A day's kWh, sampled every 10 minutes, comes from the best source there is:
1. the house's own meter (SIRISAI_ENERGY_METER_ENTITY_ID): today's last
   reading less today's first;
2. otherwise every meter added up the same way;
3. otherwise the house's power (SIRISAI_ENERGY_GRID_ENTITY_ID), or all the
   power sensors added up, times the time between samples.
A meter that goes backwards (replaced or reset) starts the day again from
its new reading rather than counting negative energy.

**By device** (6.2): each meter's kWh for the day (house meter aside), and
each power sensor's watts added up over time, so the day's biggest users
can be listed. **Always on**: between 1am and 5am, the lowest the house
drew (its power, or the sensors added up) and each sensor still drawing
over ALWAYS_ON_WATTS (15 W), so what's never off shows, with its cost over
a year.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import date
from typing import Any

from app.hub import sirisai_api
from app.hub.service import Hub
from app.services import json_store

logger = logging.getLogger(__name__)
SAMPLE_SECONDS = 600
MAX_GAP_SECONDS = 1800  # longer than this between samples: don't guess the power in between
KEEP_DAYS = 800
ALWAYS_ON_WATTS = 15.0
NIGHT_HOURS = range(1, 5)


def _path():
    return json_store.data_path("SIRISOS_POWER_PATH", "power.json")


def load() -> dict[str, Any]:
    doc = json_store.read(_path(), {})
    doc = doc if isinstance(doc, dict) else {}
    doc.setdefault("days", {})
    return doc


def save(doc: dict[str, Any]) -> None:
    days = doc["days"]
    if len(days) > KEEP_DAYS:
        doc["days"] = dict(sorted(days.items())[-KEEP_DAYS:])
    json_store.write(_path(), doc)


async def usage(hub: Hub) -> dict[str, Any] | None:
    return await sirisai_api.get(hub, "/siris/hub/v1/energy/usage")


def _meter_kwh(day: dict[str, Any], readings: dict[str, float]) -> float:
    """Update the day's first/last readings per meter and return the day's total."""
    first = day.setdefault("first", {})
    last = day.setdefault("last", {})
    used = day.setdefault("used", {})
    for eid, kwh in readings.items():
        if eid not in first:
            first[eid] = kwh
        elif kwh < last.get(eid, kwh):  # reset or replaced: carry on from here
            used[eid] = used.get(eid, 0.0) + (last[eid] - first[eid])
            first[eid] = kwh
        last[eid] = kwh
    return sum(used.get(e, 0.0) + last[e] - first[e] for e in last)


def _by_device(day: dict[str, Any], u: dict[str, Any], now: float, hour: int | None) -> None:
    names = day.setdefault("names", {})
    devices = day.setdefault("devices", {})
    house = u.get("house_meter")
    meters = {m["entity_id"]: float(m["kwh"]) for m in u.get("meters") or [] if m.get("entity_id") and m["entity_id"] != house}
    track = day.setdefault("meter_devices", {})
    _meter_kwh(track, meters)
    for m in u.get("meters") or []:
        eid = m.get("entity_id")
        if eid in meters:
            names[eid] = m.get("name") or eid
            devices[eid] = round(track["used"].get(eid, 0.0) + track["last"][eid] - track["first"][eid], 3)
    metered = {m.get("name") for m in u.get("meters") or []}
    prev_at, prev = day.get("device_at"), day.get("device_watts") or {}
    watts = {p["entity_id"]: float(p.get("watts") or 0) for p in u.get("power") or [] if p.get("entity_id")}
    for p in u.get("power") or []:
        eid = p.get("entity_id")
        if not eid or p.get("name") in metered:
            continue  # its meter already counts it
        names[eid] = p.get("name") or eid
        if prev_at is not None and 0 < now - prev_at <= MAX_GAP_SECONDS and eid in prev:
            devices[eid] = round(float(devices.get(eid, 0.0)) + (prev[eid] + watts[eid]) / 2 * (now - prev_at) / 3_600_000, 3)
    day["device_at"], day["device_watts"] = now, watts
    if hour is not None and hour in NIGHT_HOURS:
        total = u.get("house_watts")
        if total is None and watts:
            total = sum(watts.values())
        if total is not None:
            day["night_min"] = round(min(float(day.get("night_min", total)), float(total)), 1)
        night = day.setdefault("night_devices", {})
        for eid, w in watts.items():
            night[eid] = round(min(float(night.get(eid, w)), w), 1)


def record(doc: dict[str, Any], u: dict[str, Any], today: date, now: float, hour: int | None = None) -> dict[str, Any]:
    """Fold one sample into the day's figure. Pure apart from `doc`, for testing.
    `hour` is the local hour, for the overnight always-on figures."""
    day = doc["days"].setdefault(today.isoformat(), {})
    meters = {m["entity_id"]: float(m["kwh"]) for m in u.get("meters") or [] if m.get("entity_id")}
    house = u.get("house_meter")
    if house and house in meters:
        day["method"] = "house meter"
        day["kwh"] = round(_meter_kwh(day, {house: meters[house]}), 3)
    elif meters:
        day["method"] = "meters"
        day["kwh"] = round(_meter_kwh(day, meters), 3)
    else:
        watts = u.get("house_watts")
        if watts is None:
            watts = sum(float(p.get("watts") or 0) for p in u.get("power") or [])
        last = day.get("at")
        if last is not None and 0 < now - last <= MAX_GAP_SECONDS:
            prev = float(day.get("watts") or watts)
            day["kwh"] = round(float(day.get("kwh") or 0) + (prev + watts) / 2 * (now - last) / 3_600_000, 3)
        day.setdefault("kwh", 0.0)
        day["method"] = "power"
        day["watts"] = watts
    _by_device(day, u, now, hour)
    day["at"] = now
    return day


def top_devices(day: dict[str, Any], n: int = 8) -> list[dict[str, Any]]:
    """The day's biggest users, with their share of what's counted."""
    devices = {e: k for e, k in (day.get("devices") or {}).items() if k > 0}
    total = float(day.get("kwh") or 0) or sum(devices.values())
    names = day.get("names") or {}
    return [{"entity_id": e, "name": names.get(e, e), "kwh": round(k, 2), "share": round(k / total * 100) if total else None}
            for e, k in sorted(devices.items(), key=lambda x: -x[1])[:n]]


def always_on(days: dict[str, dict[str, Any]], today: date, tariff: float | None = None) -> dict[str, Any] | None:
    """The overnight floor, from the last night measured (today's, else yesterday's)."""
    for iso in (today.isoformat(), date.fromordinal(today.toordinal() - 1).isoformat()):
        d = days.get(iso) or {}
        if d.get("night_min") is None:
            continue
        watts = float(d["night_min"])
        kwh_year = round(watts * 24 * 365 / 1000)
        names = d.get("names") or {}
        devices = sorted(({"entity_id": e, "name": names.get(e, e), "watts": w} for e, w in (d.get("night_devices") or {}).items()
                          if w >= ALWAYS_ON_WATTS), key=lambda x: -x["watts"])
        return {"date": iso, "watts": watts, "kwh_year": kwh_year, "cost_year": round(kwh_year * tariff) if tariff else None, "devices": devices[:8]}
    return None


def tariff() -> float | None:
    try:
        return float(os.getenv("SIRISOS_POWER_TARIFF", "") or 0) or None
    except ValueError:
        return None


def by_month() -> dict[str, float]:
    out: dict[str, float] = {}
    for iso, d in load()["days"].items():
        if d.get("kwh") is not None:
            out[iso[:7]] = out.get(iso[:7], 0.0) + float(d["kwh"])
    return {m: round(v, 1) for m, v in out.items()}


def today_kwh(today: date) -> float | None:
    d = load()["days"].get(today.isoformat())
    return float(d["kwh"]) if d and d.get("kwh") is not None else None


def enabled() -> bool:
    return os.getenv("SIRISOS_POWER_LOG", "1") not in ("0", "false", "no")


async def loop(get_hub) -> None:
    from app.tasks import service as tasks

    while True:
        try:
            u = await usage(get_hub())
            if u and u.get("configured") and (u.get("meters") or u.get("power") or u.get("house_watts") is not None):
                doc = load()
                from datetime import datetime

                from app.brief.service import zone

                record(doc, u, tasks.today(), time.time(), datetime.now(zone()).hour)
                save(doc)
                from app.maintenance import service as maintenance

                maintenance.sample_usage(u, time.time())  # jobs that come due by use (6.2)
        except Exception as exc:  # noqa: BLE001 - keep sampling
            logger.info("Power sample failed: %s", exc)
        await asyncio.sleep(SAMPLE_SECONDS)


