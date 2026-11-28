"""The weather on each walk (12.4).

For every walk, Open-Meteo's hourly weather where it started, over the hours it took: temperature (and how it felt),
rain, wind and gusts, humidity, and the sky. Older walks come from Open-Meteo's historical archive (ERA5), recent
ones from its forecast service's past days, because the archive runs about a week behind. Nothing is sent but a
rounded start point and the dates. SIRISOS_TRAILS_WEATHER=off turns it off (it follows SIRISOS_TRAILS_PLACES when unset).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ARCHIVE = os.getenv("SIRISOS_TRAILS_WEATHER_ARCHIVE", "https://archive-api.open-meteo.com/v1/archive")
RECENT = os.getenv("SIRISOS_TRAILS_WEATHER_RECENT", "https://api.open-meteo.com/v1/forecast")
RECENT_DAYS = 60  # the forecast service keeps about three months of past days; the archive is a few days behind
MAX_TRIES = 4
HOURLY = "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_gusts_10m,relative_humidity_2m"
# Open-Meteo's weather codes, in words and an emoji.
SKY = {0: ("Clear", "☀️"), 1: ("Mostly clear", "🌤️"), 2: ("Partly cloudy", "⛅"), 3: ("Cloudy", "☁️"), 45: ("Fog", "🌫️"), 48: ("Fog", "🌫️"),
       51: ("Drizzle", "🌦️"), 53: ("Drizzle", "🌦️"), 55: ("Drizzle", "🌦️"), 56: ("Freezing drizzle", "🌧️"), 57: ("Freezing drizzle", "🌧️"),
       61: ("Rain", "🌧️"), 63: ("Rain", "🌧️"), 65: ("Heavy rain", "🌧️"), 66: ("Freezing rain", "🌧️"), 67: ("Freezing rain", "🌧️"),
       71: ("Snow", "🌨️"), 73: ("Snow", "🌨️"), 75: ("Heavy snow", "❄️"), 77: ("Snow grains", "🌨️"),
       80: ("Showers", "🌦️"), 81: ("Showers", "🌦️"), 82: ("Heavy showers", "🌧️"), 85: ("Snow showers", "🌨️"), 86: ("Snow showers", "🌨️"),
       95: ("Storms", "⛈️"), 96: ("Storms", "⛈️"), 99: ("Storms", "⛈️")}


def enabled() -> bool:
    value = os.getenv("SIRISOS_TRAILS_WEATHER") or os.getenv("SIRISOS_TRAILS_PLACES", "on")
    return value.lower() not in ("off", "0", "false")


def _hours(walk: dict[str, Any]) -> tuple[datetime, datetime]:
    start = datetime.fromisoformat(walk["start"]).astimezone(timezone.utc)
    end = datetime.fromisoformat(walk["end"]).astimezone(timezone.utc) if walk.get("end") else start + timedelta(minutes=walk.get("minutes") or 60)
    return start, max(end, start)


def summarise(hourly: dict[str, list[Any]], start: datetime, end: datetime) -> dict[str, Any] | None:
    """The hours the walk took (the hour it started in to the hour it finished in) from Open-Meteo's hourly answer."""
    times = hourly.get("time") or []
    first = start.replace(minute=0, second=0, microsecond=0)
    keep = [i for i, t in enumerate(times) if first <= datetime.fromisoformat(t).replace(tzinfo=timezone.utc) <= end]
    if not keep:
        return None

    def col(key: str) -> list[float]:
        values = hourly.get(key) or []
        return [values[i] for i in keep if i < len(values) and values[i] is not None]

    temp, feels, rain, wind, gust, hum, codes = (col(k) for k in ("temperature_2m", "apparent_temperature", "precipitation",
                                                                  "wind_speed_10m", "wind_gusts_10m", "relative_humidity_2m", "weather_code"))
    if not temp:
        return None
    # The sky: the worst that happened if it rained or snowed, else the most common.
    wet = [int(c) for c in codes if int(c) >= 51]
    code = max(wet) if wet else (max(set(int(c) for c in codes), key=lambda c: [int(x) for x in codes].count(c)) if codes else None)
    words, icon = SKY.get(code, ("", "")) if code is not None else ("", "")
    avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else None  # noqa: E731
    return {"temp_c": avg(temp), "temp_min_c": round(min(temp), 1), "temp_max_c": round(max(temp), 1), "feels_c": avg(feels),
            "rain_mm": round(sum(rain), 1) if rain else None, "wind_kmh": avg(wind), "gust_kmh": round(max(gust)) if gust else None,
            "humidity": round(sum(hum) / len(hum)) if hum else None, "code": code, "sky": words, "icon": icon}


def fetch(client: httpx.Client, walk: dict[str, Any], now: datetime | None = None) -> dict[str, Any] | None:
    start, end = _hours(walk)
    now = now or datetime.now(timezone.utc)
    lat, lon = (round(v, 2) for v in walk["start_point"])
    url = RECENT if (now - start).days < RECENT_DAYS else ARCHIVE
    r = client.get(url, params={"latitude": lat, "longitude": lon, "start_date": start.date().isoformat(), "end_date": end.date().isoformat(),
                                "hourly": HOURLY, "timezone": "GMT", "wind_speed_unit": "kmh"})
    r.raise_for_status()
    return summarise((r.json() or {}).get("hourly") or {}, start, end)


def fill_pending(limit: int = 60, now: datetime | None = None) -> int:
    """Look up the weather for walks that don't have it yet (recent ones wait until the day's weather is in)."""
    from app.trails import service

    if not enabled():
        return 0
    now = now or datetime.now(timezone.utc)
    todo = [w for w in service.load()["walks"] if "weather" not in w and (w.get("weather_retry") or 0) < MAX_TRIES and w.get("start_point")
            and _hours(w)[1] < now - timedelta(hours=2)][:limit]
    done = 0
    with httpx.Client(timeout=20, headers={"User-Agent": "SirisOS-SirisTrails/12 (self-hosted personal walk log)"}) as client:
        for walk in todo:
            try:
                got = fetch(client, walk, now)
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                logger.info("Weather for walk %s failed: %s", walk["id"], exc)
                service.set_fields(walk["id"], weather_retry=(walk.get("weather_retry") or 0) + 1)
                continue
            if got is None:
                service.set_fields(walk["id"], weather_retry=(walk.get("weather_retry") or 0) + 1)
                continue
            service.set_fields(walk["id"], weather=got)
            done += 1
    return done
