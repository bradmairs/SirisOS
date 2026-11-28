"""SirisTrails (11.22): walks and hikes from Apple Health, with their GPS routes, on a map.

What's kept: every **hike** (any length) and every **outdoor walk of an hour or more**, with a GPS route. Shorter
walks, indoor walks and everything else stay with SirisAI as before.

Where they come from:

- **Health Auto Export**: its workouts automation, with "Include Route Data" on, posts each workout with its route.
  SirisOS's health import (training/api.py) keeps the walks and hikes here before passing the rest to SirisAI.
- **The Apple Health export** (Health app → profile → Export All Health Data → export.zip): export.xml lists every
  workout, and workout-routes/ holds each one's GPX. Uploading it brings in every walk ever recorded.

The same walk from both (or uploaded twice) is kept once: a start within DUPLICATE_MINUTES of one already here is the
same walk. A walk you delete stays deleted (its start is remembered), so a later import doesn't bring it back.

For each walk: distance and time from the route (or the workout's own figures), moving time, ascent and descent
(smoothed, so GPS noise doesn't add up), highest point, pace, heart rate and energy when Health has them, and a
simplified line for the map. Everything is kept in SIRISOS_TRAILS_PATH (trails/ in the data folder): index.json and a
file per route. Place names aren't looked up: nothing about where you walk leaves SirisOS except the map tiles.
"""

from __future__ import annotations

import functools
import json
import math
import os
import re
import secrets
import threading
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET

from app.services import json_store

MIN_WALK_MINUTES = 60
DUPLICATE_MINUTES = 3
ASCENT_STEP_M = 3.0          # climbs smaller than this are GPS noise
MOVING_M_PER_S = 0.5
MAP_POINTS = 250             # each route's line on the overview map
_lock = threading.RLock()


def root() -> Path:
    return json_store.data_path("SIRISOS_TRAILS_PATH", "trails")


def _index_path() -> Path:
    return root() / "index.json"


def load() -> dict[str, Any]:
    raw = json_store.read(_index_path(), {})
    raw = raw if isinstance(raw, dict) else {}
    raw.setdefault("walks", [])
    raw.setdefault("deleted", [])  # starts of walks you deleted
    return raw


def _save(doc: dict[str, Any]) -> None:
    root().mkdir(parents=True, exist_ok=True)
    json_store.write(_index_path(), doc)


def _route_path(walk_id: str) -> Path:
    """A walk's route file: the id is one SirisTrails made, and the path stays inside the routes folder."""
    if not re.fullmatch(r"w_[0-9a-f]{12}", walk_id or ""):
        raise KeyError(walk_id)
    folder = os.path.normpath(str(root() / "routes"))
    candidate = os.path.normpath(os.path.join(folder, walk_id + ".json"))
    if not candidate.startswith(folder + os.sep):
        raise KeyError(walk_id)
    return Path(candidate)


# -- what counts ---------------------------------------------------------------------------------------------------

def kind_of(name: str) -> str | None:
    """'hike', 'walk' (outdoor), or None for anything else."""
    n = (name or "").lower().replace("hkworkoutactivitytype", "")
    if "hik" in n or "tramp" in n:
        return "hike"
    if "walk" in n and "indoor" not in n and "wheelchair" not in n:
        return "walk"
    return None


def qualifies(kind: str | None, minutes: float | None) -> bool:
    return kind == "hike" or (kind == "walk" and (minutes or 0) >= MIN_WALK_MINUTES)


# -- route maths ---------------------------------------------------------------------------------------------------

def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(min(1.0, math.sqrt(h)))


def climb(elevations: Iterable[float | None]) -> tuple[float, float]:
    """Ascent and descent, counting only moves of ASCENT_STEP_M or more from the last counted height."""
    up = down = 0.0
    ref = None
    for e in elevations:
        if e is None:
            continue
        if ref is None:
            ref = e
        elif e - ref >= ASCENT_STEP_M:
            up += e - ref
            ref = e
        elif ref - e >= ASCENT_STEP_M:
            down += ref - e
            ref = e
    return round(up), round(down)


def simplify(points: list[list[float]], keep: int = MAP_POINTS) -> list[list[float]]:
    """Douglas–Peucker on lat/lon, loosened until the line has at most `keep` points."""
    if len(points) <= keep:
        return [[round(p[0], 5), round(p[1], 5)] for p in points]

    def rdp(pts: list[list[float]], eps: float) -> list[list[float]]:
        stack, keep_idx = [(0, len(pts) - 1)], {0, len(pts) - 1}
        while stack:
            s, e = stack.pop()
            (y1, x1), (y2, x2) = pts[s][:2], pts[e][:2]
            dx, dy = x2 - x1, y2 - y1
            norm = math.hypot(dx, dy) or 1e-12
            best, idx = 0.0, None
            for i in range(s + 1, e):
                d = abs(dy * (pts[i][1] - x1) - dx * (pts[i][0] - y1)) / norm
                if d > best:
                    best, idx = d, i
            if idx is not None and best > eps:
                keep_idx.add(idx)
                stack += [(s, idx), (idx, e)]
        return [pts[i] for i in sorted(keep_idx)]

    eps, out = 1e-5, points
    while True:
        out = rdp(points, eps)
        if len(out) <= keep:
            return [[round(p[0], 5), round(p[1], 5)] for p in out]
        eps *= 2


def _ts(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace(" +", "+").replace(" -", "-")
    for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def metrics(points: list[list[float]]) -> dict[str, Any]:
    """From [[lat, lon, ele|None, unix seconds|None], ...]."""
    dist = moving = 0.0
    for a, b in zip(points, points[1:]):
        d = haversine((a[0], a[1]), (b[0], b[1]))
        dist += d
        if a[3] is not None and b[3] is not None and b[3] > a[3] and d / (b[3] - a[3]) >= MOVING_M_PER_S:
            moving += b[3] - a[3]
    eles = [p[2] for p in points if p[2] is not None]
    up, down = climb(p[2] for p in points)
    return {"route_km": round(dist / 1000, 2), "moving_minutes": round(moving / 60, 1) if moving else None,
            "ascent_m": up if eles else None, "descent_m": down if eles else None,
            "highest_m": round(max(eles)) if eles else None, "lowest_m": round(min(eles)) if eles else None}


# -- storing -------------------------------------------------------------------------------------------------------

def add(*, kind: str, start: datetime, end: datetime | None, points: list[list[float]], minutes: float | None = None,
        km: float | None = None, kcal: float | None = None, avg_hr: float | None = None, max_hr: float | None = None,
        source: str = "", tz_offset_min: int | None = None) -> dict[str, Any] | None:
    """Keep a walk unless it's already here (or deleted). Returns it, or None when skipped."""
    if len(points) < 2:
        return None
    with _lock:
        doc = load()
        for w in doc["walks"]:
            if abs((datetime.fromisoformat(w["start"]) - start).total_seconds()) <= DUPLICATE_MINUTES * 60:
                return None
        if any(abs((datetime.fromisoformat(s) - start).total_seconds()) <= DUPLICATE_MINUTES * 60 for s in doc["deleted"]):
            return None
        m = metrics(points)
        if minutes is None and end:
            minutes = (end - start).total_seconds() / 60
        local = start + timedelta(minutes=tz_offset_min or 0)
        walk_id = "w_" + secrets.token_hex(6)
        dist_km = km if km else m["route_km"]
        walk = {
            "id": walk_id, "kind": kind, "start": start.isoformat(), "end": end.isoformat() if end else None,
            "name": f"{'Hike' if kind == 'hike' else 'Walk'}, {local.strftime('%a %-d %b %Y')}", "name_auto": True, "note": "",
            "minutes": round(minutes, 1) if minutes else None, "km": round(dist_km, 2) if dist_km else None,
            "kcal": round(kcal) if kcal else None, "avg_hr": round(avg_hr) if avg_hr else None, "max_hr": round(max_hr) if max_hr else None,
            **{k: v for k, v in m.items() if k != "route_km"},
            "pace_min_per_km": round(minutes / dist_km, 1) if minutes and dist_km else None,
            "start_point": points[0][:2], "line": simplify(points), "source": source, "added": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        path = _route_path(walk_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"points": points}), encoding="utf-8")
        doc["walks"].append(walk)
        doc["walks"].sort(key=lambda w: w["start"], reverse=True)
        _save(doc)
        return walk


def change(walk_id: str, name: str | None = None, note: str | None = None) -> dict[str, Any]:
    with _lock:
        doc = load()
        walk = next((w for w in doc["walks"] if w["id"] == walk_id), None)
        if walk is None:
            raise KeyError(walk_id)
        if name is not None and name.strip() and name.strip() != walk["name"]:
            walk["name"] = name.strip()[:120]
            walk["name_auto"] = False  # 12.1: yours now; the place lookup won't change it
        if note is not None:
            walk["note"] = note.strip()[:2000]
        _save(doc)
        return walk


def set_place(walk_id: str, info: dict[str, Any]) -> dict[str, Any] | None:
    """12.1: what's around the walk (places.py): its place line, and its name unless you've given it one."""
    with _lock:
        doc = load()
        walk = next((w for w in doc["walks"] if w["id"] == walk_id), None)
        if walk is None:
            return None
        walk["place"] = info.get("place")
        walk["loop"] = info.get("loop")
        walk["landmarks"] = {k: info.get(k) for k in ("peak", "trail", "park", "locality") if info.get(k)}
        for k in ("region", "country", "country_code"):  # 12.2: for states per country
            walk[k] = info.get(k)
        from app.trails.places import PLACE_VERSION

        walk["place_v"] = PLACE_VERSION
        if info.get("overpass_done"):
            walk["overpass_done"] = True
        # Overpass couldn't be reached: the place-name fallback stands, and it's looked up again on a later run.
        walk["names_retry"] = (walk.get("names_retry") or 0) + 1 if info.get("retry") else walk.get("names_retry") or 0
        if walk.get("name_auto", True) and info.get("name"):
            walk["name"] = info["name"][:120]
        _save(doc)
        return walk


def set_fields(walk_id: str, **fields: Any) -> dict[str, Any] | None:
    """12.4: background lookups (weather) write their answers here."""
    with _lock:
        doc = load()
        walk = next((w for w in doc["walks"] if w["id"] == walk_id), None)
        if walk is None:
            return None
        walk.update(fields)
        _save(doc)
        return walk


def _stamp() -> Any:
    try:
        st = _index_path().stat()
        return (str(_index_path()), st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def _travel() -> list[dict[str, Any]]:
    try:
        from app.travel import service as travel

        return travel.load()
    except Exception:  # noqa: BLE001 - Travel is optional here
        return []


def delete(walk_id: str) -> None:
    with _lock:
        doc = load()
        walk = next((w for w in doc["walks"] if w["id"] == walk_id), None)
        if walk is None:
            raise KeyError(walk_id)
        doc["walks"] = [w for w in doc["walks"] if w["id"] != walk_id]
        doc["deleted"].append(walk["start"])
        _save(doc)
        _route_path(walk_id).unlink(missing_ok=True)
        from app.trails import tools  # 12.5: and its photos

        import shutil

        shutil.rmtree(tools._photo_dir(walk_id), ignore_errors=True)


def _smooth(values: list[float], window: int = 9) -> list[float]:
    """A centred moving average: GPS height wobbles a few metres point to point."""
    half, out = window // 2, []
    for i in range(len(values)):
        chunk = values[max(0, i - half): i + half + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def splits(points: list[list[float]]) -> list[dict[str, Any]]:
    """Each kilometre: time, pace and climb (the last one may be part of a kilometre)."""
    out: list[dict[str, Any]] = []
    run, km_start_i, next_km = 0.0, 0, 1000.0
    for i in range(1, len(points)):
        run += haversine((points[i - 1][0], points[i - 1][1]), (points[i][0], points[i][1]))
        last = i == len(points) - 1
        if run >= next_km or last:
            a, b = points[km_start_i], points[i]
            length = (run - (next_km - 1000)) / 1000 if last and run < next_km else 1.0
            secs = (b[3] - a[3]) if a[3] is not None and b[3] is not None else None
            eles = [p[2] for p in points[km_start_i: i + 1] if p[2] is not None]
            up, down = climb(eles)
            if length >= 0.05:
                out.append({"km": len(out) + 1, "length_km": round(length, 2), "minutes": round(secs / 60, 1) if secs else None,
                            "pace_min_per_km": round(secs / 60 / length, 1) if secs and length else None, "up_m": up, "down_m": down})
            km_start_i, next_km = i, next_km + 1000
    return out


def detail(walk_id: str) -> dict[str, Any]:
    walk = next((w for w in load()["walks"] if w["id"] == walk_id), None)
    if walk is None:
        raise KeyError(walk_id)
    points = json.loads(_route_path(walk_id).read_text(encoding="utf-8"))["points"]
    run, dists = 0.0, [0.0]
    for a, b in zip(points, points[1:]):
        run += haversine((a[0], a[1]), (b[0], b[1]))
        dists.append(run)
    with_ele = [(i, p[2]) for i, p in enumerate(points) if p[2] is not None]
    smooth = _smooth([e for _, e in with_ele])
    step = max(1, len(with_ele) // 400)
    profile = [[round(dists[i] / 1000, 3), round(s, 1), round(points[i][0], 6), round(points[i][1], 6)]
               for (i, _), s in list(zip(with_ele, smooth))[::step]]
    km_marks, next_km = [], 1000.0
    for i, d in enumerate(dists):
        if d >= next_km:
            km_marks.append([int(next_km // 1000), round(points[i][0], 6), round(points[i][1], 6)])
            next_km += 1000
    from app.trails import insights

    everything = load()["walks"]
    group = next((g for g in insights.repeats_cached(everything, _stamp()) if any(t["id"] == walk_id for t in g["times"])), None)
    return {**with_tz(walk), "repeat": group, "route": [[round(p[0], 6), round(p[1], 6)] for p in points[:: max(1, len(points) // 2000)]],
            "profile": profile, "splits": splits(points), "km_marks": km_marks}


@functools.lru_cache(maxsize=1)
def _zones() -> list[tuple[set[str], float, float, str]]:
    """The time-zone database's cities (zone1970.tab): country codes, lat, lon, zone."""
    out = []
    try:
        lines = Path(os.getenv("SIRISOS_TRAILS_ZONE_TAB", "/usr/share/zoneinfo/zone1970.tab")).read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        m = re.fullmatch(r"([+-])(\d{2})(\d{2})(\d{2})?([+-])(\d{3})(\d{2})(\d{2})?", parts[1])
        if not m:
            continue
        lat = (int(m[2]) + int(m[3]) / 60 + int(m[4] or 0) / 3600) * (1 if m[1] == "+" else -1)
        lon = (int(m[6]) + int(m[7]) / 60 + int(m[8] or 0) / 3600) * (1 if m[5] == "+" else -1)
        out.append((set(parts[0].split(",")), lat, lon, parts[2]))
    return out


# Where state borders, not distance, decide the clock (Byron Bay is nearer Brisbane but keeps Sydney time).
REGION_TZ = {("AU", "Victoria"): "Australia/Melbourne", ("AU", "New South Wales"): "Australia/Sydney",
             ("AU", "Australian Capital Territory"): "Australia/Sydney", ("AU", "Tasmania"): "Australia/Hobart",
             ("AU", "Queensland"): "Australia/Brisbane", ("AU", "South Australia"): "Australia/Adelaide",
             ("AU", "Western Australia"): "Australia/Perth", ("AU", "Northern Territory"): "Australia/Darwin",
             ("US", "Hawaii"): "Pacific/Honolulu", ("US", "California"): "America/Los_Angeles", ("US", "New York"): "America/New_York"}


@functools.lru_cache(maxsize=512)
def tz_for(code: str | None, lat: float, lon: float, region: str | None = None) -> str | None:
    """12.2.3: the walk's own time zone: the nearest time-zone city in its country. Apple Health's export writes
    every time in the phone's zone when it was exported, so a Hong Kong hike showed in Melbourne time."""
    if code and (code.upper(), region) in REGION_TZ:
        return REGION_TZ[(code.upper(), region)]
    zones = [z for z in _zones() if code and code.upper() in z[0]] or []
    if not zones:
        return None
    return min(zones, key=lambda z: haversine((lat, lon), (z[1], z[2])))[3]


def with_tz(walk: dict[str, Any]) -> dict[str, Any]:
    p = walk.get("start_point") or [0, 0]
    return {**walk, "tz": tz_for(walk.get("country_code"), round(p[0], 2), round(p[1], 2), walk.get("region"))}


def _flag(code: str | None) -> str:
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in code.upper()) if code and len(code) == 2 and code.isalpha() else ""


def summary(year: int | None = None) -> dict[str, Any]:
    everything = load()["walks"]
    walks = [w for w in everything if w["start"][:4] == str(year)] if year else everything

    def total(items: list[dict[str, Any]], key: str) -> float:
        return sum(w.get(key) or 0 for w in items)

    # 12.2: where: countries, and their states or regions
    countries: dict[str, dict[str, Any]] = {}
    for w in walks:
        if not w.get("country"):
            continue
        c = countries.setdefault(w["country"], {"country": w["country"], "code": w.get("country_code"), "flag": _flag(w.get("country_code")),
                                                "walks": 0, "km": 0.0, "hours": 0.0, "regions": {}})
        c["walks"] += 1
        c["km"] += w.get("km") or 0
        c["hours"] += (w.get("minutes") or 0) / 60
        r = c["regions"].setdefault(w.get("region") or "Elsewhere", {"region": w.get("region") or "Elsewhere", "walks": 0, "km": 0.0, "places": set()})
        r["walks"] += 1
        r["km"] += w.get("km") or 0
        if (w.get("landmarks") or {}).get("locality"):
            r["places"].add(w["landmarks"]["locality"])
    where = []
    for c in sorted(countries.values(), key=lambda c: -c["km"]):
        regions = [{"region": r["region"], "walks": r["walks"], "km": round(r["km"], 1), "places": len(r["places"])}
                   for r in sorted(c["regions"].values(), key=lambda r: -r["km"])]
        where.append({**c, "km": round(c["km"], 1), "hours": round(c["hours"], 1), "regions": regions})

    def record(key: str) -> dict[str, Any] | None:
        best = max((w for w in walks if w.get(key)), key=lambda w: w[key], default=None)
        return {"id": best["id"], "name": best["name"], "value": best[key], "start": best["start"], "tz": with_tz(best)["tz"]} if best else None

    by_year: dict[str, dict[str, float]] = {}
    for w in everything:
        y = by_year.setdefault(w["start"][:4], {"walks": 0, "km": 0.0, "hours": 0.0})
        y["walks"] += 1
        y["km"] += w.get("km") or 0
        y["hours"] += (w.get("minutes") or 0) / 60
    timed = [w for w in walks if w.get("minutes") and w.get("km")]
    from app.trails import insights  # 12.4

    shown = {w["id"] for w in walks}
    groups = [g for g in insights.repeats_cached(everything, _stamp()) if any(t["id"] in shown for t in g["times"])]
    count_of = {t["id"]: g["count"] for g in groups for t in g["times"]}
    return {"walks": [{**with_tz(w), "repeats": count_of.get(w["id"])} for w in walks],
            "repeats": groups, "landmarks": insights.landmarks(walks), "trips": insights.trips(walks, _travel(), everything),
            "weather_records": insights.weather_records(walks), "count": len(walks), "hikes": sum(w["kind"] == "hike" for w in walks),
            "km": round(total(walks, "km"), 1), "hours": round(total(walks, "minutes") / 60, 1), "ascent_m": round(total(walks, "ascent_m")),
            "highest_m": max((w["highest_m"] for w in walks if w.get("highest_m") is not None), default=None),
            "longest_km": max((w["km"] for w in walks if w.get("km")), default=None),
            "avg_km": round(total(walks, "km") / len(walks), 1) if walks else None,
            "avg_minutes": round(total(walks, "minutes") / len(walks)) if walks else None,
            "avg_pace": round(sum(w["minutes"] for w in timed) / sum(w["km"] for w in timed), 1) if timed else None,
            "countries": len(where), "regions": sum(len(c["regions"]) for c in where),
            "places": len({(w.get("landmarks") or {}).get("locality") for w in walks if (w.get("landmarks") or {}).get("locality")}),
            "where": where,
            "records": {"longest": record("km"), "longest_time": record("minutes"), "most_climbing": record("ascent_m"), "highest": record("highest_m")},
            "by_year": [{"year": int(y), "walks": v["walks"], "km": round(v["km"], 1), "hours": round(v["hours"], 1)} for y, v in sorted(by_year.items())],
            "years": sorted({int(w["start"][:4]) for w in everything}, reverse=True)}


# -- Health Auto Export --------------------------------------------------------------------------------------------

def _qty(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("qty", value.get("avg"))
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _km(value: Any) -> float | None:
    q = _qty(value)
    if q is None:
        return None
    units = str(value.get("units", "km") if isinstance(value, dict) else "km").lower()
    return q * 1.609344 if units.startswith("mi") else q / 1000 if units == "m" else q


def from_auto_export(body: Any) -> list[dict[str, Any]]:
    """Keep the walks and hikes (with routes) in a Health Auto Export post. Never raises: the import carries on."""
    out = []
    workouts = ((body or {}).get("data") or {}).get("workouts") if isinstance(body, dict) else None
    for w in workouts if isinstance(workouts, list) else []:
        try:
            kind = kind_of(str(w.get("name") or ""))
            start, end = _ts(w.get("start")), _ts(w.get("end"))
            minutes = (_qty(w.get("duration")) or 0) / 60 or ((end - start).total_seconds() / 60 if start and end else None)
            if not start or not qualifies(kind, minutes):
                continue
            raw = w.get("route") or w.get("locations") or []
            points = []
            for p in raw if isinstance(raw, list) else []:
                lat, lon = p.get("lat", p.get("latitude")), p.get("lon", p.get("longitude"))
                if lat is None or lon is None:
                    continue
                t = _ts(p.get("timestamp") or p.get("time") or p.get("date"))
                ele = p.get("altitude", p.get("elevation"))
                points.append([float(lat), float(lon), float(ele) if ele is not None else None, t.timestamp() if t else None])
            hr = w.get("heartRate") or {}
            walk = add(kind=kind or "walk", start=start, end=end, points=points, minutes=minutes, km=_km(w.get("distance")),
                       kcal=_qty(w.get("activeEnergyBurned") or w.get("activeEnergy")),
                       avg_hr=_qty(w.get("avgHeartRate") or (hr.get("avg") if isinstance(hr, dict) else None)),
                       max_hr=_qty(w.get("maxHeartRate") or (hr.get("max") if isinstance(hr, dict) else None)),
                       source="health_auto_export", tz_offset_min=int(start.utcoffset().total_seconds() // 60) if start.utcoffset() else None)
            if walk:
                out.append(walk)
        except Exception:  # noqa: BLE001 - one odd workout never stops the import
            continue
    return out


def strip_routes(body: Any) -> Any:
    """The body for SirisAI without the route points (it doesn't use them, and they're most of the size)."""
    workouts = ((body or {}).get("data") or {}).get("workouts") if isinstance(body, dict) else None
    if isinstance(workouts, list):
        for w in workouts:
            if isinstance(w, dict):
                w.pop("route", None)
                w.pop("locations", None)
    return body


# -- the Apple Health export ---------------------------------------------------------------------------------------

_status: dict[str, Any] = {"running": False}
_GPX = "{http://www.topografix.com/GPX/1/1}"


def import_status() -> dict[str, Any]:
    saved = load().get("last_import")
    return {**(saved or {}), **_status}


def _gpx_points(data: bytes) -> list[list[float]]:
    points = []
    for _, el in ET.iterparse(__import__("io").BytesIO(data), events=("end",)):
        if el.tag.endswith("trkpt"):
            ele, t = el.find(f"{_GPX}ele"), el.find(f"{_GPX}time")
            if ele is None:
                ele = next((c for c in el if c.tag.endswith("ele")), None)
            if t is None:
                t = next((c for c in el if c.tag.endswith("time")), None)
            when = _ts(t.text) if t is not None else None
            points.append([float(el.get("lat")), float(el.get("lon")), float(ele.text) if ele is not None and ele.text else None,
                           when.timestamp() if when else None])
            el.clear()
    return points


def import_apple_export(zip_path: Path) -> dict[str, Any]:
    """Every qualifying workout in an Apple Health export.zip, with its GPX route."""
    added = skipped = no_route = looked = 0
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        xml_name = next((n for n in names if n.endswith("export.xml") and "cda" not in n.lower()), None)
        if not xml_name:
            raise ValueError("That zip has no export.xml: use Export All Health Data in the Health app.")
        prefix = xml_name[: -len("export.xml")]
        with z.open(xml_name) as fh:
            for _, el in ET.iterparse(fh, events=("end",)):
                if el.tag != "Workout":
                    if el.tag in ("Record", "ActivitySummary"):
                        el.clear()
                    continue
                looked += 1
                kind = kind_of(el.get("workoutActivityType", ""))
                dur = float(el.get("duration") or 0)
                minutes = dur * 60 if (el.get("durationUnit") or "min") == "hr" else dur if (el.get("durationUnit") or "min") == "min" else dur / 60
                if not qualifies(kind, minutes):
                    el.clear()
                    continue
                start, end = _ts(el.get("startDate")), _ts(el.get("endDate"))
                ref = next((f.get("path") for r in el.iter("WorkoutRoute") for f in r.iter("FileReference")), None)
                if not ref or not start:
                    no_route += 1
                    el.clear()
                    continue
                member = prefix + ref.lstrip("/")
                if member not in names:
                    no_route += 1
                    el.clear()
                    continue
                stats = {s.get("type"): s for s in el.iter("WorkoutStatistics")}
                hr = stats.get("HKQuantityTypeIdentifierHeartRate")
                dist = el.get("totalDistance")
                km = float(dist) * (1.609344 if el.get("totalDistanceUnit") == "mi" else 1) if dist else None
                if km is None and stats.get("HKQuantityTypeIdentifierDistanceWalkingRunning") is not None:
                    s = stats["HKQuantityTypeIdentifierDistanceWalkingRunning"]
                    km = float(s.get("sum") or 0) * (1.609344 if s.get("unit") == "mi" else 1) or None
                energy = el.get("totalEnergyBurned") or (stats.get("HKQuantityTypeIdentifierActiveEnergyBurned").get("sum")
                                                         if stats.get("HKQuantityTypeIdentifierActiveEnergyBurned") is not None else None)
                walk = add(kind=kind or "walk", start=start, end=end, points=_gpx_points(z.read(member)), minutes=minutes, km=km,
                           kcal=float(energy) if energy else None,
                           avg_hr=float(hr.get("average")) if hr is not None and hr.get("average") else None,
                           max_hr=float(hr.get("maximum")) if hr is not None and hr.get("maximum") else None,
                           source="apple_health_export", tz_offset_min=int(start.utcoffset().total_seconds() // 60) if start.utcoffset() else None)
                if walk:
                    added += 1
                else:
                    skipped += 1
                el.clear()
    return {"workouts": looked, "added": added, "already_here": skipped, "no_route": no_route}


def start_apple_import(zip_path: Path) -> bool:
    if _status.get("running"):
        return False

    def work() -> None:
        _status.update(running=True, started=datetime.now(timezone.utc).isoformat(timespec="seconds"), error=None)
        try:
            result = import_apple_export(zip_path)
            with _lock:
                doc = load()
                doc["last_import"] = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **result}
                _save(doc)
            if result.get("added"):
                from app.trails import places

                places.kick()  # 12.2.1: the new walks are named straight away
        except Exception as exc:  # noqa: BLE001 - say why on the screen
            _status["error"] = str(exc)[:300]
        finally:
            zip_path.unlink(missing_ok=True)
            _status["running"] = False

    threading.Thread(target=work, daemon=True, name="trails-import").start()
    return True
