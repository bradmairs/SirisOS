"""Each app's health over time, for the System status page.

Every status check is recorded (at most one sample per app every 4 minutes,
so a busy Home screen doesn't flood it), and a background sampler checks
every configured app every 5 minutes so there's history even when nobody
has SirisOS open. Seven days are kept, in the data directory.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any

from app.services import json_store

logger = logging.getLogger(__name__)

KEEP_SECONDS = 7 * 24 * 3600
MIN_GAP_SECONDS = 240
SAMPLE_EVERY_SECONDS = 300
CODES = {"ok": 0, "degraded": 1, "down": 2}
NAMES = {v: k for k, v in CODES.items()}

_lock = threading.Lock()
_samples: dict[str, list[list[Any]]] | None = None  # app id -> [[t, code, latency_ms, detail]]


def _path():
    return json_store.data_path("SIRISOS_STATUS_HISTORY_PATH", "status-history.json")


def _load() -> dict[str, list[list[Any]]]:
    global _samples
    if _samples is None:
        raw = json_store.read(_path(), {})
        _samples = {k: v for k, v in raw.items() if isinstance(v, list)} if isinstance(raw, dict) else {}
    return _samples


def reset() -> None:
    """Forget the in-memory copy (tests)."""
    global _samples
    _samples = None


def record(app_id: str, status: dict[str, Any], now: float | None = None) -> bool:
    """Keep one sample; False when it was too soon after the last one (unless the state changed)."""
    state = status.get("state")
    if state not in CODES:
        return False
    now = now if now is not None else time.time()
    with _lock:
        samples = _load().setdefault(app_id, [])
        if samples and now - samples[-1][0] < MIN_GAP_SECONDS and samples[-1][1] == CODES[state]:
            return False
        detail = str(status.get("detail") or "")[:160] if state != "ok" else ""
        samples.append([round(now), CODES[state], status.get("latency_ms"), detail])
        cutoff = now - KEEP_SECONDS
        while samples and samples[0][0] < cutoff:
            samples.pop(0)
        try:
            json_store.write(_path(), _load())
        except OSError as exc:
            logger.warning("Couldn't save status history: %s", exc)
    return True


def _bucket_states(samples: list[list[Any]], start: float, width: float, count: int) -> list[str | None]:
    out: list[str | None] = []
    for i in range(count):
        lo, hi = start + i * width, start + (i + 1) * width
        codes = [s[1] for s in samples if lo <= s[0] < hi]
        out.append(NAMES[max(codes)] if codes else None)
    return out


def summary(app_id: str, now: float | None = None) -> dict[str, Any]:
    now = now if now is not None else time.time()
    with _lock:
        samples = list(_load().get(app_id, []))

    def uptime(seconds: float) -> float | None:
        window = [s for s in samples if s[0] >= now - seconds]
        return round(100 * sum(1 for s in window if s[1] < 2) / len(window), 1) if window else None

    day = [s for s in samples if s[0] >= now - 86400]
    latencies = [s[2] for s in day if isinstance(s[2], (int, float)) and s[1] < 2]
    incidents = []
    previous = None
    for s in samples:
        if s[1] == 2 and previous != 2:
            incidents.append({"at": s[0], "detail": s[3] or "Down"})
        previous = s[1]
    if incidents:
        # How long each lasted: until the next sample that wasn't down.
        for incident in incidents:
            back = next((s[0] for s in samples if s[0] > incident["at"] and s[1] < 2), None)
            incident["minutes"] = round((back - incident["at"]) / 60) if back else None
    last_bad = next((s for s in reversed(samples) if s[1] > 0), None)
    return {
        "samples": len(samples),
        "uptime_24h": uptime(86400),
        "uptime_7d": uptime(KEEP_SECONDS),
        "latency_ms_24h": round(sum(latencies) / len(latencies)) if latencies else None,
        "hours": _bucket_states(samples, now - 86400, 3600, 24),
        "days": _bucket_states(samples, now - 7 * 86400, 86400, 7),
        "last_problem": {"at": last_bad[0], "state": NAMES[last_bad[1]], "detail": last_bad[3]} if last_bad else None,
        "incidents": list(reversed(incidents))[:5],
    }


async def sampler(hub_getter) -> None:  # noqa: ANN001 - a function returning the Hub
    """Check every configured app every 5 minutes (fresh), so history has no gaps overnight."""
    while True:
        await asyncio.sleep(SAMPLE_EVERY_SECONDS)
        try:
            hub = hub_getter()
            await asyncio.gather(*(hub.status(c, fresh=True) for c in hub.connectors if c.configured and not c.launch_only))
        except Exception as exc:  # noqa: BLE001 - keep sampling
            logger.warning("Status sampler failed: %s", exc)
