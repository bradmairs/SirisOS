"""What your walks add up to (12.4): the routes you repeat, the peaks and parks you've been to, and your trips away.

- **Routes you repeat**: two walks are the same route when their lengths are within LENGTH_SHARE of each other and
  every part of each one is close to the other (on average within SAME_M), whichever way round or wherever on a loop
  you started. Each route has its count, its fastest time and how each time went.
- **Peaks, parks and tracks**: from the names OpenStreetMap gave each walk (places.py).
- **Trips**: home is where most walks start. Walks more than AWAY_KM from it, a few days apart at most and in the same
  country, are one trip ("Hong Kong, Nov 2025"). When Travel has a trip over the same days, it's linked.

Worked out from index.json each time it changes; nothing is stored.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any

LENGTH_SHARE = 0.15
SAME_M = 120.0
RESAMPLE = 40
AWAY_KM = 80.0
TRIP_GAP_DAYS = 4
HOME_CELL = 0.05  # degrees: about 5 km
HOME_YEARS = 1
_cache: dict[str, Any] = {}


def _xy(p: list[float], lat0: float) -> tuple[float, float]:
    return p[1] * 111320 * math.cos(math.radians(lat0)), p[0] * 110540


def resample(line: list[list[float]], n: int = RESAMPLE, lat0: float | None = None) -> list[tuple[float, float]]:
    """n points evenly along the line, in metres on a flat grid at latitude lat0 (the line's start by default)."""
    if len(line) < 2:
        return []
    lat0 = line[0][0] if lat0 is None else lat0
    pts = [_xy(p, lat0) for p in line]
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = cum[-1] or 1.0
    out, j = [], 0
    for k in range(n):
        target = total * k / (n - 1)
        while j < len(cum) - 2 and cum[j + 1] < target:
            j += 1
        seg = (cum[j + 1] - cum[j]) or 1.0
        t = (target - cum[j]) / seg
        out.append((pts[j][0] + t * (pts[j + 1][0] - pts[j][0]), pts[j][1] + t * (pts[j + 1][1] - pts[j][1])))
    return out


def _closeness(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    """The average distance from each point of a to the nearest of b, and the other way: 0 for the same route."""
    def one_way(x: list[tuple[float, float]], y: list[tuple[float, float]]) -> float:
        return sum(min(math.hypot(p[0] - q[0], p[1] - q[1]) for q in y) for p in x) / len(x)

    return max(one_way(a, b), one_way(b, a))


def same_route(a: dict[str, Any], b: dict[str, Any]) -> bool:
    ka, kb = a.get("km") or 0, b.get("km") or 0
    if not ka or not kb or abs(ka - kb) > LENGTH_SHARE * max(ka, kb):
        return False
    la, lb = a.get("line") or [], b.get("line") or []
    if len(la) < 2 or len(lb) < 2:
        return False
    # Quick no: their boxes don't overlap.
    if (max(p[0] for p in la) < min(p[0] for p in lb) or max(p[0] for p in lb) < min(p[0] for p in la)
            or max(p[1] for p in la) < min(p[1] for p in lb) or max(p[1] for p in lb) < min(p[1] for p in la)):
        return False
    lat0 = la[0][0]  # both on the same grid
    return _closeness(resample(la, lat0=lat0), resample(lb, lat0=lat0)) <= SAME_M


def repeats(walks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Groups of two or more walks along the same route, most walked first."""
    parent = {w["id"]: w["id"] for w in walks}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(walks):
        for b in walks[i + 1:]:
            if find(a["id"]) != find(b["id"]) and same_route(a, b):
                parent[find(a["id"])] = find(b["id"])
    groups: dict[str, list[dict[str, Any]]] = {}
    for w in walks:
        groups.setdefault(find(w["id"]), []).append(w)
    out = []
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda w: w["start"])
        timed = [w for w in members if w.get("minutes")]
        fastest = min(timed, key=lambda w: w["minutes"]) if timed else None
        names = Counter(w["name"] for w in members)
        out.append({"id": members[0]["id"], "name": names.most_common(1)[0][0], "count": len(members),
                    "km": round(sum(w.get("km") or 0 for w in members) / len(members), 1),
                    "fastest": {"id": fastest["id"], "minutes": fastest["minutes"], "start": fastest["start"]} if fastest else None,
                    "latest": members[-1]["id"],
                    "times": [{"id": w["id"], "start": w["start"], "minutes": w.get("minutes"), "pace": w.get("pace_min_per_km")} for w in members]})
    out.sort(key=lambda g: (-g["count"], g["name"]))
    return out


def landmarks(walks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Each named peak, park and track, with the walks that went there (newest first)."""
    out: dict[str, dict[str, dict[str, Any]]] = {"peaks": {}, "parks": {}, "trails": {}}
    for w in sorted(walks, key=lambda w: w["start"], reverse=True):
        marks = w.get("landmarks") or {}
        for key, group in (("peak", "peaks"), ("park", "parks"), ("trail", "trails")):
            name = marks.get(key)
            if not name:
                continue
            item = out[group].setdefault(name, {"name": name, "count": 0, "walks": [], "first": w["start"], "last": w["start"],
                                                "place": w.get("place"), "country_code": w.get("country_code"), "highest_m": None})
            item["count"] += 1
            item["walks"].append(w["id"])
            item["first"] = min(item["first"], w["start"])
            if key == "peak" and w.get("highest_m") is not None:
                item["highest_m"] = max(item["highest_m"] or 0, w["highest_m"])
    return {g: sorted(items.values(), key=lambda x: (-x["count"], x["name"])) for g, items in out.items()}


def _km(a: list[float], b: list[float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(min(1.0, math.sqrt(h)))


def _cell(p: list[float]) -> tuple[int, int]:
    return round(p[0] / HOME_CELL), round(p[1] / HOME_CELL)


def home(walks: list[dict[str, Any]], when: str | None = None) -> list[float] | None:
    """The middle of the 5 km square where most walks start: of the walks within HOME_YEARS of `when` (people move:
    home in 2020 isn't home now), else of them all."""
    have = [w for w in walks if w.get("start_point")]
    if when:
        at = datetime.fromisoformat(when)
        near_in_time = [w for w in have if abs((datetime.fromisoformat(w["start"]) - at).days) <= 365 * HOME_YEARS]
        have = near_in_time or have
    cells = Counter(_cell(w["start_point"]) for w in have)
    if not cells:
        return None
    best = cells.most_common(1)[0][0]
    near = [w for w in have if _cell(w["start_point"]) == best]
    return [sum(w["start_point"][0] for w in near) / len(near), sum(w["start_point"][1] for w in near) / len(near)]


def home_country(walks: list[dict[str, Any]], when: str | None = None) -> str | None:
    """The country of home then."""
    base = home(walks, when)
    if base is None:
        return None
    codes = Counter(w.get("country_code") for w in walks if w.get("start_point") and w.get("country_code") and _km(base, w["start_point"]) <= AWAY_KM)
    return codes.most_common(1)[0][0] if codes else None


def _month(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%b %Y")


def trips(walks: list[dict[str, Any]], travel: list[dict[str, Any]] | None = None, everything: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Walks away from home, grouped into trips, newest first. Home is worked out from `everything` (all years)."""
    pool = everything or walks
    if not pool:
        return []
    homes: dict[str, list[float] | None] = {}
    for w in walks:
        key = w["start"][:7]  # home by the month: the same for every walk in it
        if key not in homes:
            homes[key] = home(pool, w["start"])
    away = sorted((w for w in walks if w.get("start_point") and homes[w["start"][:7]] and _km(homes[w["start"][:7]], w["start_point"]) > AWAY_KM),
                  key=lambda w: w["start"])
    groups: list[list[dict[str, Any]]] = []
    for w in away:
        last = groups[-1][-1] if groups else None
        if last and w.get("country_code") == last.get("country_code") and \
                datetime.fromisoformat(w["start"]) - datetime.fromisoformat(last["start"]) <= timedelta(days=TRIP_GAP_DAYS):
            groups[-1].append(w)
        else:
            groups.append([w])
    out = []
    for g in groups:
        regions = Counter(w.get("region") for w in g if w.get("region"))
        towns = Counter((w.get("landmarks") or {}).get("locality") for w in g if (w.get("landmarks") or {}).get("locality"))
        country = g[0].get("country")
        abroad = bool(g[0].get("country_code") and g[0].get("country_code") != home_country(pool, g[0]["start"]))
        if abroad:  # overseas: its one state ("Tokyo, Japan"), or the country when it went further
            place = f"{next(iter(regions))}, {country}" if len(regions) == 1 and country else country
        elif len(towns) == 1:  # at home: the town ("Lorne"), else the state
            place = next(iter(towns))
        else:
            place = regions.most_common(1)[0][0] if regions else country
        place = place or country or "Away"
        first, last = g[0]["start"][:10], g[-1]["start"][:10]
        trip = {"id": g[0]["id"], "name": f"{place}, {_month(g[0]['start'])}", "place": place, "country": country,
                "country_code": g[0].get("country_code"), "from": first, "to": last, "walks": [w["id"] for w in g], "count": len(g),
                "hikes": sum(w["kind"] == "hike" for w in g), "km": round(sum(w.get("km") or 0 for w in g), 1),
                "hours": round(sum(w.get("minutes") or 0 for w in g) / 60, 1), "ascent_m": round(sum(w.get("ascent_m") or 0 for w in g))}
        for t in travel or []:  # SirisOS Travel's trip over the same days
            try:
                if date.fromisoformat(t["start"]) - timedelta(days=1) <= date.fromisoformat(first) and date.fromisoformat(last) <= date.fromisoformat(t["end"]) + timedelta(days=1):
                    trip["travel"] = {"id": t["id"], "destination": t.get("destination") or t.get("place") or ""}
                    break
            except (KeyError, TypeError, ValueError):
                continue
        out.append(trip)
    return list(reversed(out))


def weather_records(walks: list[dict[str, Any]]) -> dict[str, Any]:
    def best(key: str, low: bool = False) -> dict[str, Any] | None:
        have = [w for w in walks if (w.get("weather") or {}).get(key) is not None]
        if not have:
            return None
        w = (min if low else max)(have, key=lambda w: w["weather"][key])
        if not low and key == "rain_mm" and not w["weather"][key]:
            return None
        return {"id": w["id"], "name": w["name"], "value": w["weather"][key], "start": w["start"]}

    return {"hottest": best("temp_max_c"), "coldest": best("temp_min_c", low=True), "wettest": best("rain_mm"), "windiest": best("gust_kmh")}


def repeats_cached(walks: list[dict[str, Any]], stamp: Any) -> list[dict[str, Any]]:
    """The pairwise route comparison is the slow part: kept until index.json changes."""
    if _cache.get("stamp") != stamp:
        _cache.update(stamp=stamp, repeats=repeats(walks))
    return _cache["repeats"]
