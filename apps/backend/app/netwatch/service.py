"""Network alerts (5.3): a phone notification when something new joins the
home network, or something important drops off it.

Every two minutes (from the notifications loop) SirisOS reads SirisAI's
live network (/siris/hub/v1/network, UniFi). The first look records what's
there: that's the baseline, not a flood of "new device" alerts. After that:

- **A device it hasn't seen** gets one notification with **Trust** (it's
  ours: stop asking) and **Block** (SirisAI blocks it in UniFi). Until you
  decide, it's listed under "New on the network" on the Smart home page.
- **An important device** that's gone for 10 minutes gets one notification
  per outage. Important means the gateway, switches and access points, and
  anything named like the NAS, Home Assistant or a camera, unless you
  change it; star or un-star any device on the Smart home page.
- **Blocked devices** are listed, with Unblock.

Guest mode hides clients, so nothing is checked then.

**Inventory** (6.2): each device can have a label ("Lounge TV"), an owner
and a type, and takes its room from where it sits in the 3D house. Alerts
use them ("Lounge TV (Lounge) is offline"), not the MAC. When SirisAI
watches for new devices itself (3.83, `device_alerts`), with UniFi's own
first-seen date and names, SirisOS leaves new devices to it rather than
alert twice. Either way a device UniFi has a name for, or first saw over
a day ago, isn't new.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

from app.hub import sirisai_api
from app.hub.service import Hub
from app.services import json_store

CHECK_EVERY_SECONDS = 120
OFFLINE_AFTER_SECONDS = 600
IMPORTANT_NAMES = re.compile(r"\b(nas|synology|home ?assist[ae]nt|hass|camera|cam|doorbell|frigate|nvr|server|router)\b", re.I)


def _path():
    return json_store.data_path("SIRISOS_NETWATCH_PATH", "netwatch.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load() -> dict[str, Any]:
    doc = json_store.read(_path(), {})
    doc = doc if isinstance(doc, dict) else {}
    for key, default in (("known", {}), ("blocked", {}), ("important", {}), ("missing_since", {})):
        doc.setdefault(key, default)
    doc.setdefault("baseline", False)
    doc.setdefault("checked", 0)
    return doc


def save(doc: dict[str, Any]) -> None:
    json_store.write(_path(), doc)


def _rooms() -> dict[str, str]:
    raw = json_store.read(json_store.data_path("SIRISOS_HOUSE_PATH", "house.json"), {})
    return {k: v.get("room") for k, v in ((raw or {}).get("placements") or {}).items() if isinstance(v, dict) and v.get("room")}


def label(entry: dict[str, Any], node_id: str, rooms: dict[str, str] | None = None) -> str:
    """What to call it in an alert: your label (else UniFi's name), and its room."""
    name = entry.get("label") or entry.get("name") or node_id
    room = (rooms if rooms is not None else _rooms()).get(node_id)
    return f"{name} ({room})" if room and room.lower() not in name.lower() else name


def set_details(node_id: str, details: dict[str, Any]) -> dict[str, Any]:
    doc = load()
    entry = doc["known"].get(node_id)
    if entry is None:
        raise LookupError(node_id)
    for key in ("label", "owner", "type"):
        if key in details:
            value = str(details[key] or "").strip()[:60]
            if value:
                entry[key] = value
            else:
                entry.pop(key, None)
    entry["trusted"] = True  # described it: it's ours
    save(doc)
    return entry


NEW_WITHIN_SECONDS = 24 * 3600


def important(doc: dict[str, Any], node_id: str, entry: dict[str, Any]) -> bool:
    """Your choice if you made one, else infrastructure and the NAS/HA/cameras by name."""
    chosen = doc["important"].get(node_id)
    if chosen is not None:
        return bool(chosen)
    return entry.get("kind") in ("gateway", "switch", "access_point") or bool(IMPORTANT_NAMES.search(str(entry.get("name") or "")))


def observe(doc: dict[str, Any], nodes: list[dict[str, Any]], now: float, sirisai_alerts: bool = False,
            rooms: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Fold one look at the network into `doc`; returns the alerts it raises
    (as notifier messages). Pure apart from `doc`, for testing."""
    from app.push.notifier import message

    rooms = rooms if rooms is not None else {}
    out: list[dict[str, Any]] = []
    seen = {str(n.get("id")): n for n in nodes if n.get("id")}
    stamp = datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds")
    first = not doc["baseline"]
    for nid, n in seen.items():
        entry = doc["known"].get(nid)
        if entry is None:
            entry = {"name": n.get("name") or nid, "kind": n.get("kind"), "first_seen": stamp, "trusted": first}
            doc["known"][nid] = entry
            seen_before = n.get("first_seen") is not None and now - float(n["first_seen"]) > NEW_WITHIN_SECONDS
            if n.get("named") or seen_before:
                entry["trusted"] = True
            if not first and n.get("kind") == "client" and not sirisai_alerts and not entry["trusted"]:
                out.append(message(f"net:new:{nid}", "home", f"New on your network: {entry['name']}",
                                   f"{nid}{' · wired' if n.get('wired') else ''}. Is it yours?", "/house?view=network",
                                   "high", f"netdev:{nid}", [{"id": "trust", "title": "It's mine"}, {"id": "block", "title": "Block it"}]))
        entry.update({"name": n.get("name") or entry.get("name"), "kind": n.get("kind") or entry.get("kind"), "last_seen": stamp})
        if n.get("online", True):
            doc["missing_since"].pop(nid, None)
        else:
            doc["missing_since"].setdefault(nid, now)
    for nid, entry in doc["known"].items():
        if nid not in seen and nid not in doc["blocked"]:
            doc["missing_since"].setdefault(nid, now)
    for nid, since in list(doc["missing_since"].items()):
        entry = doc["known"].get(nid)
        if entry is None or nid in doc["blocked"]:
            doc["missing_since"].pop(nid, None)
            continue
        if important(doc, nid, entry) and now - since >= OFFLINE_AFTER_SECONDS:
            out.append(message(f"net:offline:{nid}:{int(since)}", "home", f"{label(entry, nid, rooms)} is offline",
                               f"Not on the network for {int((now - since) // 60)} minutes.", "/house?view=network", "high"))
    doc["baseline"] = True
    return out


async def check(hub: Hub, now: float | None = None) -> list[dict[str, Any]]:
    """At most every two minutes; nothing when SirisAI, UniFi or guest mode say no."""
    now = now or time.time()
    doc = load()
    if now - float(doc.get("checked") or 0) < CHECK_EVERY_SECONDS:
        return []
    net = await sirisai_api.get(hub, "/siris/hub/v1/network")
    doc["checked"] = now
    if not net or not net.get("configured") or net.get("guest_mode"):
        save(doc)
        return []
    alerts = observe(doc, net.get("nodes") or [], now, bool(net.get("device_alerts")), _rooms())
    save(doc)
    return alerts


def view() -> dict[str, Any]:
    doc = load()
    rooms = _rooms()
    now = time.time()
    devices = []
    for nid, e in doc["known"].items():
        since = doc["missing_since"].get(nid)
        devices.append({"id": nid, "name": e.get("label") or e.get("name") or nid, "unifi_name": e.get("name"), "owner": e.get("owner"),
                        "type": e.get("type"), "room": rooms.get(nid), "kind": e.get("kind"), "first_seen": e.get("first_seen"),
                        "last_seen": e.get("last_seen"), "trusted": bool(e.get("trusted")), "important": important(doc, nid, e),
                        "blocked": nid in doc["blocked"], "online": since is None,
                        "offline_minutes": int((now - since) // 60) if since else None})
    devices.sort(key=lambda d: (d["trusted"], not d["important"], d["name"].lower()))
    return {"watching": bool(doc["baseline"]), "devices": devices}


def trust(node_id: str) -> None:
    doc = load()
    if node_id not in doc["known"]:
        raise LookupError(node_id)
    doc["known"][node_id]["trusted"] = True
    save(doc)


def set_important(node_id: str, on: bool) -> None:
    doc = load()
    if node_id not in doc["known"]:
        raise LookupError(node_id)
    doc["important"][node_id] = on
    save(doc)


async def set_blocked(hub: Hub, node_id: str, blocked: bool) -> dict[str, Any]:
    """Through SirisAI (raises SirisAIError with its message)."""
    result = await sirisai_api.post(hub, f"/siris/hub/v1/network/{node_id}/block", json={"blocked": blocked})
    doc = load()
    if blocked:
        doc["blocked"][node_id] = _now()
        doc["known"].setdefault(node_id, {"name": node_id, "kind": "client", "first_seen": _now()})
        doc["known"][node_id]["trusted"] = True  # decided: don't ask about it again
    else:
        doc["blocked"].pop(node_id, None)
    doc["missing_since"].pop(node_id, None)
    save(doc)
    return result or {"id": node_id, "blocked": blocked}
