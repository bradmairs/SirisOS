"""Push notifications API.

    GET    /api/v1/push/key              the VAPID public key for pushManager.subscribe()
    GET    /api/v1/push/subscriptions    this server's devices (labels and topics, no keys)
    POST   /api/v1/push/subscribe        add or update this device: {endpoint, keys, label, topics}
    POST   /api/v1/push/unsubscribe      {endpoint}
    POST   /api/v1/push/test             {endpoint}: send this device a test notification
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_user
from app.hub.service import shared_client
from app.push import store, webpush

router = APIRouter(prefix="/api/v1/push", tags=["push"], dependencies=[Depends(require_user)])


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
