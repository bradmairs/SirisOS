"""Names for walks from where they went (12.1).

Apple Health keeps no name for a walk, so SirisTrails names each one from OpenStreetMap:

- **Hikes**: the named peak within PEAK_M of the walk's highest point ("Mt Arthur"), else the named track the route
  follows for at least TRAIL_SHARE of its length ("Abel Tasman Coast Track"), else the park or reserve most of it is in.
- **Walks**: the named track it follows, else the park or reserve, else the suburb or town, as "<place> loop" when it
  ends where it started and "<place> walk" otherwise.

The place line under the name ("Kaiapoi, Canterbury, New Zealand") comes from Nominatim. Lookups use OpenStreetMap's
public Overpass and Nominatim services, one request a second at most as their usage policies ask, with a sample of
the route's points (never anything else). SIRISOS_TRAILS_PLACES=off turns it off. A walk you've renamed keeps your
name; its place line is still filled in.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
import threading
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# The main public Overpass server, then a mirror: they're often busy, so each is tried with a pause between.
OVERPASS = [u for u in os.getenv("SIRISOS_TRAILS_OVERPASS", "https://overpass-api.de/api/interpreter,https://overpass.kumi.systems/api/interpreter").split(",") if u]
MAX_TRIES = 4
PLACE_VERSION = 2  # 12.2.2: Japan's prefectures (address "province")  # runs that couldn't reach Overpass before a walk is left with its place-name fallback
NOMINATIM = os.getenv("SIRISOS_TRAILS_NOMINATIM", "https://nominatim.openstreetmap.org/reverse")
UA = "SirisOS-SirisTrails/12 (self-hosted personal walk log)"
PEAK_M = 250
TRAIL_M = 35
TRAIL_SHARE = 0.4
AREA_SHARE = 0.6
LOOP_M = 300
SAMPLES = 40
# A road isn't a walk's name ("Calwell Road" through Sugarloaf Reservoir Park); "Track", "Walk", "Trail" are.
ROADISH = re.compile(r"\b(road|rd|street|st|lane|ln|avenue|ave|drive|dr|highway|hwy|court|crescent|parade)\.?$", re.I)
_last_call = 0.0
_naming = threading.Lock()  # one naming run at a time (the 10-minute loop, or a kick when a walk arrives)


def enabled() -> bool:
    return os.getenv("SIRISOS_TRAILS_PLACES", "on").lower() not in ("off", "0", "false")


def _polite(client: httpx.Client, method: str, url: str, **kw: Any) -> httpx.Response:
    """One request a second to OpenStreetMap's services."""
    global _last_call
    wait = 1.1 - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()
    r = client.request(method, url, **kw)
    r.raise_for_status()
    return r


def _metres(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(min(1.0, math.sqrt(h)))


def _to_segment(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    """Metres from p to segment ab (flat-earth, fine at walking scale)."""
    kx = 111320 * math.cos(math.radians(p[0]))
    ax, ay, bx, by, px, py = a[1] * kx, a[0] * 110540, b[1] * kx, b[0] * 110540, p[1] * kx, p[0] * 110540
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def sample(points: list[list[float]], n: int = SAMPLES) -> list[tuple[float, float]]:
    step = max(1, len(points) // n)
    return [(p[0], p[1]) for p in points[::step]]


def _query(south: float, west: float, north: float, east: float) -> str:
    bbox = f"{south},{west},{north},{east}"
    return (f'[out:json][timeout:40];('
            f'relation["route"~"^(hiking|foot|walking)$"]["name"]({bbox});'
            f'way["highway"~"^(path|footway|track|bridleway|steps|pedestrian)$"]["name"]({bbox});'
            f'way["leisure"~"^(park|nature_reserve)$"]["name"]({bbox});relation["leisure"~"^(park|nature_reserve)$"]["name"]({bbox});'
            f'way["boundary"~"^(protected_area|national_park)$"]["name"]({bbox});relation["boundary"~"^(protected_area|national_park)$"]["name"]({bbox});'
            f'node["natural"~"^(peak|volcano|hill)$"]["name"]({bbox});'
            f');out tags geom qt;')


def choose(elements: list[dict[str, Any]], pts: list[tuple[float, float]], highest: tuple[float, float] | None, kind: str) -> dict[str, Any]:
    """From Overpass's answer: the best trail, park and peak for this route."""
    trails: dict[str, float] = {}
    areas: dict[str, tuple[float, float]] = {}  # name -> (share of points inside, bbox area)
    peak = None
    for el in elements:
        tags = el.get("tags") or {}
        name = tags.get("name:en") or tags.get("name")  # "Lion Rock", not "獅子山 Lion Rock"
        if not name:
            continue
        if el["type"] == "node":
            if highest:
                d = _metres(highest, (el["lat"], el["lon"]))
                if d <= PEAK_M and (peak is None or d < peak[1]):
                    peak = (name, d)
            continue
        is_area = tags.get("leisure") in ("park", "nature_reserve") or tags.get("boundary") in ("protected_area", "national_park")
        if is_area:
            b = el.get("bounds")
            if not b:
                continue
            inside = sum(b["minlat"] <= p[0] <= b["maxlat"] and b["minlon"] <= p[1] <= b["maxlon"] for p in pts) / len(pts)
            size = (b["maxlat"] - b["minlat"]) * (b["maxlon"] - b["minlon"])
            prev = areas.get(name)
            if prev is None or inside > prev[0] or (inside == prev[0] and size < prev[1]):
                areas[name] = (inside, size)
            continue
        if ROADISH.search(name.strip()) and not tags.get("route"):
            continue
        lines = [el["geometry"]] if el.get("geometry") else [m["geometry"] for m in el.get("members") or [] if m.get("geometry")]
        segs = [((a["lat"], a["lon"]), (b["lat"], b["lon"])) for line in lines for a, b in zip(line, line[1:])]
        if not segs:
            continue
        near = sum(any(_to_segment(p, a, b) <= TRAIL_M for a, b in segs) for p in pts) / len(pts)
        bonus = 0.15 if tags.get("route") else 0.0  # a signposted route beats one of its path sections
        trails[name] = max(trails.get(name, 0.0), near + bonus)
    trail = max(trails.items(), key=lambda x: x[1]) if trails else None
    good_areas = [(n, s) for n, s in areas.items() if s[0] >= AREA_SHARE]
    area = min(good_areas, key=lambda x: x[1][1])[0] if good_areas else None  # the smallest place that holds the walk
    return {"peak": peak[0] if peak else None, "trail": trail[0] if trail and trail[1] >= TRAIL_SHARE else None, "park": area}


def _place_line(addr: dict[str, Any]) -> tuple[str | None, str]:
    local = next((addr.get(k) for k in ("suburb", "village", "town", "hamlet", "city_district", "city", "municipality", "county") if addr.get(k)), None)
    region = addr.get("state") or addr.get("province") or addr.get("region") or addr.get("state_district")
    parts = [p for p in (local, region, addr.get("country")) if p]
    out: list[str] = []
    for p in parts:
        if p not in out:
            out.append(p)
    return local, ", ".join(out)


def where(client: httpx.Client, lat: float, lon: float) -> dict[str, Any]:
    """12.2: Nominatim's address for a point: locality, state or region, country (one fast request)."""
    r = _polite(client, "GET", NOMINATIM, params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 14, "addressdetails": 1})
    addr = (r.json() or {}).get("address") or {}
    local, place = _place_line(addr)
    return {"locality": local, "place": place or None,
            "region": addr.get("state") or addr.get("province") or addr.get("region") or addr.get("state_district"),  # Japan: province
            "country": addr.get("country"), "country_code": (addr.get("country_code") or "").upper() or None}


def peak_at(client: httpx.Client, lat: float, lon: float) -> str | None:
    """12.2: the named natural feature (peak, hill, rock) at a hike's high point, from Nominatim: fast, unlike Overpass."""
    r = _polite(client, "GET", NOMINATIM, params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 17, "layer": "natural", "namedetails": 1})
    got = r.json() or {}
    if got.get("category") != "natural" or got.get("type") not in ("peak", "hill", "volcano", "rock", "saddle", "cliff", "ridge"):
        return None
    try:
        if _metres((lat, lon), (float(got["lat"]), float(got["lon"]))) > PEAK_M:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    names = got.get("namedetails") or {}
    return names.get("name:en") or got.get("name") or None


def _name(kind: str, found: dict[str, Any], local: str | None, loop: bool) -> str | None:
    if kind == "hike":
        return found.get("peak") or found.get("trail") or found.get("park") or (f"{local} hike" if local else None)
    return found.get("trail") or found.get("park") or (f"{local} {'loop' if loop else 'walk'}" if local else None)


def describe(points: list[list[float]], kind: str, overpass: bool = True) -> dict[str, Any]:
    """{name, place, locality, region, country, country_code, peak, trail, park, loop}. Nominatim always (fast);
    Overpass's tracks and parks only when `overpass` (slow, often busy: one try, and a later run tries again)."""
    pts = sample(points)
    lats, lons = [p[0] for p in pts], [p[1] for p in pts]
    eles = [(p[2], (p[0], p[1])) for p in points if p[2] is not None]
    highest = max(eles)[1] if eles else None
    loop = _metres((points[0][0], points[0][1]), (points[-1][0], points[-1][1])) <= LOOP_M
    found: dict[str, Any] = {"peak": None, "trail": None, "park": None}
    with httpx.Client(timeout=30, headers={"User-Agent": UA, "Accept-Language": "en"}) as client:
        mid = (sum(lats) / len(lats), sum(lons) / len(lons))
        info = where(client, *mid)
        if kind == "hike" and highest:
            try:
                found["peak"] = peak_at(client, *highest)
            except (httpx.HTTPError, ValueError):
                pass
        if overpass:
            pad = 0.002
            query = _query(min(lats) - pad, min(lons) - pad, max(lats) + pad, max(lons) + pad)
            try:
                r = _polite(client, "POST", OVERPASS[0], data={"data": query}, timeout=45)
                got = choose(r.json().get("elements") or [], pts, highest, kind)
                found = {**got, "peak": got.get("peak") or found["peak"]}
                found["overpass_done"] = True
            except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
                logger.info("Overpass lookup failed: %s", exc)
                found["retry"] = True
    return {**found, **info, "name": _name(kind, found, info["locality"], loop), "loop": loop}


def _chain(*batches: Any):
    for batch in batches:
        yield from batch()


def name_pending(limit: int = 200, overpass_limit: int = 6) -> int:
    """First every walk without a place gets one from Nominatim (fast); then a few at a time get Overpass's tracks and
    parks (slow). Returns how many were looked up."""
    from app.trails import service

    if not enabled() or not _naming.acquire(blocking=False):
        return 0
    try:
        return _name_pending(limit, overpass_limit)
    finally:
        _naming.release()


def kick() -> None:
    """12.2.1: name new walks now, in the background, instead of at the next 10-minute run."""
    if enabled() and not _naming.locked():
        threading.Thread(target=name_pending, daemon=True, name="trails-naming").start()


def _name_pending(limit: int, overpass_limit: int) -> int:
    from app.trails import service

    done = 0

    def fast() -> list[tuple[dict[str, Any], bool]]:
        # PLACE_VERSION: walks placed by an older lookup (before Japan's prefectures were read) are placed again
        return [(w, False) for w in service.load()["walks"] if not w.get("country") or (not w.get("region") and (w.get("place_v") or 1) < PLACE_VERSION)][:limit]

    def slow() -> list[tuple[dict[str, Any], bool]]:  # chosen after the fast pass, so it sees the walks just placed
        todo = [w for w in service.load()["walks"] if w.get("country") and not w.get("overpass_done") and (w.get("names_retry") or 0) < MAX_TRIES]
        todo.sort(key=lambda w: w["kind"] != "hike")  # hikes first: tracks, parks and peaks matter most there
        return [(w, True) for w in todo][:overpass_limit]

    for walk, use_overpass in _chain(fast, slow):
        try:
            points = json.loads(service._route_path(walk["id"]).read_text(encoding="utf-8"))["points"]
            info = describe(points, walk["kind"], overpass=use_overpass)
        except Exception as exc:  # noqa: BLE001 - try again next time
            logger.info("Naming walk %s failed: %s", walk["id"], exc)
            continue
        if not use_overpass:  # keep what Overpass found before, if it had
            info = {**info, **{k: (walk.get("landmarks") or {}).get(k) or info.get(k) for k in ("trail", "park")}}
            info["name"] = _name(walk["kind"], info, info.get("locality"), info["loop"])
            info["overpass_done"] = walk.get("overpass_done")
        service.set_place(walk["id"], info)
        done += 1
    return done


async def loop(every: float = 600.0) -> None:
    """New walks get their names within ten minutes; the first run names the backlog, 40 at a time."""
    while True:
        try:
            await asyncio.to_thread(name_pending)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("Naming walks failed: %s", exc)
        await asyncio.sleep(every)
