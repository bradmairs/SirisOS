"""SirisAI's guest mode, as SirisOS sees it (ADR 110): while visitors may be
looking at the screen, the widgets that show personal things -- SirisAI's
"Today" (the calendar) and the Second Brain's "Learned today" -- are left
off the home screen, as SirisAI already leaves them out of its own answers.
Asked of SirisAI at most every 30 seconds; unknown (SirisAI down, or too old
to say) counts as off."""

from __future__ import annotations

import time

from app.hub.connectors.sirisai import SirisAIConnector
from app.hub.service import Hub, shared_client

PERSONAL_WIDGETS = {"sirisai", "second-brain"}
CACHE_SECONDS = 30.0

_cache: tuple[float, bool] | None = None


def reset() -> None:
    global _cache
    _cache = None


async def guest_mode(hub: Hub) -> bool:
    global _cache
    if _cache and time.monotonic() - _cache[0] < CACHE_SECONDS:
        return _cache[1]
    connector = hub.get("sirisai")
    on = False
    if isinstance(connector, SirisAIConnector) and connector.configured:
        try:
            response = await shared_client().get(f"{connector.base_url}/siris/hub/v1", headers=connector.headers(), timeout=4.0)
            on = response.status_code == 200 and bool(response.json().get("guest_mode"))
        except Exception:  # noqa: BLE001 - unknown means off
            on = False
    _cache = (time.monotonic(), on)
    return on


def hide_personal(apps: list[dict]) -> list[dict]:
    return [{**a, "widget": None} if a.get("id") in PERSONAL_WIDGETS else a for a in apps]
