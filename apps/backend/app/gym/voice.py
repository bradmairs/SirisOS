"""Logging a set with Siri (8.8): "Hey Siri, log 100 by 5".

A workout in progress lives on the phone, so a set said to Siri can't be put
straight into it. A Shortcut sends the words here with your SirisGym key; they
wait in a short queue, and the workout screen takes them in (as its own voice
logging does) whenever it's open. Siri answers at once with what it heard.

The key is made in SirisGym's settings and shown once; only its hash is kept.
It can do one thing: add to this queue.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from app.services import json_store

MAX_QUEUE = 50
_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
          "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
          "eighty": 80, "ninety": 90, "hundred": 100}


def _path():
    return json_store.data_path("SIRISOS_GYM_VOICE_PATH", "gym-voice.json")


def new_key() -> tuple[str, str]:
    key = "sg_" + secrets.token_urlsafe(24)
    return key, hashlib.sha256(key.encode()).hexdigest()


def matches(key: str | None, stored_hash: str) -> bool:
    if not key or not stored_hash:
        return False
    return secrets.compare_digest(hashlib.sha256(key.encode()).hexdigest(), stored_hash)


def parse(text: str) -> dict[str, Any] | None:
    """What a spoken set says: {weight, reps, rpe?, name?}, like the workout screen's own voice logging."""
    t = " " + re.sub(r"[,!?]", " ", text.lower()) + " "
    t = re.sub(r"\b(" + "|".join(_WORDS) + r")\b", lambda m: str(_WORDS[m.group(1)]), t)
    t = re.sub(r"\b(\d) 100\b", lambda m: str(int(m.group(1)) * 100), t)  # "one hundred" -> 100
    t = re.sub(r"\b(\d00) (?:and )?(\d{1,2})\b", lambda m: str(int(m.group(1)) + int(m.group(2))), t)
    t = re.sub(r"\b([2-9]0) ([1-9])\b", lambda m: str(int(m.group(1)) + int(m.group(2))), t)
    t = re.sub(r"(\d)\s*point\s*(\d)", r"\1.\2", t).replace(" and a half", ".5")
    rpe = None
    if m := re.search(r"\brpe\s*(\d+(?:\.\d)?)", t):
        rpe = float(m.group(1))
        t = t.replace(m.group(0), " ")
    unit = r"(?:\s*(?:kg|kilos?|kilograms?))?"
    out: dict[str, Any] | None = None
    m = re.search(rf"(\d+(?:\.\d+)?){unit}\s*(?:by|x|times|for|×)\s*(\d+)(?:\s*reps?)?", t)
    if m:
        out = {"weight": float(m.group(1)), "reps": int(m.group(2))}
    elif m := re.search(rf"(\d+)\s*reps?\s*(?:at|with|of)\s*(\d+(?:\.\d+)?){unit}", t):
        out = {"weight": float(m.group(2)), "reps": int(m.group(1))}
    elif m := re.search(r"(?:body ?weight|no weight)\s*(?:for\s*)?(\d+)", t):
        out = {"weight": None, "reps": int(m.group(1))}
    elif m := re.search(r"(\d+)\s*reps?\b", t):
        out = {"reps": int(m.group(1))}
    if not out or not out.get("reps") or out["reps"] > 100:
        return None
    name = re.sub(r"\b(log|logged|did|set|just|hey|siri|sirisgym)\b", " ", t[:m.start()]).strip() if m else ""
    if rpe and 5 <= rpe <= 10:
        out["rpe"] = rpe
    if len(name) > 2:
        out["name"] = name
    return out


def said(p: dict[str, Any]) -> str:
    w = p.get("weight")
    return (f"{w:g} by {p['reps']}" if w else f"{p['reps']} reps") + (f" at RPE {p['rpe']:g}" if p.get("rpe") else "") + (f" for {p['name']}" if p.get("name") else "")


def queue() -> list[dict[str, Any]]:
    found = json_store.read(_path(), [])
    return found if isinstance(found, list) else []


def add(text: str, parsed: dict[str, Any]) -> dict[str, Any]:
    item = {"id": uuid.uuid4().hex[:12], "text": text[:200], "parsed": parsed, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    json_store.write(_path(), [*queue(), item][-MAX_QUEUE:])
    return item


def ack(ids: list[str]) -> int:
    before = queue()
    left = [q for q in before if q["id"] not in set(ids)]
    json_store.write(_path(), left)
    return len(before) - len(left)
