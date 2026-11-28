"""Streets explored and walks you want to do (12.6).

- **Streets explored**: for the suburbs you walk in most (STREETS_MIN_WALKS or more walks), the named streets and
  paths there (from OpenStreetMap, inside the suburb's boundary) and how much of each you've walked: a street counts
  as walked where your routes came within NEAR_M of it. Looked up in the background, a suburb at a time, and kept in
  trails/streets/; the share walked is worked out again whenever your walks change.
- **Wishlist**: search OpenStreetMap for a track, peak or park ("Cathedral Range", "Mt Feathertop") and add it. Its
  line comes from OpenStreetMap and its climb from Open-Meteo's elevation service. It's ticked off by itself when a
  walk covers WISH_SHARE of its line (or reaches the peak, or walks inside the park).
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import secrets
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from app.services import json_store
from app.trails import service

logger = logging.getLogger(__name__)

STREETS_MIN_WALKS = 5
STREETS_SUBURBS = 4
NEAR_M = 30.0
STEP_M = 25.0
REFRESH_DAYS = 60
WISH_SHARE = 0.7
WISH_POINT_M = 200.0
TRACK_KM = 30
SEARCH = os.getenv("SIRISOS_TRAILS_NOMINATIM_SEARCH", "https://nominatim.openstreetmap.org/search")
LOOKUP = os.getenv("SIRISOS_TRAILS_NOMINATIM_LOOKUP", "https://nominatim.openstreetmap.org/lookup")
ELEVATION = os.getenv("SIRISOS_TRAILS_ELEVATION", "https://api.open-meteo.com/v1/elevation")
STREET_TYPES = "residential|living_street|unclassified|tertiary|secondary|primary|pedestrian|footway|path|cycleway|track|service"
_lock = threading.RLock()
_cache: dict[str, Any] = {}


def _client() -> httpx.Client:
    from app.trails.places import UA

    return httpx.Client(timeout=40, headers={"User-Agent": UA, "Accept-Language": "en"})


# -- geometry ------------------------------------------------------------------------------------------------------

def _grid(points: list[list[float]], cell_m: float = NEAR_M) -> tuple[set[tuple[int, int]], float]:
    """Every route point's grid square (NEAR_M across), so 'is a route near here' is a lookup."""
    if not points:
        return set(), 0.0
    lat0 = points[0][0]
    kx = 111320 * math.cos(math.radians(lat0))
    return {(int(p[1] * kx // cell_m), int(p[0] * 110540 // cell_m)) for p in points}, lat0


def _near(grid: set[tuple[int, int]], lat0: float, p: tuple[float, float], cell_m: float = NEAR_M) -> bool:
    kx = 111320 * math.cos(math.radians(lat0))
    x, y = int(p[1] * kx // cell_m), int(p[0] * 110540 // cell_m)
    return any((x + dx, y + dy) in grid for dx in (-1, 0, 1) for dy in (-1, 0, 1))


def _densify(line: list[tuple[float, float]], step: float = STEP_M) -> list[tuple[float, float]]:
    out = [line[0]] if line else []
    for a, b in zip(line, line[1:]):
        d = service.haversine(a, b)
        n = max(1, int(d // step))
        out += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(1, n + 1)]
    return out


def _length_m(line: list[tuple[float, float]]) -> float:
    return sum(service.haversine(a, b) for a, b in zip(line, line[1:]))


def _inside(p: tuple[float, float], ring: list[tuple[float, float]]) -> bool:
    """Ray casting: ring is [(lat, lon), ...]."""
    y, x, inside = p[0], p[1], False
    for (y1, x1), (y2, x2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1:
            inside = not inside
    return inside


def _rings(geojson: dict[str, Any]) -> list[list[tuple[float, float]]]:
    """Outer rings of a (Multi)Polygon as [(lat, lon)]."""
    t, c = geojson.get("type"), geojson.get("coordinates") or []
    polys = [c] if t == "Polygon" else c if t == "MultiPolygon" else []
    return [[(pt[1], pt[0]) for pt in poly[0]] for poly in polys if poly]


def _lines(geojson: dict[str, Any]) -> list[list[tuple[float, float]]]:
    t, c = geojson.get("type"), geojson.get("coordinates") or []
    if t == "LineString":
        return [[(pt[1], pt[0]) for pt in c]]
    if t == "MultiLineString":
        return [[(pt[1], pt[0]) for pt in line] for line in c]
    return []


def _thin(line: list[tuple[float, float]], keep: int = 400) -> list[list[float]]:
    return service.simplify([[p[0], p[1]] for p in line], keep)


# -- streets explored ----------------------------------------------------------------------------------------------

def _streets_dir() -> Path:
    return service.root() / "streets"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "place"


def _street_file(slug: str) -> Path:
    if not re.fullmatch(r"[a-z0-9-]{1,60}", slug or ""):
        raise KeyError(slug)
    folder = os.path.normpath(str(_streets_dir()))
    candidate = os.path.normpath(os.path.join(folder, slug + ".json"))
    if not candidate.startswith(folder + os.sep):
        raise KeyError(slug)
    return Path(candidate)


def suburbs(walks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The suburbs walked in most: (locality, region, country, walks)."""
    seen = Counter(((w.get("landmarks") or {}).get("locality"), w.get("region"), w.get("country")) for w in walks
                   if (w.get("landmarks") or {}).get("locality") and w.get("country"))
    return [{"locality": k[0], "region": k[1], "country": k[2], "walks": n, "slug": _slug(f"{k[0]} {k[1] or ''}")}
            for k, n in seen.most_common(STREETS_SUBURBS) if n >= STREETS_MIN_WALKS]


def fetch_streets(client: httpx.Client, locality: str, region: str | None, country: str | None) -> dict[str, Any]:
    """The suburb's boundary (Nominatim), then its named streets and paths (Overpass), kept inside the boundary."""
    from app.trails import places

    q = ", ".join(x for x in (locality, region, country) if x)
    got = places._polite(client, "GET", SEARCH, params={"q": q, "format": "jsonv2", "polygon_geojson": 1, "limit": 1,
                                                        "polygon_threshold": 0.0001, "featureType": "settlement"}).json() or []
    if not got:
        got = places._polite(client, "GET", SEARCH, params={"q": q, "format": "jsonv2", "polygon_geojson": 1, "limit": 1, "polygon_threshold": 0.0001}).json() or []
    rings = _rings((got[0] if got else {}).get("geojson") or {})
    if not rings:
        raise ValueError(f"No boundary for {q}")
    lats = [p[0] for r in rings for p in r]
    lons = [p[1] for r in rings for p in r]
    bbox = f"{min(lats)},{min(lons)},{max(lats)},{max(lons)}"
    query = f'[out:json][timeout:60];way["highway"~"^({STREET_TYPES})$"]["name"]({bbox});out geom;'
    r = places._polite(client, "POST", places.OVERPASS[0], data={"data": query}, timeout=90)
    streets: dict[str, list[list[list[float]]]] = {}
    for el in r.json().get("elements") or []:
        geom = [(g["lat"], g["lon"]) for g in el.get("geometry") or []]
        name = (el.get("tags") or {}).get("name")
        if len(geom) < 2 or not name:
            continue
        mid = geom[len(geom) // 2]
        if not any(_inside(mid, ring) for ring in rings):
            continue
        streets.setdefault(name, []).append([[round(p[0], 6), round(p[1], 6)] for p in geom])
    return {"locality": locality, "region": region, "country": country, "boundary": [_thin(r, 300) for r in rings],
            "streets": streets, "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def _route_points(walks: list[dict[str, Any]], bounds: tuple[float, float, float, float]) -> list[list[float]]:
    s, w, n, e = bounds
    out: list[list[float]] = []
    for walk in walks:
        line = walk.get("line") or []
        if not line or max(p[0] for p in line) < s or min(p[0] for p in line) > n or max(p[1] for p in line) < w or min(p[1] for p in line) > e:
            continue
        try:
            pts = json.loads(service._route_path(walk["id"]).read_text(encoding="utf-8"))["points"]
        except (OSError, KeyError, ValueError):
            continue
        inside = [(p[0], p[1]) for p in pts if s <= p[0] <= n and w <= p[1] <= e]
        out += [[p[0], p[1]] for p in _densify(inside, STEP_M)] if len(inside) > 1 else [[p[0], p[1]] for p in inside]  # GPS gaps filled in
    return out


def coverage(doc: dict[str, Any], walks: list[dict[str, Any]]) -> dict[str, Any]:
    """Each street's length and how much of it you've walked."""
    lines = [seg for segs in doc["streets"].values() for seg in segs]
    if not lines:
        return {"streets": 0, "walked": 0, "km": 0.0, "km_walked": 0.0, "share": 0.0, "lines": []}
    lats = [p[0] for seg in lines for p in seg]
    lons = [p[1] for seg in lines for p in seg]
    pad = 0.001
    grid, lat0 = _grid(_route_points(walks, (min(lats) - pad, min(lons) - pad, max(lats) + pad, max(lons) + pad)))
    total = walked_m = 0.0
    walked_streets = 0
    out_lines = []
    for name, segs in doc["streets"].items():
        street_m = street_walked = 0.0
        for seg in segs:
            dense = _densify([(p[0], p[1]) for p in seg])
            hits = [_near(grid, lat0, p) if grid else False for p in dense]
            seg_m = _length_m(dense)
            share = sum(hits) / len(hits) if hits else 0
            street_m += seg_m
            street_walked += seg_m * share
            out_lines.append({"name": name, "line": seg, "walked": share >= 0.5})
        total += street_m
        walked_m += street_walked
        if street_m and street_walked / street_m >= 0.5:
            walked_streets += 1
    return {"streets": len(doc["streets"]), "walked": walked_streets, "km": round(total / 1000, 1), "km_walked": round(walked_m / 1000, 1),
            "share": round(walked_m / total, 3) if total else 0.0, "lines": out_lines}


def _stamp() -> Any:
    try:
        st = (service.root() / "index.json").stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def streets_overview() -> list[dict[str, Any]]:
    walks = service.load()["walks"]
    out = []
    for sub in suburbs(walks):
        item = {**sub, "ready": False}
        try:
            doc = json.loads(_street_file(sub["slug"]).read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError):
            out.append(item)
            continue
        cov = _coverage_cached(sub["slug"], doc, walks)
        out.append({**item, "ready": True, **{k: v for k, v in cov.items() if k != "lines"}, "fetched": doc.get("fetched")})
    return out


def _coverage_cached(slug: str, doc: dict[str, Any], walks: list[dict[str, Any]]) -> dict[str, Any]:
    key = (slug, _stamp(), doc.get("fetched"))
    if _cache.get(slug, {}).get("key") != key:
        _cache[slug] = {"key": key, "value": coverage(doc, walks)}
    return _cache[slug]["value"]


def streets_detail(slug: str) -> dict[str, Any]:
    doc = json.loads(_street_file(slug).read_text(encoding="utf-8"))
    cov = _coverage_cached(slug, doc, service.load()["walks"])
    return {"locality": doc["locality"], "region": doc.get("region"), "boundary": doc.get("boundary"), **cov}


def fetch_pending(now: datetime | None = None) -> int:
    """One suburb a run (Overpass is slow and shared): the first not fetched yet, or one REFRESH_DAYS old."""
    now = now or datetime.now(timezone.utc)
    for sub in suburbs(service.load()["walks"]):
        path = _street_file(sub["slug"])
        try:
            fetched = datetime.fromisoformat(json.loads(path.read_text(encoding="utf-8"))["fetched"])
            if now - fetched < timedelta(days=REFRESH_DAYS):
                continue
        except (OSError, ValueError, KeyError):
            pass
        with _client() as client:
            try:
                doc = fetch_streets(client, sub["locality"], sub["region"], sub["country"])
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                logger.info("Streets for %s failed: %s", sub["locality"], exc)
                return 0
        path.parent.mkdir(parents=True, exist_ok=True)
        json_store.write(path, doc)
        return 1
    return 0


# -- wishlist ------------------------------------------------------------------------------------------------------

def _wish_path() -> Path:
    return service.root() / "wishlist.json"


def load_wishes() -> list[dict[str, Any]]:
    raw = json_store.read(_wish_path(), {})
    return list((raw if isinstance(raw, dict) else {}).get("wishes") or [])


def _save_wishes(items: list[dict[str, Any]]) -> None:
    service.root().mkdir(parents=True, exist_ok=True)
    json_store.write(_wish_path(), {"wishes": items})


def _kind(hit: dict[str, Any]) -> str:
    cat, typ = hit.get("category") or hit.get("class"), hit.get("type")
    if cat == "natural" and typ in ("peak", "volcano", "hill", "saddle", "ridge"):
        return "peak"
    if cat in ("leisure", "boundary") and typ in ("park", "nature_reserve", "national_park", "protected_area"):
        return "park"
    if cat == "route" or typ in ("path", "footway", "track", "hiking", "foot"):
        return "track"
    return "place"


def search(q: str) -> list[dict[str, Any]]:
    from app.trails import places

    from app.trails import insights

    walks = service.load()["walks"]
    home = insights.home_country(walks, max((w["start"] for w in walks), default=None)) if walks else None
    params = {"q": q, "format": "jsonv2", "limit": 8, "addressdetails": 1}
    with _client() as client:
        # Where you live first (a "Cathedral Range" in Victoria before California's), then anywhere
        hits = places._polite(client, "GET", SEARCH, params={**params, "countrycodes": home.lower()}).json() or [] if home else []
        if len(hits) < 3:
            seen = {(h.get("osm_type"), h.get("osm_id")) for h in hits}
            hits += [h for h in places._polite(client, "GET", SEARCH, params=params).json() or [] if (h.get("osm_type"), h.get("osm_id")) not in seen]
    out = []
    seen_tracks: set[tuple[str, str]] = set()
    for h in hits:
        if h.get("osm_type") not in ("node", "way", "relation"):
            continue
        addr = h.get("address") or {}
        if _kind(h) == "track":  # a track's pieces are separate ways: one result for them (the whole track is found on adding)
            key = (h.get("name") or "", addr.get("state") or "")
            if key in seen_tracks:
                continue
            seen_tracks.add(key)
        where = ", ".join(x for x in (addr.get("state") or addr.get("region"), addr.get("country")) if x)
        out.append({"osm": f"{h['osm_type'][0].upper()}{h['osm_id']}", "name": h.get("name") or h.get("display_name", "").split(",")[0],
                    "kind": _kind(h), "where": where, "lat": float(h["lat"]), "lon": float(h["lon"])})
    return out


def _climb(client: httpx.Client, line: list[list[float]]) -> tuple[int | None, int | None]:
    """Ascent and highest point along a line, from Open-Meteo's elevation service (100 points at most)."""
    if len(line) < 2:
        return None, None
    step = max(1, len(line) // 100)
    pts = line[::step][:100]
    r = client.get(ELEVATION, params={"latitude": ",".join(f"{p[0]:.5f}" for p in pts), "longitude": ",".join(f"{p[1]:.5f}" for p in pts)})
    r.raise_for_status()
    eles = r.json().get("elevation") or []
    up, _ = service.climb(eles)
    return (int(up), int(max(eles))) if eles else (None, None)


def _whole_track(client: httpx.Client, osm: str, hit: dict[str, Any]) -> list[list[tuple[float, float]]] | None:
    """A track piece (a way) stands for the whole track: the hiking route it's part of, else every way with its name
    within TRACK_KM. From Overpass; None when that can't be reached (the piece is used)."""
    from app.trails import places

    way = osm[1:]
    name = (hit.get("name") or "").replace("\\", "").replace('"', "")
    query = (f'[out:json][timeout:60];way({way})->.w;(rel(bw.w)["route"~"^(hiking|foot|walking)$"];)->.r;.r out geom;'
             f'way(id:{way});way(around:{TRACK_KM * 1000})["name"="{name}"]["highway"];out geom;')
    els = None
    for server in places.OVERPASS:  # the main server is often busy: then its mirror
        try:
            els = places._polite(client, "POST", server, data={"data": query}, timeout=90).json().get("elements") or []
            break
        except (httpx.HTTPError, ValueError) as exc:
            logger.info("Overpass (%s) for %s failed: %s", server, osm, exc)
    if els is None:
        return None
    rels = [e for e in els if e["type"] == "relation"]
    if rels:
        rel = max(rels, key=lambda e: len(e.get("members") or []))
        return [[(g["lat"], g["lon"]) for g in m["geometry"]] for m in rel.get("members") or [] if m.get("type") == "way" and len(m.get("geometry") or []) > 1] or None
    ways = [[(g["lat"], g["lon"]) for g in e.get("geometry") or []] for e in els if e["type"] == "way"]
    return [w for w in ways if len(w) > 1] or None


def add_wish(osm: str) -> dict[str, Any]:
    from app.trails import places

    if not re.fullmatch(r"[NWR]\d{1,12}", osm or ""):
        raise ValueError("That isn't an OpenStreetMap place.")
    items = load_wishes()
    if any(w["osm"] == osm for w in items):
        raise ValueError("That's already on your wishlist.")
    with _client() as client:
        got = places._polite(client, "GET", LOOKUP, params={"osm_ids": osm, "format": "jsonv2", "polygon_geojson": 1,
                                                            "polygon_threshold": 0.00005, "addressdetails": 1}).json() or []
        if not got:
            raise ValueError("OpenStreetMap doesn't know that place.")
        h = got[0]
        geo = h.get("geojson") or {}
        whole = _whole_track(client, osm, h) if osm.startswith("W") and _kind(h) == "track" else None
        pending = osm.startswith("W") and _kind(h) == "track" and whole is None  # Overpass busy: the whole track is found later
        pieces = whole or _lines(geo)
        lines = [_thin(l, max(20, 1500 // max(1, len(pieces)))) for l in pieces]
        rings = [_thin(r, 300) for r in _rings(geo)]
        kind = _kind(h)
        length = round(sum(_length_m([(p[0], p[1]) for p in l]) for l in lines) / 1000, 1) if lines else None
        try:
            ascent, highest = _climb(client, [p for l in lines for p in l]) if lines else _climb(client, [[float(h["lat"]), float(h["lon"])]] * 2)
        except (httpx.HTTPError, ValueError):
            ascent, highest = None, None
    addr = h.get("address") or {}
    wish = {"id": "x_" + secrets.token_hex(5), "osm": osm, "name": h.get("name") or h.get("display_name", "").split(",")[0], "kind": kind,
            "where": ", ".join(x for x in (addr.get("state") or addr.get("region"), addr.get("country")) if x),
            "center": [float(h["lat"]), float(h["lon"])], "lines": lines, "area": rings, "km": length,
            "ascent_m": ascent if lines else None, "highest_m": highest, "added": datetime.now(timezone.utc).isoformat(timespec="seconds"), "done": None,
            **({"whole_pending": 1} if pending else {})}
    with _lock:
        items = load_wishes()
        items.append(wish)
        _save_wishes(items)
    tick()
    return next(w for w in load_wishes() if w["id"] == wish["id"])


def _shape(client: httpx.Client, pieces: list[list[tuple[float, float]]]) -> dict[str, Any]:
    lines = [_thin(l, max(20, 1500 // max(1, len(pieces)))) for l in pieces]
    try:
        ascent, highest = _climb(client, [p for l in lines for p in l])
    except (httpx.HTTPError, ValueError):
        ascent, highest = None, None
    return {"lines": lines, "km": round(sum(_length_m([(p[0], p[1]) for p in l]) for l in lines) / 1000, 1), "ascent_m": ascent, "highest_m": highest}


def complete_pending() -> int:
    """Tracks added while Overpass was busy: look up the whole track again (a few tries, then the piece stands)."""
    todo = [w for w in load_wishes() if w.get("whole_pending")]
    done = 0
    for wish in todo:
        with _client() as client:
            whole = _whole_track(client, wish["osm"], {"name": wish["name"]})
            shape = _shape(client, whole) if whole else None
        with _lock:
            items = load_wishes()
            for w in items:
                if w["id"] == wish["id"]:
                    if shape:
                        w.update(shape)
                        w.pop("whole_pending", None)
                        done += 1
                    else:
                        w["whole_pending"] = w["whole_pending"] + 1
                        if w["whole_pending"] > 6:
                            w.pop("whole_pending", None)
            _save_wishes(items)
    if done:
        tick()
    return done


def remove_wish(wish_id: str) -> None:
    with _lock:
        items = load_wishes()
        if not any(w["id"] == wish_id for w in items):
            raise KeyError(wish_id)
        _save_wishes([w for w in items if w["id"] != wish_id])


def done_by(wish: dict[str, Any], walk: dict[str, Any], points: list[list[float]]) -> bool:
    if not points:
        return False
    if wish.get("lines"):
        grid, lat0 = _grid([[p[0], p[1]] for p in _densify([(q[0], q[1]) for q in points], STEP_M)], 50.0)
        dense = [p for l in wish["lines"] for p in _densify([(q[0], q[1]) for q in l], 50.0)]
        return bool(dense) and sum(_near(grid, lat0, p, 50.0) for p in dense) / len(dense) >= WISH_SHARE
    if wish.get("area"):
        sample = points[:: max(1, len(points) // 60)]
        return sum(any(_inside((p[0], p[1]), [tuple(q) for q in ring]) for ring in wish["area"]) for p in sample) / len(sample) >= 0.5
    c = wish["center"]
    return any(service.haversine((c[0], c[1]), (p[0], p[1])) <= WISH_POINT_M for p in points[:: max(1, len(points) // 400)])


def tick() -> int:
    """Tick off wishes a walk has now done (the earliest walk after it was added, or any walk before)."""
    with _lock:
        items = load_wishes()
        open_ = [w for w in items if not w.get("done")]
        if not open_:
            return 0
        walks = sorted(service.load()["walks"], key=lambda w: w["start"])
        ticked = 0
        for wish in open_:
            c = wish["center"]
            for walk in walks:
                line = walk.get("line") or []
                if not line or min(service.haversine((c[0], c[1]), (p[0], p[1])) for p in line[:: max(1, len(line) // 50)]) > 30000:
                    continue
                try:
                    pts = json.loads(service._route_path(walk["id"]).read_text(encoding="utf-8"))["points"]
                except (OSError, KeyError, ValueError):
                    continue
                if done_by(wish, walk, pts):
                    wish["done"] = {"walk": walk["id"], "name": walk["name"], "start": walk["start"]}
                    ticked += 1
                    break
        if ticked:
            _save_wishes(items)
        return ticked


# -- Home ----------------------------------------------------------------------------------------------------------

def home_card(today: datetime | None = None) -> dict[str, Any] | None:
    """12.6: the last walk and this year so far, for the Home card."""
    walks = service.load()["walks"]
    if not walks:
        return None
    today = today or datetime.now(timezone.utc)
    year = [w for w in walks if w["start"][:4] == str(today.year)]
    latest = service.with_tz(max(walks, key=lambda w: w["start"]))
    from app.trails import insights

    group = next((g for g in insights.repeats_cached(walks, service._stamp()) if any(t["id"] == latest["id"] for t in g["times"])), None)
    month = [w for w in walks if datetime.fromisoformat(w["start"]) >= today - timedelta(days=30)]
    wishes = load_wishes()
    return {"latest": {k: latest.get(k) for k in ("id", "name", "kind", "start", "tz", "km", "minutes", "ascent_m", "place", "weather")}
                      | {"times": group["count"] if group else None, "best": bool(group and group["fastest"] and group["fastest"]["id"] == latest["id"])},
            "year": {"year": today.year, "walks": len(year), "km": round(sum(w.get("km") or 0 for w in year), 1),
                     "hours": round(sum(w.get("minutes") or 0 for w in year) / 60, 1), "ascent_m": round(sum(w.get("ascent_m") or 0 for w in year))},
            "last_30_days": {"walks": len(month), "km": round(sum(w.get("km") or 0 for w in month), 1)},
            "wishlist": {"open": sum(1 for w in wishes if not w.get("done")), "done": sum(1 for w in wishes if w.get("done"))}}


def month_recap(ym: str) -> dict[str, Any] | None:
    """12.6: a month's walks for the monthly recap: count, distance, climb, new places, against the month before."""
    walks = service.load()["walks"]
    month = [w for w in walks if w["start"][:7] == ym]
    y, m = int(ym[:4]), int(ym[5:7])
    prev = f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"
    before = sum(1 for w in walks if w["start"][:7] == prev)
    if not month and not before:
        return None
    earlier = {(w.get("landmarks") or {}).get("locality") for w in walks if w["start"][:7] < ym}
    new_places = sorted({(w.get("landmarks") or {}).get("locality") for w in month} - earlier - {None})
    longest = max(month, key=lambda w: w.get("km") or 0, default=None)
    return {"walks": len(month), "hikes": sum(w["kind"] == "hike" for w in month), "before": before,
            "km": round(sum(w.get("km") or 0 for w in month), 1), "ascent_m": round(sum(w.get("ascent_m") or 0 for w in month)),
            "longest": {"name": longest["name"], "km": longest.get("km")} if longest else None, "new_places": new_places[:5]}


def facts(today: datetime, start: str, end: str, q: str | None = None) -> dict[str, Any]:
    """12.6: walks for SirisAI's sirisos_facts (topic 'walks'): in a period, or the ones matching q (a name or place)."""
    walks = service.load()["walks"]
    if q:
        needle = q.lower()
        found = [w for w in walks if needle in (w.get("name") or "").lower() or needle in (w.get("place") or "").lower()
                 or any(needle in (v or "").lower() for v in (w.get("landmarks") or {}).values())]
    else:
        found = [w for w in walks if start <= w["start"][:10] <= end]
    found.sort(key=lambda w: w["start"], reverse=True)

    def row(w: dict[str, Any]) -> dict[str, Any]:
        wx = w.get("weather") or {}
        return {"name": w["name"], "date": w["start"][:10], "kind": w["kind"], "km": w.get("km"), "minutes": w.get("minutes"),
                "ascent_m": w.get("ascent_m"), "place": w.get("place"), "weather": f"{wx.get('sky', '')} {round(wx['temp_c'])}°C".strip() if wx.get("temp_c") is not None else None}

    return {"walks": [row(w) for w in found[:20]], "count": len(found), "km": round(sum(w.get("km") or 0 for w in found), 1),
            "hours": round(sum(w.get("minutes") or 0 for w in found) / 60, 1), "ascent_m": round(sum(w.get("ascent_m") or 0 for w in found)),
            "all_time": {"walks": len(walks), "km": round(sum(w.get("km") or 0 for w in walks), 1)},
            "matched": q or None, "from": None if q else start, "to": None if q else end}
