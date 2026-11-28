"""Photos, GPX, trimming and joining walks (12.5).

- **Photos**: add them to a walk from your phone. The browser makes a 2048 px JPEG and a small one for the gallery,
  and reads when and where each was taken from its EXIF; the photo goes on the route where you were then (its GPS when
  it has it, else the route point at the time it was taken). Kept in trails/photos/<walk>/.
- **GPX**: any walk as a GPX file, for other apps. With `hide_home`, the bits of the route within HOME_M of home
  (where most walks start) are left off both ends, so a shared file doesn't show where you live.
- **Trim**: cut the start or end (the phone kept recording in the car). The original route is kept: "Undo trim".
- **Join**: two recordings of one walk (it was paused and restarted) become one. The second is kept inside the first,
  so it can be split back out.
"""

from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from app.trails import service

HOME_M = 400
MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_THUMB_BYTES = 512 * 1024
MAX_PHOTOS = 60
PHOTO_ID = re.compile(r"p_[0-9a-f]{10}")
NEAR_MINUTES = 20  # a photo this long before the start or after the end still belongs to the walk


def _points(walk_id: str) -> dict[str, Any]:
    return json.loads(service._route_path(walk_id).read_text(encoding="utf-8"))


def _write(walk_id: str, doc: dict[str, Any]) -> None:
    service._route_path(walk_id).write_text(json.dumps(doc), encoding="utf-8")


def _find(doc: dict[str, Any], walk_id: str) -> dict[str, Any]:
    walk = next((w for w in doc["walks"] if w["id"] == walk_id), None)
    if walk is None:
        raise KeyError(walk_id)
    return walk


STATS = ("start", "end", "minutes", "km", "moving_minutes", "ascent_m", "descent_m", "highest_m", "lowest_m", "pace_min_per_km",
         "start_point", "line", "kind", "kcal", "avg_hr", "max_hr")


def _stats(walk: dict[str, Any]) -> dict[str, Any]:
    """What a trim or join changes, kept so undoing it puts the walk back exactly (Health's own distance and all)."""
    return {k: walk.get(k) for k in STATS}


def _restat(walk: dict[str, Any], points: list[list[float]]) -> None:
    """Distance, time, climb and the map line again, from the route as it is now."""
    m = service.metrics(points)
    times = [p[3] for p in points if p[3] is not None]
    walk.update({k: v for k, v in m.items() if k != "route_km"})
    walk["km"] = m["route_km"] or walk.get("km")
    if len(times) >= 2:
        walk["start"] = datetime.fromtimestamp(times[0], timezone.utc).astimezone(datetime.fromisoformat(walk["start"]).tzinfo).isoformat()
        walk["end"] = datetime.fromtimestamp(times[-1], timezone.utc).astimezone(datetime.fromisoformat(walk["start"]).tzinfo).isoformat()
        walk["minutes"] = round((times[-1] - times[0]) / 60, 1)
    walk["pace_min_per_km"] = round(walk["minutes"] / walk["km"], 1) if walk.get("minutes") and walk.get("km") else None
    walk["start_point"] = points[0][:2]
    walk["line"] = service.simplify(points)


# -- trim and join -------------------------------------------------------------------------------------------------

def trim(walk_id: str, from_km: float, to_km: float) -> dict[str, Any]:
    """Keep the route between from_km and to_km (along the original route)."""
    with service._lock:
        doc = service.load()
        walk = _find(doc, walk_id)
        route = _points(walk_id)
        original = route.get("original") or route["points"]
        run, kept = 0.0, []
        for i, p in enumerate(original):
            if i:
                run += service.haversine((original[i - 1][0], original[i - 1][1]), (p[0], p[1]))
            if from_km * 1000 - 1 <= run <= to_km * 1000 + 1:
                kept.append(p)
        if len(kept) < 2:
            raise ValueError("That leaves almost nothing of the walk.")
        route.setdefault("original_stats", _stats(walk))
        route["original"] = original
        route["points"] = kept
        _write(walk_id, route)
        walk["trimmed"] = [round(from_km, 2), round(to_km, 2)]
        _restat(walk, kept)
        service._save(doc)
        return walk


def untrim(walk_id: str) -> dict[str, Any]:
    with service._lock:
        doc = service.load()
        walk = _find(doc, walk_id)
        route = _points(walk_id)
        if route.get("original"):
            route["points"] = route.pop("original")
            walk.update(route.pop("original_stats", None) or {})
            _write(walk_id, route)
        walk.pop("trimmed", None)
        service._save(doc)
        return walk


def join(walk_id: str, other_id: str) -> dict[str, Any]:
    """The other walk's route is added to this one (in time order) and the other leaves the list, kept inside this."""
    if walk_id == other_id:
        raise ValueError("That's the same walk.")
    with service._lock:
        doc = service.load()
        walk, other = _find(doc, walk_id), _find(doc, other_id)
        if abs((datetime.fromisoformat(walk["start"]) - datetime.fromisoformat(other["start"])).total_seconds()) > 24 * 3600:
            raise ValueError("Only walks on the same day can be joined.")
        mine, theirs = _points(walk_id), _points(other_id)
        if mine.get("original") or theirs.get("original"):
            raise ValueError("Undo the trim first.")
        points = sorted(mine["points"] + theirs["points"], key=lambda p: p[3] if p[3] is not None else 0)
        mine.setdefault("joined", []).append({"walk": other, "points": theirs["points"], "stats": _stats(walk)})
        mine["points"] = points
        _write(walk_id, mine)
        kcal = (walk.get("kcal") or 0) + (other.get("kcal") or 0)
        hr = [(w.get("avg_hr"), w.get("minutes") or 0) for w in (walk, other) if w.get("avg_hr")]
        kind = "hike" if "hike" in (walk["kind"], other["kind"]) else "walk"
        recorded = (walk.get("minutes") or 0) + (other.get("minutes") or 0)  # the time recorded, not the break between
        _restat(walk, points)
        if recorded:
            walk["minutes"] = round(recorded, 1)
            walk["pace_min_per_km"] = round(recorded / walk["km"], 1) if walk.get("km") else None
        walk.update(kind=kind, kcal=round(kcal) or None, max_hr=max((w.get("max_hr") or 0) for w in (walk, other)) or None,
                    avg_hr=round(sum(a * m for a, m in hr) / sum(m for _, m in hr)) if hr and sum(m for _, m in hr) else walk.get("avg_hr"),
                    joined=[*(walk.get("joined") or []), other_id], photos=[*(walk.get("photos") or []), *(other.get("photos") or [])])
        walk.pop("weather", None)  # the hours changed: looked up again
        doc["walks"] = [w for w in doc["walks"] if w["id"] != other_id]
        service._save(doc)
        _move_photos(other_id, walk_id)
        service._route_path(other_id).unlink(missing_ok=True)
        return walk


def split(walk_id: str) -> dict[str, Any]:
    """Undo the last join: the other walk comes back as it was."""
    with service._lock:
        doc = service.load()
        walk = _find(doc, walk_id)
        mine = _points(walk_id)
        if not mine.get("joined"):
            raise ValueError("This walk wasn't joined.")
        last = mine["joined"].pop()
        other = last["walk"]
        theirs = {tuple(p) for p in last["points"]}
        mine["points"] = [p for p in mine["points"] if tuple(p) not in theirs]
        _write(walk_id, mine)
        service._route_path(other["id"]).write_text(json.dumps({"points": last["points"]}), encoding="utf-8")
        ids = {p["id"] for p in other.get("photos") or []}
        walk["photos"] = [p for p in walk.get("photos") or [] if p["id"] not in ids]
        _move_photos(walk_id, other["id"], ids)
        walk.update(last.get("stats") or {})
        walk["joined"] = [j for j in walk.get("joined") or [] if j != other["id"]]
        walk.pop("weather", None)
        doc["walks"].append(other)
        doc["walks"].sort(key=lambda w: w["start"], reverse=True)
        service._save(doc)
        return walk


# -- GPX -----------------------------------------------------------------------------------------------------------

def gpx(walk_id: str, hide_home: bool = False) -> str:
    from app.trails import insights

    doc = service.load()
    walk = _find(doc, walk_id)
    points = _points(walk_id)["points"]
    if hide_home:
        base = insights.home(doc["walks"], walk["start"])
        if base:
            far = lambda p: service.haversine((p[0], p[1]), (base[0], base[1])) > HOME_M  # noqa: E731
            first = next((i for i, p in enumerate(points) if far(p)), len(points))
            last = next((i for i in range(len(points) - 1, -1, -1) if far(points[i])), -1)
            points = points[first: last + 1]
    rows = []
    for p in points:
        ele = f"<ele>{p[2]:.1f}</ele>" if p[2] is not None else ""
        when = f"<time>{datetime.fromtimestamp(p[3], timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}</time>" if p[3] is not None else ""
        rows.append(f'<trkpt lat="{p[0]:.6f}" lon="{p[1]:.6f}">{ele}{when}</trkpt>')
    name = escape(walk["name"])
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<gpx version="1.1" creator="SirisTrails" xmlns="http://www.topografix.com/GPX/1/1">\n'
            f'<metadata><name>{name}</name><time>{walk["start"]}</time></metadata>\n'
            f'<trk><name>{name}</name><type>{walk["kind"]}</type><trkseg>\n' + "\n".join(rows) + "\n</trkseg></trk>\n</gpx>\n")


# -- photos --------------------------------------------------------------------------------------------------------

def _photo_dir(walk_id: str) -> Path:
    service._route_path(walk_id)  # checks the id
    folder = os.path.normpath(str(service.root() / "photos"))
    candidate = os.path.normpath(os.path.join(folder, walk_id))
    if not candidate.startswith(folder + os.sep):
        raise KeyError(walk_id)
    return Path(candidate)


def photo_path(walk_id: str, photo_id: str, thumb: bool = False) -> Path:
    if not PHOTO_ID.fullmatch(photo_id or ""):
        raise KeyError(photo_id)
    folder = os.path.normpath(str(_photo_dir(walk_id)))
    candidate = os.path.normpath(os.path.join(folder, photo_id + ("_t" if thumb else "") + ".jpg"))
    if not candidate.startswith(folder + os.sep):
        raise KeyError(photo_id)
    return Path(candidate)


def _move_photos(src: str, dst: str, only: set[str] | None = None) -> None:
    a, b = _photo_dir(src), _photo_dir(dst)
    if not a.exists():
        return
    b.mkdir(parents=True, exist_ok=True)
    for f in a.iterdir():
        if only is None or f.stem.removesuffix("_t") in only:
            f.rename(b / f.name)


def _taken(text: str | None, tz: str | None, fallback: Any = None) -> datetime | None:
    """EXIF's time: with its own offset when the camera wrote one, else in the walk's time zone."""
    if not text:
        return None
    try:
        t = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        try:
            from zoneinfo import ZoneInfo

            t = t.replace(tzinfo=ZoneInfo(tz) if tz else fallback or timezone.utc)
        except Exception:  # noqa: BLE001
            t = t.replace(tzinfo=timezone.utc)
    return t


def place_photo(points: list[list[float]], taken: datetime | None, lat: float | None, lon: float | None,
                start: datetime, end: datetime | None) -> tuple[list[float] | None, float | None]:
    """Where on the route a photo was taken, and how far along (km). GPS first; else the route point at that time."""
    if taken is not None:
        lo, hi = start - timedelta(minutes=NEAR_MINUTES), (end or start + timedelta(hours=12)) + timedelta(minutes=NEAR_MINUTES)
        if not lo <= taken <= hi:
            taken = None  # not during the walk: placed by GPS if it has it, else not on the map
    best, best_i = None, None
    if lat is not None and lon is not None:
        d = [service.haversine((lat, lon), (p[0], p[1])) for p in points]
        best_i = min(range(len(points)), key=d.__getitem__)
        best = [round(lat, 6), round(lon, 6)] if d[best_i] < 2000 else None
        if best is None:
            best_i = None
    elif taken is not None:
        ts = taken.timestamp()
        timed = [(i, p) for i, p in enumerate(points) if p[3] is not None]
        if timed:
            best_i, p = min(timed, key=lambda ip: abs(ip[1][3] - ts))
            best = [round(p[0], 6), round(p[1], 6)]
    if best_i is None:
        return best, None
    run = sum(service.haversine((points[i - 1][0], points[i - 1][1]), (points[i][0], points[i][1])) for i in range(1, best_i + 1))
    return best, round(run / 1000, 2)


def add_photo(walk_id: str, full: bytes, thumb: bytes, taken: str | None, lat: float | None, lon: float | None,
              width: int | None = None, height: int | None = None) -> dict[str, Any]:
    if not full.startswith(b"\xff\xd8") or not thumb.startswith(b"\xff\xd8"):
        raise ValueError("Photos come as JPEG.")
    if len(full) > MAX_PHOTO_BYTES or len(thumb) > MAX_THUMB_BYTES:
        raise ValueError("That photo is too big.")
    with service._lock:
        doc = service.load()
        walk = _find(doc, walk_id)
        if len(walk.get("photos") or []) >= MAX_PHOTOS:
            raise ValueError(f"A walk keeps {MAX_PHOTOS} photos at most.")
        tz = service.with_tz(walk).get("tz")
        start = datetime.fromisoformat(walk["start"])
        when = _taken(taken, tz, start.tzinfo)  # no time zone known: the one the walk was recorded in
        end = datetime.fromisoformat(walk["end"]) if walk.get("end") else None
        at, km = place_photo(_points(walk_id)["points"], when, lat, lon, start, end)
        pid = "p_" + secrets.token_hex(5)
        photo_path(walk_id, pid).parent.mkdir(parents=True, exist_ok=True)
        photo_path(walk_id, pid).write_bytes(full)
        photo_path(walk_id, pid, thumb=True).write_bytes(thumb)
        photo = {"id": pid, "taken": when.isoformat() if when else None, "at": at, "km": km, "w": width, "h": height}
        walk["photos"] = sorted([*(walk.get("photos") or []), photo], key=lambda p: (p["km"] is None, p["km"] or 0, p["taken"] or ""))
        service._save(doc)
        return photo


def remove_photo(walk_id: str, photo_id: str) -> None:
    with service._lock:
        doc = service.load()
        walk = _find(doc, walk_id)
        if not any(p["id"] == photo_id for p in walk.get("photos") or []):
            raise KeyError(photo_id)
        walk["photos"] = [p for p in walk["photos"] if p["id"] != photo_id]
        service._save(doc)
        photo_path(walk_id, photo_id).unlink(missing_ok=True)
        photo_path(walk_id, photo_id, thumb=True).unlink(missing_ok=True)
