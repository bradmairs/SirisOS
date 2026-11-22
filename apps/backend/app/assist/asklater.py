"""Questions asked offline (11.4).

A question asked in SirisAI's chat with no connection waits on the phone; when it syncs, it lands here. SirisOS asks
SirisAI (POST /siris/chat, in the background) and sends the answer as a notification that opens the conversation.
If the answer needs a confirmation (an action), the notification says to open it and confirm there: nothing is done
on its own. Kept in asked.json (the last 50).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any

from app.hub import sirisai_api
from app.hub.service import Hub
from app.services import json_store

logger = logging.getLogger(__name__)


def _path():
    return json_store.data_path("SIRISOS_ASKED_PATH", "asked.json")


def history() -> list[dict[str, Any]]:
    return (json_store.read(_path(), {}) or {}).get("asked", [])


def _record(item: dict[str, Any]) -> None:
    doc = json_store.read(_path(), {}) or {}
    doc["asked"] = [*doc.get("asked", []), item][-50:]
    json_store.write(_path(), doc)


async def answer(hub: Hub, prompt: str, conversation_id: str | None, asked_at: str | None) -> dict[str, Any]:
    key = "ask:" + hashlib.sha256(f"{asked_at}|{prompt}".encode()).hexdigest()[:16]
    if any(a["key"] == key for a in history()):
        return {"key": key, "duplicate": True}  # the same question synced twice: asked once
    body: dict[str, Any] = {"prompt": prompt}
    if conversation_id:
        body["conversation_id"] = conversation_id
    try:
        out = await sirisai_api.post(hub, "/siris/chat", json=body, timeout=180.0) or {}
    except Exception as exc:  # noqa: BLE001 - say so rather than lose it
        logger.warning("Asked-offline question failed: %s", exc)
        out = {"response": None, "error": str(exc)[:200]}
    conv = out.get("conversation_id")
    if out.get("confirmation_required"):
        text = "It wants to do something and needs you to confirm it: open SirisAI to see and confirm."
    elif out.get("response"):
        text = str(out["response"]).strip()
    elif out.get("error"):
        text = f"SirisAI couldn't answer it: {out['error']}"
    else:
        text = "SirisAI answered: open the conversation to see it."
    item = {"key": key, "prompt": prompt, "asked_at": asked_at, "answered_at": datetime.now().isoformat(timespec="seconds"),  # noqa: DTZ005
            "conversation_id": conv, "answer": text[:4000]}
    _record(item)
    msg = {"key": key, "topic": "inbox", "title": f"SirisAI answered: {prompt[:60]}", "body": text[:300],
           "url": f"/assistant?c={conv}" if conv else "/assistant", "urgency": "normal", "target": None, "actions": []}
    try:
        from app.push import notifier, store

        await notifier.deliver([msg])
        store.mark_sent([key])
    except Exception as exc:  # noqa: BLE001
        logger.info("Asked-offline answer not pushed: %s", exc)
    return item
