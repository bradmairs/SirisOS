"""Moving SirisOS's old health store into SirisAI (5.8).

From 5.7 SirisOS kept everything Health Auto Export sent in
`health-days.json`, beside SirisAI's eight metrics. Since 5.8 SirisAI keeps
it all (SirisAI 3.51), so on first use the old file is sent across in
SirisAI's own shape, a few months at a time, tagged as source "sirisos" (so a
day Health Auto Export already gave SirisAI keeps that value). Once every part
is in, the file is renamed `health-days.migrated.json` and kept as a backup.
A failure leaves it in place and tries again after an hour.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.hub import sirisai_api
from app.hub.service import Hub
from app.services import json_store

logger = logging.getLogger(__name__)

CHUNK_DAYS = 120
RETRY_SECONDS = 3600
_lock = asyncio.Lock()
_last_try = 0.0


def _path():
    return json_store.data_path("SIRISOS_HEALTH_PATH", "health-days.json")


def pending() -> bool:
    return _path().exists()


async def ensure(hub: Hub) -> dict[str, Any] | None:
    """Send the old store across if it's still here. Returns what was sent,
    None when there was nothing to do (or it isn't time to retry)."""
    global _last_try
    if not pending() or time.monotonic() - _last_try < RETRY_SECONDS and _last_try:
        return None
    async with _lock:
        if not pending():
            return None
        _last_try = time.monotonic()
        doc = json_store.read(_path(), {})
        doc = doc if isinstance(doc, dict) else {}
        metrics, sleep, workouts = doc.get("metrics") or {}, doc.get("sleep") or {}, doc.get("workouts") or {}
        days = sorted(set(metrics) | set(sleep) | set(workouts))
        try:
            for i in range(0, len(days), CHUNK_DAYS):
                part = days[i:i + CHUNK_DAYS]
                body = {"metrics": {d: metrics[d] for d in part if d in metrics},
                        "sleep": {d: sleep[d] for d in part if d in sleep},
                        "workouts": {d: workouts[d] for d in part if d in workouts}}
                if not body["metrics"]:
                    body["metrics"] = {part[0]: {}}  # the shape needs a metrics block
                await sirisai_api.post(hub, "/siris/health/metrics", json=body, headers={"X-Health-Source": "sirisos"}, timeout=120.0)
        except sirisai_api.SirisAIError as exc:
            logger.warning("Moving health history to SirisAI failed (will retry): %s", exc)
            return {"moved": False, "error": str(exc)}
        _path().rename(_path().with_name("health-days.migrated.json"))
        logger.info("Moved %d days of health history to SirisAI", len(days))
        return {"moved": True, "days": len(days)}
