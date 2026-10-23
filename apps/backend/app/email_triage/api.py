"""Email triage API (3.3).

    GET /api/v1/email/triage     SirisAI's drafted replies: who, subject, the email's opening, the draft

Sending, snoozing and leaving one use the Inbox routes:
POST /api/v1/attention/{id}/act {"action": "send", "body": "<edited reply>"},
POST /api/v1/attention/{id}/snooze and POST /api/v1/attention/{id}/dismiss.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.auth import require_user
from app.email_triage import service
from app.hub.service import Hub, get_hub

router = APIRouter(prefix="/api/v1/email", tags=["email"], dependencies=[Depends(require_user)])


@router.get("/triage")
async def triage(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    try:
        return await service.replies(hub)
    except Exception:  # noqa: BLE001 - SirisAI down reads as "unavailable", not a 500
        return {"replies": [], "snoozed": 0, "unavailable": True}
