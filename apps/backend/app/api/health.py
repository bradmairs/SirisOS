from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.services.health_mcp_service import HealthMcpService

router = APIRouter(prefix="/health", tags=["health"])
service = HealthMcpService()


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


def _require_bearer(authorization: Annotated[str | None, Header()] = None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")


@router.get("/snapshot", response_model=HealthSnapshotResponse)
async def health_snapshot(
    authorization: Annotated[str | None, Header()] = None,
) -> HealthSnapshotResponse:
    _require_bearer(authorization)
    snapshot = service.snapshot()
    return HealthSnapshotResponse(
        available=snapshot.available,
        endpoint_configured=snapshot.endpoint_configured,
        tools=snapshot.tools,
        metrics=[HealthMetricResponse(**item.__dict__) for item in snapshot.metrics],
        error=snapshot.error,
    )
