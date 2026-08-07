from datetime import datetime
import os
from typing import Annotated

import jwt
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from app.services.grafana_service import GrafanaService
from app.services.unifi_service import UniFiService

router = APIRouter(prefix="/api/v1/homelab", tags=["homelab"])

AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")

grafana_service = GrafanaService()
unifi_service = UniFiService()


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


class UniFiDeviceResponse(BaseModel):
    id: str
    name: str
    model: str
    state: str
    ip_address: str | None = None
    firmware_version: str | None = None
    firmware_updatable: bool
    is_access_point: bool


class UniFiSnapshotResponse(BaseModel):
    configured: bool
    available: bool
    site_id: str | None = None
    site_name: str | None = None
    total_devices: int
    online_devices: int
    offline_devices: int
    access_points: int
    connected_clients: int
    wan_interfaces: int
    devices: list[UniFiDeviceResponse]
    generated_at: str
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


@router.get("/grafana", response_model=GrafanaSnapshotResponse)
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


@router.get("/grafana/render", response_model=GrafanaRenderResponse)
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
        raise HTTPException(
            status_code=502,
            detail=f"Grafana render failed: {type(exc).__name__}",
        ) from exc
    return GrafanaRenderResponse(
        image_base64=encoded,
        generated_at=datetime.now().astimezone().isoformat(),
    )


@router.get("/unifi", response_model=UniFiSnapshotResponse)
async def unifi_snapshot(
    refresh: bool = Query(default=False),
    authorization: Annotated[str | None, Header()] = None,
) -> UniFiSnapshotResponse:
    _authenticate(authorization)
    snapshot = await unifi_service.snapshot(force=refresh)
    return UniFiSnapshotResponse(
        configured=snapshot.configured,
        available=snapshot.available,
        site_id=snapshot.site_id,
        site_name=snapshot.site_name,
        total_devices=snapshot.total_devices,
        online_devices=snapshot.online_devices,
        offline_devices=snapshot.offline_devices,
        access_points=snapshot.access_points,
        connected_clients=snapshot.connected_clients,
        wan_interfaces=snapshot.wan_interfaces,
        devices=[
            UniFiDeviceResponse(
                id=item.id,
                name=item.name,
                model=item.model,
                state=item.state,
                ip_address=item.ip_address,
                firmware_version=item.firmware_version,
                firmware_updatable=item.firmware_updatable,
                is_access_point=item.is_access_point,
            )
            for item in snapshot.devices
        ],
        generated_at=snapshot.generated_at,
        error=snapshot.error,
    )
