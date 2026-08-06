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
) -> list[ActivityEventResponse]:
    _authenticate(authorization)
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
        )
        for item in service.list_events(limit=limit)
    ]
