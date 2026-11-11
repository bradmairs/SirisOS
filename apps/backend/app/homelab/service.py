"""Home Lab (8.5): the hardware as a diagram, from what SirisOS already knows.

- **The network** from the network watch (UniFi through SirisAI): the gateway, switches, access points, and
  devices marked important. The other devices are counted, not drawn.
- **Servers** from the terminal's machines (SIRISOS_TERMINAL_HOSTS).
- **Docker**: how many containers SirisAI sees, under the first server unless moved.
- **Your own hardware** that SirisOS can't see (a modem, a UPS, a NAS on another network).

What plugs into what is guessed (gateway under the internet, switches under the gateway, access points and
servers under the first switch) until you set it. Your labels, models, notes and parents are kept in
homelab.json, by each node's id, so they stay when the network changes.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from app.hub import sirisai_api
from app.hub.service import Hub
from app.services import json_store

KINDS = ("internet", "modem", "gateway", "switch", "access_point", "server", "nas", "ups", "docker", "device", "other")
ROOT = "internet"


def _path():
    return json_store.data_path("SIRISOS_HOMELAB_PATH", "homelab.json")


def load() -> dict[str, Any]:
    raw = json_store.read(_path(), {})
    doc = raw if isinstance(raw, dict) else {}
    doc.setdefault("nodes", {})
    doc.setdefault("custom", {})
    return doc


def save(doc: dict[str, Any]) -> None:
    json_store.write(_path(), doc)


async def _containers(hub: Hub) -> list[dict[str, Any]] | None:
    body = await sirisai_api.get(hub, "/siris/hub/v1/tracking", timeout=8.0)
    return body.get("containers") if isinstance(body, dict) else None


def _network() -> list[dict[str, Any]]:
    from app.netwatch import service as netwatch

    try:
        return netwatch.view()["devices"]
    except Exception:  # noqa: BLE001 - no network watch yet
        return []


def _servers() -> list[dict[str, Any]]:
    from app.terminal import service as terminal

    return [{"id": f"server:{re.sub(r'[^a-z0-9]+', '-', h.name.lower())}", "label": h.name, "kind": "server", "detail": h.host} for h in terminal.hosts()]


async def diagram(hub: Hub) -> dict[str, Any]:
    doc = load()
    mine = doc["nodes"]
    devices = _network()
    nodes: list[dict[str, Any]] = [{"id": ROOT, "label": "Internet", "kind": "internet", "online": True, "found": "built in"}]
    for d in devices:
        if d.get("kind") in ("gateway", "switch", "access_point") or d.get("important"):
            kind = d.get("kind") if d.get("kind") in ("gateway", "switch", "access_point") else "device"
            nodes.append({"id": f"net:{d['id']}", "label": d["name"], "kind": kind, "online": d.get("online"), "found": "network",
                          "detail": " · ".join(x for x in (d.get("type"), d.get("room"), d.get("owner")) if x) or None})
    nodes += [{**s, "online": None, "found": "terminal"} for s in _servers()]
    try:
        containers = await _containers(hub)
    except Exception:  # noqa: BLE001 - SirisAI not reachable: no Docker box
        containers = None
    if containers:
        running = sum(1 for c in containers if c.get("state") == "running")
        nodes.append({"id": "docker", "label": "Docker", "kind": "docker", "online": True, "found": "sirisai",
                      "detail": f"{running} of {len(containers)} containers running"})
    for cid, c in doc["custom"].items():
        nodes.append({"id": cid, "label": c.get("label") or "Hardware", "kind": c.get("kind") or "other", "online": None, "found": "you"})

    # Defaults for what plugs into what, then your own choices on top.
    first = lambda kind: next((n["id"] for n in nodes if n["kind"] == kind), None)  # noqa: E731
    gateway, switch, server = first("gateway"), first("switch"), first("server")
    for n in nodes:
        if n["id"] == ROOT:
            n["parent"] = None
            continue
        guess = {"modem": ROOT, "gateway": first("modem") or ROOT, "switch": gateway or ROOT, "access_point": switch or gateway or ROOT,
                 "docker": server or switch or gateway or ROOT}.get(n["kind"], switch or gateway or ROOT)
        n["parent"] = guess if guess != n["id"] else ROOT
        n["parent_guessed"] = True
        own = mine.get(n["id"]) or {}
        for key in ("label", "model", "notes"):
            if own.get(key):
                n[key] = own[key]
        if own.get("parent"):
            n["parent"], n["parent_guessed"] = own["parent"], False
    ids = {n["id"] for n in nodes}
    for n in nodes:  # a parent that's gone (a switch replaced): back to the guess, or the internet
        if n["parent"] is not None and (n["parent"] not in ids or _loops(nodes, n["id"])):
            n["parent"], n["parent_guessed"] = ROOT, True
    clients = [d for d in devices if d.get("kind") == "client" and not d.get("important")]  # the ones not drawn
    return {"nodes": nodes, "clients": {"total": len(clients), "online": sum(1 for d in clients if d.get("online"))},
            "sources": {"network": bool(devices), "servers": any(n["kind"] == "server" for n in nodes), "docker": containers is not None}}


def _loops(nodes: list[dict[str, Any]], start: str) -> bool:
    parent = {n["id"]: n.get("parent") for n in nodes}
    seen, at = set(), parent.get(start)
    while at:
        if at == start or at in seen:
            return True
        seen.add(at)
        at = parent.get(at)
    return False


def update(node_id: str, changes: dict[str, Any]) -> None:
    doc = load()
    own = dict(doc["nodes"].get(node_id) or {})
    for key in ("label", "model", "notes", "parent"):
        if key in changes and changes[key] is not None:
            value = str(changes[key]).strip()[:300 if key == "notes" else 80]
            if value:
                own[key] = value
            else:
                own.pop(key, None)
    if node_id in doc["custom"] and changes.get("kind") in KINDS:
        doc["custom"][node_id]["kind"] = changes["kind"]
    if node_id in doc["custom"] and own.get("label"):
        doc["custom"][node_id]["label"] = own["label"]
    doc["nodes"][node_id] = own
    save(doc)


def add(label: str, kind: str, parent: str | None) -> str:
    doc = load()
    cid = f"own:{uuid.uuid4().hex[:8]}"
    doc["custom"][cid] = {"label": label.strip()[:80], "kind": kind if kind in KINDS else "other"}
    if parent:
        doc["nodes"][cid] = {"parent": parent}
    save(doc)
    return cid


def remove(node_id: str) -> bool:
    doc = load()
    if node_id not in doc["custom"]:
        return False
    doc["custom"].pop(node_id)
    doc["nodes"].pop(node_id, None)
    for own in doc["nodes"].values():  # what plugged into it goes back to its guess
        if own.get("parent") == node_id:
            own.pop("parent")
    save(doc)
    return True
