"""Push notifications API.

    GET    /api/v1/push/key              the VAPID public key for pushManager.subscribe()
    GET    /api/v1/push/subscriptions    this server's devices (labels and topics, no keys)
    POST   /api/v1/push/subscribe        add or update this device: {endpoint, keys, label, topics}
    POST   /api/v1/push/unsubscribe      {endpoint}
    POST   /api/v1/push/test             {endpoint}: send this device a test notification

Notification buttons (3.8), no sign-in: the signed token is the permission (push/actions.py).

    GET    /api/v1/push/act?t=           what the notification is, its buttons, and what was already pressed
    POST   /api/v1/push/act              {token, action}: press one
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_user
from app.hub.service import Hub, get_hub, shared_client
from app.push import actions, store, webpush

router = APIRouter(prefix="/api/v1/push", tags=["push"], dependencies=[Depends(require_user)])
act_router = APIRouter(prefix="/api/v1/push/act", tags=["push"])


class Press(BaseModel):
    token: str = Field(min_length=10, max_length=4000)
    action: str = Field(min_length=1, max_length=40)
    pin: str | None = Field(default=None, max_length=32)


def _checked(token: str) -> dict[str, Any]:
    try:
        return actions.verify(token)
    except actions.BadToken as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@act_router.get("")
def what(t: str) -> dict[str, Any]:
    p = _checked(t)
    return {"title": p["ti"], "body": p["b"], "url": p["u"], "actions": p["a"], "done": actions.used(p["n"])}


@act_router.post("")
async def press(body: Press, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    p = _checked(body.token)
    if (before := actions.used(p["n"])) is not None:
        raise HTTPException(status_code=409, detail=f"Already done from this notification ({before}).")
    try:
        said = await actions.perform(hub, p, body.action, pin=body.pin)
    except actions.BadToken as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="That's already gone.") from exc
    actions.mark_used(p["n"], body.action, p["e"])
    return {"done": body.action, "message": said, "url": p["u"]}


class Endpoint(BaseModel):
    endpoint: str = Field(min_length=10, max_length=2000)


def _public(sub: store.Subscription) -> dict[str, Any]:
    return {"endpoint": sub.endpoint, "label": sub.label, "topics": sub.topics, "created_at": sub.created_at}


@router.get("/key")
def key() -> dict[str, Any]:
    return {"public_key": webpush.vapid().public_key, "topics": list(store.TOPICS)}


@router.get("/subscriptions")
def subscriptions() -> dict[str, Any]:
    return {"subscriptions": [_public(s) for s in store.subscriptions()]}


@router.post("/subscribe")
def subscribe(sub: store.Subscription) -> dict[str, Any]:
    return _public(store.upsert(sub))


@router.post("/unsubscribe")
def unsubscribe(body: Endpoint) -> dict[str, Any]:
    return {"removed": store.remove(body.endpoint)}


@router.post("/test")
async def test(body: Endpoint) -> dict[str, Any]:
    sub = next((s for s in store.subscriptions() if s.endpoint == body.endpoint), None)
    if sub is None:
        raise HTTPException(status_code=404, detail="This device isn't subscribed.")
    try:
        await webpush.send(shared_client(), sub.model_dump(), {
            "title": "SirisOS notifications are on", "body": "You'll hear from SirisOS here.", "url": "/", "tag": "test",
        })
    except webpush.Gone:
        store.remove(sub.endpoint)
        raise HTTPException(status_code=410, detail="The push service no longer knows this device. Turn notifications on again.")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Couldn't send: {exc}") from exc
    return {"sent": True}
