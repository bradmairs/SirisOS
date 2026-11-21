"""What to watch tonight (10.4), and new episodes this week.

From SirisAI (7.3's /siris/hub/v1/watch): what you're part-way through on Plex, what's new and unwatched, and
Sonarr's episodes and Radarr's films coming in the next week. Tonight's picks fit the time before bed (Health's
bedtime, else 10:30pm): carry on with what you're watching first; a film only when there's two hours or more.
On Home from 6pm.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from app.hub import sirisai_api
from app.hub.service import Hub

FILM_MINUTES = 120
DEFAULT_BED = "22:30"


async def tonight(hub: Hub, local_now: datetime) -> dict[str, Any]:
    from app.health import service as health

    body = await sirisai_api.get(hub, "/siris/hub/v1/watch", timeout=20.0)
    if not isinstance(body, dict) or body.get("guest_mode"):
        return {"available": False}
    bed = DEFAULT_BED
    try:
        b = str(((await health.overview(hub)).get("bedtime") or {}).get("bedtime") or "")
        if re.fullmatch(r"\d{1,2}:\d{2}", b[:5]):
            bed = b[:5]
    except Exception:  # noqa: BLE001
        pass
    h, m = (int(x) for x in bed.split(":"))
    bedtime = local_now.replace(hour=h, minute=m, second=0, microsecond=0)
    if bedtime < local_now - timedelta(hours=3):
        bedtime += timedelta(days=1)
    minutes = max(0, int((bedtime - local_now).total_seconds() // 60))
    deck = body.get("on_deck") or []
    new = body.get("new_unwatched") or []
    picks: list[dict[str, Any]] = []
    if deck:
        picks.append({**deck[0], "why": "Carry on where you left off"})
    films = [n for n in new if n.get("type") == "movie"]
    shows = [n for n in new if n.get("type") != "movie" and not any(p.get("show") and p.get("show") == n.get("show") for p in picks)]
    if minutes >= FILM_MINUTES and films:
        picks.append({**films[0], "why": f"A film fits: {minutes // 60} h {minutes % 60:02d} before bed"})
    if shows:
        picks.append({**shows[0], "why": "New and not watched yet"})
    return {"available": True, "minutes_to_bed": minutes, "bedtime": bed, "picks": picks[:3], "on_deck": deck, "new_unwatched": new,
            "episodes": body.get("episodes"), "movies": body.get("movies"), "plex": body.get("on_deck") is not None}
