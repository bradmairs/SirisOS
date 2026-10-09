"""The inbox (ADR 110): everything that needs Brad, from every app, in one list.

Two sources, merged:

- **SirisAI's attention feed** (`/siris/hub/v1/attention`): its alerts
  (intruders, failed self-heals, security), actions waiting for approval,
  habit suggestions, jobs waiting for cheap power, Second Brain reviews.
  Their actions (Approve, Lock down, Create automation...) are SirisAI's and
  run there; SirisOS only relays them. Ids are prefixed `ai:`.
- **SirisOS's own**, from what the hub already watches (ids `os:`): any app
  that's down or degraded, Project Management's overdue tasks, and the
  Engineering Archive's review queue. Their only action is Dismiss; tapping
  opens the app. A dismissal is remembered (server-side, so every device
  agrees) until the situation changes -- the item's key includes its state
  or count, so "APD PM is down" comes back if it goes down again tomorrow,
  and "3 overdue" comes back as "4 overdue".

Each source fails alone: a SirisAI outage leaves SirisOS's own items (and
an "apps down" item for SirisAI itself), and the reverse.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.hub.connectors.sirisai import SirisAIConnector
from app.hub.service import Hub, shared_client

logger = logging.getLogger(__name__)

SEVERITIES = ("urgent", "attention", "info")
MAX_DISMISSED = 500


def _state_path() -> Path:
    return Path(os.getenv("SIRISOS_ATTENTION_STATE_PATH", "/app/data/attention-state.json"))


def _dismissed() -> list[str]:
    try:
        value = json.loads(_state_path().read_text(encoding="utf-8")).get("dismissed")
        return value if isinstance(value, list) else []
    except (OSError, ValueError, AttributeError):
        return []


def dismiss_local(key: str) -> None:
    keys = [k for k in _dismissed() if k != key] + [key]
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"dismissed": keys[-MAX_DISMISSED:]}), encoding="utf-8")
    tmp.replace(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metric(widget: dict[str, Any] | None, label: str) -> int:
    for m in (widget or {}).get("metrics") or []:
        if m.get("label") == label:
            try:
                return int(str(m.get("value")).replace(",", ""))
            except ValueError:
                return 0
    return 0


def own_items(apps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """SirisOS's items from the hub's app list (with widgets), before dismissals."""
    items: list[dict[str, Any]] = []
    day = datetime.now(timezone.utc).date().isoformat()
    for app in apps:
        status = app.get("status") or {}
        state = status.get("state")
        if state in ("down", "degraded"):
            items.append({
                "key": f"app:{app['id']}:{state}",
                "kind": "alert",
                "severity": "attention" if state == "down" else "info",
                "title": f"{app['name']} is {state}",
                "body": status.get("detail") or "",
                "source": "hub",
                "app": app["name"],
                "url": app.get("launch_url"),
            })
        widget = app.get("widget") if isinstance(app.get("widget"), dict) else None
        if app.get("id") == "apd-pm" and (overdue := _metric(widget, "Overdue")):
            items.append({
                "key": f"apd:overdue:{overdue}:{day}",
                "kind": "notice",
                "severity": "attention",
                "title": f"{overdue} overdue task{'s' if overdue != 1 else ''} in {app['name']}",
                "body": "; ".join(i.get("title", "") for i in (widget or {}).get("items") or [] if i.get("tone") == "critical")[:300],
                "source": "apd-pm",
                "app": app["name"],
                "url": app.get("launch_url"),
            })
        if app.get("id") == "archive" and (review := _metric(widget, "Needs review")):
            items.append({
                "key": f"archive:review:{review}",
                "kind": "review",
                "severity": "info",
                "title": f"{review} item{'s' if review != 1 else ''} waiting for review in the {app['name']}",
                "body": "",
                "source": "archive",
                "app": app["name"],
                "url": app.get("launch_url"),
            })
    return items


def from_os(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"os:{item['key']}",
        "origin": "sirisos",
        "kind": item["kind"],
        "severity": item["severity"],
        "title": item["title"],
        "body": item.get("body") or "",
        "source": item["source"],
        "app": item.get("app") or "SirisOS",
        "url": item.get("url"),
        "link": None,
        "actions": [],
        "created_at": _now(),
        "updated_at": _now(),
    }


def from_ai(item: dict[str, Any]) -> dict[str, Any]:
    """One SirisAI AttentionItem (contract v1) as an inbox item."""
    return {
        "id": f"ai:{item['id']}",
        "origin": "sirisai",
        "kind": item.get("kind", "notice"),
        "severity": item.get("severity", "attention"),
        "title": item.get("title", ""),
        "body": item.get("body") or "",
        "source": item.get("source", "siris"),
        "app": "SirisAI",
        "url": None,
        "link": item.get("link"),
        "actions": item.get("actions") or [],
        "created_at": item.get("created_at") or _now(),
        "updated_at": item.get("updated_at") or _now(),
    }


def sort_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Urgent first, then attention, then info; newest first within each."""
    newest = sorted(items, key=lambda i: i["updated_at"], reverse=True)
    return sorted(newest, key=lambda i: SEVERITIES.index(i["severity"]) if i["severity"] in SEVERITIES else 9)


def counts(items: list[dict[str, Any]]) -> dict[str, int]:
    return {"open": len(items), "urgent": sum(1 for i in items if i["severity"] == "urgent")}


def sirisai(hub: Hub) -> SirisAIConnector | None:
    connector = hub.get("sirisai")
    return connector if isinstance(connector, SirisAIConnector) and connector.configured else None


async def ai_items(hub: Hub) -> list[dict[str, Any]] | None:
    """SirisAI's open items, or None if SirisAI isn't configured, is too old
    to have the feed, or didn't answer."""
    connector = sirisai(hub)
    if connector is None:
        return None
    response = await shared_client().get(f"{connector.base_url}/siris/hub/v1/attention", headers=connector.headers(), timeout=8.0)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return [from_ai(i) for i in response.json().get("items") or []]


async def os_items(hub: Hub) -> list[dict[str, Any]]:
    dismissed = set(_dismissed())
    apps = await hub.apps(with_widgets=True)
    return [from_os(i) for i in own_items(apps) if f"os:{i['key']}" not in dismissed]


async def inbox(hub: Hub) -> dict[str, Any]:
    failed: list[str] = []
    mine = []
    try:
        mine = await os_items(hub)
    except Exception as exc:  # noqa: BLE001 - one source never empties the inbox
        logger.info("SirisOS inbox items unavailable: %s", exc)
        failed.append("SirisOS")
    theirs: list[dict[str, Any]] = []
    try:
        theirs = await ai_items(hub) or []
    except Exception as exc:  # noqa: BLE001
        logger.info("SirisAI attention feed unavailable: %s", exc)
        failed.append("SirisAI")
    items = sort_items(theirs + mine)
    return {"items": items, "counts": counts(items), "unavailable": failed}
