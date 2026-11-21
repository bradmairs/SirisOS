"""Push notifications API.

    GET    /api/v1/push/key              the VAPID public key for pushManager.subscribe()
    GET    /api/v1/push/subscriptions    this server's devices (labels, topics, last delivered and last error; no keys)
    POST   /api/v1/push/subscribe        add or update this device: {endpoint, keys, label, topics, device?, replaces?}
                                         (7.9: the same install, or the endpoint it replaces, isn't kept twice)
    POST   /api/v1/push/unsubscribe      {endpoint}
    POST   /api/v1/push/test             {endpoint}: send this device a test notification
    GET    /api/v1/push/digest           (10.2) the roundup: on, times, what's waiting
    PUT    /api/v1/push/digest           {on?, times?}

Notification buttons (3.8), no sign-in: the signed token is the permission (push/actions.py).

    GET    /api/v1/push/act?t=           what the notification is, its buttons, and what was already pressed
    POST   /api/v1/push/act              {token, action}: press one
    POST   /api/v1/push/act/opened       {key}: a notification was tapped (10.6; counts only keys SirisOS pushed)

Smarter notifications (10.6, push/smart.py):

    POST   /api/v1/push/seen             {keys}: cards that have been on screen
    POST   /api/v1/push/active           {device, endpoint?, label?, focus_until?}: the app is open; returns in-app banners
    GET    /api/v1/push/smart            the week by kind, the cap, on or off
    PUT    /api/v1/push/smart            {on?, cap?}
    PUT    /api/v1/push/smart/kinds/{kind}  {mode: auto, normal, roundup or off}
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_user
from app.hub.service import Hub, get_hub, shared_client
from app.hub.sirisai_api import SirisAIError
from app.push import actions, digest, notifier, store, webpush

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
    except SirisAIError as exc:  # e.g. Block, when SirisAI or UniFi can't do it right now
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    actions.mark_used(p["n"], body.action, p["e"])
    return {"done": body.action, "message": said, "url": p["u"]}


class Endpoint(BaseModel):
    endpoint: str = Field(min_length=10, max_length=2000)


def _public(sub: store.Subscription, health: dict[str, Any] | None = None) -> dict[str, Any]:
    h = (health if health is not None else store.health()).get(sub.endpoint) or {}
    return {"endpoint": sub.endpoint, "label": sub.label, "topics": sub.topics, "created_at": sub.created_at, "device": sub.device,
            "last_ok": h.get("last_ok"), "last_error": h.get("last_error"), "last_error_at": h.get("last_error_at"),
            "failing": store.failing(sub, h)}


@router.get("/key")
def key() -> dict[str, Any]:
    return {"public_key": webpush.vapid().public_key, "topics": list(store.TOPICS)}


@router.get("/subscriptions")
def subscriptions() -> dict[str, Any]:
    health = store.health()
    return {"subscriptions": [_public(s, health) for s in store.subscriptions()]}


class Subscribe(store.Subscription):
    replaces: str | None = Field(default=None, max_length=2000)  # this install's previous endpoint (7.9)


@router.post("/subscribe")
def subscribe(body: Subscribe) -> dict[str, Any]:
    replaces = body.replaces
    sub = store.Subscription.model_validate(body.model_dump(exclude={"replaces"}))
    return _public(store.upsert(sub, replaces))


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
        store.record(sub.endpoint)
    except webpush.Gone:
        store.remove(sub.endpoint)
        raise HTTPException(status_code=410, detail="The push service no longer knows this device. Turn notifications on again.")
    except httpx.HTTPStatusError as exc:
        store.record(sub.endpoint, notifier.describe(exc))
        code = exc.response.status_code
        reason = "the push service turned down SirisOS's signature" if code in (401, 403) else f"the push service answered {code}"
        raise HTTPException(status_code=502, detail=f"Couldn't send: {reason}. Turn notifications off and on again on this device.") from exc
    except Exception as exc:  # noqa: BLE001
        store.record(sub.endpoint, notifier.describe(exc))
        raise HTTPException(status_code=502, detail=f"Couldn't send: {exc}") from exc
    return {"sent": True}


class DigestIn(BaseModel):
    on: bool | None = None
    times: list[str] | None = Field(None, max_length=4)


@router.get("/digest")
def get_digest() -> dict[str, Any]:
    return digest.settings()


@router.put("/digest")
def put_digest(body: DigestIn) -> dict[str, Any]:
    try:
        return digest.change(body.on, body.times)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


# 10.6: smarter notifications (push/smart.py).

class SeenIn(BaseModel):
    keys: list[str] = Field(max_length=50)


class ActiveIn(BaseModel):
    device: str = Field(min_length=4, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    endpoint: str | None = Field(default=None, max_length=2000)
    label: str | None = Field(default=None, max_length=60)
    focus_until: str | None = Field(default=None, max_length=40)


class SmartIn(BaseModel):
    on: bool | None = None
    cap: int | None = Field(default=None, ge=1, le=30)


class KindIn(BaseModel):
    mode: str = Field(pattern=r"^(auto|normal|roundup|off)$")


class OpenedIn(BaseModel):
    key: str = Field(min_length=3, max_length=160)


def _now():
    from datetime import datetime

    from app.brief.service import zone

    return datetime.now(zone())


@router.post("/seen")
def seen(body: SeenIn) -> dict[str, Any]:
    """Cards on screen: their notifications won't be sent (and any waiting are dropped)."""
    from app.push import smart

    return {"seen": smart.mark_seen(body.keys, _now())}


@router.post("/active")
def active(body: ActiveIn) -> dict[str, Any]:
    """The app is open on this device (every minute while it's on screen); returns the in-app banners waiting."""
    from app.push import smart

    return {"inapp": smart.heartbeat(body.device, body.endpoint, body.label, body.focus_until, _now())}


@router.get("/smart")
def get_smart() -> dict[str, Any]:
    from app.push import smart

    return smart.report(_now())


@router.put("/smart")
def put_smart(body: SmartIn) -> dict[str, Any]:
    from app.push import smart

    smart.change(body.on, body.cap)
    return smart.report(_now())


@router.put("/smart/kinds/{kind}")
def put_kind(kind: str, body: KindIn) -> dict[str, Any]:
    from app.push import smart

    if not kind.replace("-", "").isalnum() or len(kind) > 40:
        raise HTTPException(status_code=404, detail="No such kind of notification.")
    smart.set_mode(kind, body.mode)
    return smart.report(_now())


@act_router.post("/opened")
def opened(body: OpenedIn) -> dict[str, Any]:
    """A notification was tapped (from the service worker, no sign-in): only counts keys SirisOS actually pushed."""
    from app.push import smart

    return {"counted": smart.opened(body.key, _now())}
