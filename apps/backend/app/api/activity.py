import os
from typing import Annotated, Literal

import jwt
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from app.services.activity_service import ActivityService

router = APIRouter(prefix="/api/v1/activity", tags=["activity"])
service = ActivityService()
service.initialise()

AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")


class ActivityEventResponse(BaseModel):
    id: int
    occurred_at: str
    module: str
    event_type: str
    title: str
    message: str
    severity: Literal["info", "success", "warning", "critical"]
    user: str | None
    is_unread: bool


class NotificationSummaryResponse(BaseModel):
    unread_count: int


class MarkReadResponse(BaseModel):
    last_read_event_id: int
    unread_count: int = 0


def _authenticate(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        payload = jwt.decode(
            authorization.removeprefix("Bearer ").strip(),
            JWT_SECRET,
            algorithms=["HS256"],
            issuer="sirisos-api",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session.") from exc
    username = payload.get("sub")
    if username != AUTH_USERNAME:
        raise HTTPException(status_code=401, detail="Invalid session user.")
    return AUTH_USERNAME


@router.get("", response_model=list[ActivityEventResponse])
async def activity_feed(
    authorization: Annotated[str | None, Header()] = None,
    limit: int = Query(default=30, ge=1, le=200),
    severity: Literal["all", "info", "success", "warning", "critical"] = "all",
) -> list[ActivityEventResponse]:
    username = _authenticate(authorization)
    last_read = service.last_read_event_id(username)
    return [
        ActivityEventResponse(
            id=item.id,
            occurred_at=item.occurred_at.isoformat(),
            module=item.module,
            event_type=item.event_type,
            title=item.title,
            message=item.message,
            severity=item.severity,
            user=item.user,
            is_unread=item.id > last_read,
        )
        for item in service.list_events(limit=limit, severity=severity)
    ]


@router.get("/notifications", response_model=NotificationSummaryResponse)
async def notification_summary(
    authorization: Annotated[str | None, Header()] = None,
) -> NotificationSummaryResponse:
    username = _authenticate(authorization)
    return NotificationSummaryResponse(unread_count=service.unread_count(username))


@router.post("/notifications/read-all", response_model=MarkReadResponse)
async def mark_all_notifications_read(
    authorization: Annotated[str | None, Header()] = None,
) -> MarkReadResponse:
    username = _authenticate(authorization)
    latest_id = service.mark_all_read(username)
    return MarkReadResponse(last_read_event_id=latest_id)
