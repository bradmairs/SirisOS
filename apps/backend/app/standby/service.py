"""Standby killer (6.4): the smart plugs you pick go off overnight and when
nobody's home, and back on after.

- **Which**: switches you turn on for it on the Power card. It suggests the
  plug behind each always-on power sensor (sensor.tv_plug_power →
  switch.tv_plug) when Home Assistant has one.
- **When**: in SIRISOS_STANDBY_HOURS (local, "1-6") or while SirisAI's
  presence says nobody's home. Checked with each power sample (10 minutes).
- **Only what it turned off goes back on**: a plug you switched off yourself
  stays off; one you switched back on in the night isn't fought (it's left
  alone until the next night).
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Any

from app.hub import sirisai_api
from app.hub.service import Hub
from app.services import json_store

logger = logging.getLogger(__name__)


def _path():
    return json_store.data_path("SIRISOS_STANDBY_PATH", "standby.json")


def load() -> dict[str, Any]:
    doc = json_store.read(_path(), {})
    doc = doc if isinstance(doc, dict) else {}
    doc.setdefault("switches", [])
    doc.setdefault("off_by_us", [])
    doc.setdefault("period", None)
    return doc


def save(doc: dict[str, Any]) -> None:
    json_store.write(_path(), doc)


def hours() -> tuple[int, int]:
    try:
        a, b = (int(x) for x in os.getenv("SIRISOS_STANDBY_HOURS", "1-6").split("-", 1))
        return a % 24, b % 24
    except ValueError:
        return 1, 6


def in_hours(hour: int, span: tuple[int, int]) -> bool:
    a, b = span
    return a <= hour < b if a <= b else hour >= a or hour < b


def switch_for(sensor_id: str) -> str:
    """The plug a power sensor probably belongs to."""
    name = sensor_id.split(".", 1)[-1]
    name = re.sub(r"_(power|current_power|current_consumption|watts|w|energy_power)$", "", name)
    return f"switch.{name}"


def suggestions(always_on: list[dict[str, Any]], switches: list[str]) -> list[dict[str, Any]]:
    known = set(switches)
    out = []
    for d in always_on:
        sw = switch_for(d["entity_id"])
        if sw in known:
            out.append({"sensor": d["entity_id"], "name": d["name"], "watts": d["watts"], "switch": sw})
    return out


def plan(doc: dict[str, Any], states: dict[str, str], night: bool, away: bool | None) -> tuple[list[str], list[str], str]:
    """(turn off, turn on, period) for the moment. Pure, for testing."""
    period = "away" if away else "night" if night else "day"
    if period != "day":
        off = [s for s in doc["switches"] if states.get(s) == "on" and (doc["period"] == "day" or doc["period"] is None)]
        return off, [], period
    on = [s for s in doc["off_by_us"] if states.get(s) == "off"]
    return [], on, period


async def run(hub: Hub, now: datetime) -> dict[str, Any]:
    doc = load()
    if not doc["switches"]:
        return {"skipped": "no switches chosen"}
    controls = await sirisai_api.get(hub, "/siris/hub/v1/controls") or {}
    states = {c["entity_id"]: c.get("state") for c in controls.get("controls") or []}
    presence = await sirisai_api.get(hub, "/siris/hub/v1/presence") or {}
    off, on, period = plan(doc, states, in_hours(now.hour, hours()), presence.get("home") is False)
    done_off, done_on = [], []
    for s in off:
        try:
            await sirisai_api.post(hub, f"/siris/hub/v1/controls/{s}", json={"action": "turn_off"})
            done_off.append(s)
        except sirisai_api.SirisAIError as exc:
            logger.info("Standby: couldn't turn off %s: %s", s, exc)
    for s in on:
        try:
            await sirisai_api.post(hub, f"/siris/hub/v1/controls/{s}", json={"action": "turn_on"})
            done_on.append(s)
        except sirisai_api.SirisAIError as exc:
            logger.info("Standby: couldn't turn on %s: %s", s, exc)
    if period == "day":
        doc["off_by_us"] = [s for s in doc["off_by_us"] if s not in done_on and states.get(s) == "off" and s not in on]
    else:
        doc["off_by_us"] = sorted(set(doc["off_by_us"]) | set(done_off))
    doc["period"] = period
    save(doc)
    return {"period": period, "turned_off": done_off, "turned_on": done_on}
