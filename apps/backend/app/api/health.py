import os
from typing import Annotated

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.services.health_mcp_service import HealthMcpService

router = APIRouter(prefix="/health", tags=["health"])
service = HealthMcpService()

AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")


class HealthMetricResponse(BaseModel):
    name: str
    value: float | str | None
    unit: str | None
    date: str | None


class HealthSnapshotResponse(BaseModel):
    available: bool
    endpoint_configured: bool
    tools: list[str]
    metrics: list[HealthMetricResponse]
    error: str | None = None


def _authenticate(authorization: Annotated[str | None, Header()] = None) -> None:
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
    if payload.get("sub") != AUTH_USERNAME:
        raise HTTPException(status_code=401, detail="Invalid session user.")


@router.get("/snapshot", response_model=HealthSnapshotResponse)
async def health_snapshot(
    authorization: Annotated[str | None, Header()] = None,
) -> HealthSnapshotResponse:
    _authenticate(authorization)
    snapshot = service.snapshot()
    return HealthSnapshotResponse(
        available=snapshot.available,
        endpoint_configured=snapshot.endpoint_configured,
        tools=snapshot.tools,
        metrics=[HealthMetricResponse(**item.__dict__) for item in snapshot.metrics],
        error=snapshot.error,
    )
