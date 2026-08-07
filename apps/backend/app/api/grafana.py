from datetime import datetime
import os
from typing import Annotated

import jwt
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from app.services.grafana_service import GrafanaService

router = APIRouter(prefix="/api/v1/homelab/grafana", tags=["homelab"])

AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")

grafana_service = GrafanaService()


class GrafanaDashboardResponse(BaseModel):
    uid: str
    title: str
    url: str
    folder_title: str | None = None
    tags: list[str]


class GrafanaSnapshotResponse(BaseModel):
    configured: bool
    available: bool
    version: str | None = None
    dashboard_count: int
    dashboards: list[GrafanaDashboardResponse]
    rendering_enabled: bool
    generated_at: str
    error: str | None = None


class GrafanaRenderResponse(BaseModel):
    image_base64: str
    generated_at: str


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


@router.get("", response_model=GrafanaSnapshotResponse)
async def grafana_snapshot(
    authorization: Annotated[str | None, Header()] = None,
) -> GrafanaSnapshotResponse:
    _authenticate(authorization)
    snapshot = await grafana_service.snapshot()
    return GrafanaSnapshotResponse(
        configured=snapshot.configured,
        available=snapshot.available,
        version=snapshot.version,
        dashboard_count=len(snapshot.dashboards),
        dashboards=[
            GrafanaDashboardResponse(
                uid=item.uid,
                title=item.title,
                url=item.url,
                folder_title=item.folder_title,
                tags=list(item.tags),
            )
            for item in snapshot.dashboards
        ],
        rendering_enabled=grafana_service.rendering_enabled,
        generated_at=datetime.now().astimezone().isoformat(),
        error=snapshot.error,
    )


@router.get("/render", response_model=GrafanaRenderResponse)
async def grafana_render(
    dashboard_uid: str = Query(min_length=1, max_length=128),
    slug: str = Query(min_length=1, max_length=128),
    panel_id: str = Query(min_length=1, max_length=128),
    width: int = Query(default=1000, ge=320, le=2000),
    height: int = Query(default=500, ge=180, le=1200),
    authorization: Annotated[str | None, Header()] = None,
) -> GrafanaRenderResponse:
    _authenticate(authorization)
    try:
        encoded = await grafana_service.render_panel(
            dashboard_uid=dashboard_uid,
            slug=slug,
            panel_id=panel_id,
            width=width,
            height=height,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Grafana render failed: {type(exc).__name__}") from exc
    return GrafanaRenderResponse(
        image_base64=encoded,
        generated_at=datetime.now().astimezone().isoformat(),
    )
