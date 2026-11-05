"""The live checks (app/verify.py), every morning (7.0). They change nothing and
send nothing. What's broken goes to the Inbox and to your phone; what's only worth
a look goes to the Inbox quietly, and stays dismissed until that list changes.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from app.hub.service import test_mode
from app.services import json_store

logger = logging.getLogger(__name__)

HOUR = 5  # local time: after the night's backup and Siris' dream
CHECK_EVERY_S = 300
FIRST_WAIT_S = 120


def enabled() -> bool:
    return os.getenv("SIRISOS_SELFTEST", "1") not in ("0", "false", "no") and not test_mode()


def _path():
    return json_store.data_path("SIRISOS_SELFTEST_PATH", "selftest.json")


def last() -> dict[str, Any] | None:
    found = json_store.read(_path(), None)
    return found if isinstance(found, dict) else None


def summarise(results: list[Any], day: str, at: str) -> dict[str, Any]:
    pick = lambda state: [{"name": r.name, "detail": r.detail} for r in results if r.state == state]  # noqa: E731
    return {"day": day, "at": at, "ok": sum(1 for r in results if r.state == "ok"), "broken": pick("fail"), "look": pick("warn")}


async def run_once(day: str) -> dict[str, Any]:
    from app import verify

    args = argparse.Namespace(ea=None, push=False)
    async with httpx.AsyncClient(base_url=os.getenv("SIRISOS_VERIFY_API", "http://127.0.0.1:8000"), timeout=20.0) as api:
        results = await verify.run(args, api)
    out = summarise(results, day, datetime.now(timezone.utc).isoformat(timespec="seconds"))
    json_store.write(_path(), out)
    return out


def due(now_local: datetime, saved: dict[str, Any] | None) -> bool:
    return now_local.hour >= HOUR and (saved or {}).get("day") != now_local.date().isoformat()


def _lines(rows: list[dict[str, str]]) -> str:
    return "; ".join(f"{r['name']}: {r['detail']}" if r["detail"] else r["name"] for r in rows)[:600]


def items() -> list[dict[str, Any]]:
    s = last()
    if not s:
        return []
    out = []
    if s.get("broken"):
        n = len(s["broken"])
        out.append({"key": f"selftest:broken:{s['day']}", "kind": "alert", "severity": "attention",
                    "title": f"This morning's self-test: {n} thing{'' if n == 1 else 's'} broken", "body": _lines(s["broken"]),
                    "source": "selftest", "app": "SirisOS", "url": "/status"})
    if s.get("look"):
        n = len(s["look"])
        names = ",".join(sorted(r["name"] for r in s["look"]))
        out.append({"key": f"selftest:look:{hashlib.sha1(names.encode()).hexdigest()[:10]}", "kind": "alert", "severity": "info",
                    "title": f"This morning's self-test: {n} thing{'' if n == 1 else 's'} worth a look", "body": _lines(s["look"]),
                    "source": "selftest", "app": "SirisOS", "url": "/status"})
    return out


async def loop() -> None:
    from app.tasks.service import zone

    await asyncio.sleep(FIRST_WAIT_S)
    while True:
        try:
            now = datetime.now(zone())
            if due(now, last()):
                await run_once(now.date().isoformat())
        except Exception as exc:  # noqa: BLE001 - try again tomorrow's way: next check
            logger.warning("Self-test failed to run: %s", exc)
        await asyncio.sleep(CHECK_EVERY_S)
