"""Is SirisAI answering? (7.0) It can hang with its container up, and then chat,
voice, protocols and health all stop with nothing to say why. Once a minute
this asks it for its attention feed (a route that runs on its worker threads,
so a jam shows up, where a bare status check would still answer). No answer for
three minutes puts one alert in the Inbox, which notifications then send once.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from app.hub import sirisai_api
from app.hub.service import Hub, shared_client, test_mode

logger = logging.getLogger(__name__)

EVERY_S = 60
ALERT_AFTER_S = 180
TIMEOUT_S = 15.0

_silent_since: datetime | None = None


def enabled() -> bool:
    return os.getenv("SIRISOS_WATCH", "1") not in ("0", "false", "no") and not test_mode()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def record(answered: bool, now: datetime | None = None) -> None:
    global _silent_since
    if answered:
        _silent_since = None
    elif _silent_since is None:
        _silent_since = now or _now()


async def answering(hub: Hub) -> bool:
    c = sirisai_api.connector(hub)
    if c is None:
        return True  # not set up isn't the same as not answering
    try:
        r = await shared_client().get(f"{c.base_url}/siris/hub/v1/attention", headers=c.headers(), timeout=TIMEOUT_S)
    except httpx.HTTPError:
        return False
    return r.status_code < 500


def items(now: datetime | None = None) -> list[dict[str, Any]]:
    if _silent_since is None:
        return []
    gone = ((now or _now()) - _silent_since).total_seconds()
    if gone < ALERT_AFTER_S:
        return []
    return [{
        "key": f"sirisai:silent:{_silent_since.isoformat(timespec='minutes')}",
        "kind": "alert",
        "severity": "attention",
        "title": "SirisAI isn't answering",
        "body": f"No reply for {round(gone / 60)} minutes. Chat, voice, protocols and health wait on it. If it doesn't come back, restart its container.",
        "source": "hub",
        "app": "SirisAI",
        "url": "/status",
    }]


async def loop(get_hub: Any) -> None:
    while True:
        try:
            record(await answering(get_hub()))
        except Exception as exc:  # noqa: BLE001 - keep watching
            logger.warning("SirisAI watch failed: %s", exc)
        await asyncio.sleep(EVERY_S)
