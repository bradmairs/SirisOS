from datetime import datetime
import os
from typing import Annotated, Literal

import httpx
import jwt
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from app.services.docker_service import DockerMonitor
from app.services.home_assistant_service import HomeAssistantService
from app.services.homelab_audit_service import HomelabAuditService
from app.services.host_metrics_service import HostMetricsCollector
from app.services.prometheus_service import PrometheusService

router = APIRouter(prefix="/api/v1/homelab", tags=["homelab"])

AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
CPU_WARNING = float(os.getenv("SIRISOS_CPU_WARNING_PERCENT", "80"))
CPU_CRITICAL = float(os.getenv("SIRISOS_CPU_CRITICAL_PERCENT", "95"))
MEMORY_WARNING = float(os.getenv("SIRISOS_MEMORY_WARNING_PERCENT", "80"))
MEMORY_CRITICAL = float(os.getenv("SIRISOS_MEMORY_CRITICAL_PERCENT", "95"))
DISK_WARNING = float(os.getenv("SIRISOS_DISK_WARNING_PERCENT", "80"))
DISK_CRITICAL = float(os.getenv("SIRISOS_DISK_CRITICAL_PERCENT", "90"))

collector = HostMetricsCollector()
docker_monitor = DockerMonitor()
home_assistant_service = HomeAssistantService()
prometheus_service = PrometheusService()
audit_service = HomelabAuditService()
audit_service.initialise()


class AlertResponse(BaseModel):
    id: str
    severity: Literal["warning", "critical"]
    source: str
    title: str
    message: str
    value: float | None = None
    threshold: float | None = None


class AlertSummaryResponse(BaseModel):
    status: Literal["healthy", "warning", "critical"]
    warning_count: int
    critical_count: int
    alerts: list[AlertResponse]


class AuditEventResponse(BaseModel):
    id: int
    occurred_at: str
    username: str
    container_id: str
    container_name: str | None
    action: str
    result: str
    detail: str | None


class IntegrationStatusResponse(BaseModel):
    key: str
    name: str
    configured: bool
    available: bool
    status: Literal["healthy", "warning", "unconfigured"]
    detail: str
    version: str | None = None
    latency_ms: int | None = None


class IntegrationDiagnosticsResponse(BaseModel):
    integrations: list[IntegrationStatusResponse]
    healthy: int
    configured: int
    total: int
    generated_at: str


class DockerUpdateResponse(BaseModel):
    container_id: str
    name: str
    image: str
    update_available: bool
    update_check_error: str | None = None


class DockerUpdateSummaryResponse(BaseModel):
    available: bool
    updates_available: int
    containers: list[DockerUpdateResponse]
    generated_at: str
    error: str | None = None


class HomeAssistantEntityResponse(BaseModel):
    entity_id: str
    state: str
    name: str
    domain: str
    last_changed: str | None = None


class HomeAssistantSnapshotResponse(BaseModel):
    configured: bool
    available: bool
    total: int
    unavailable: int
    entities: list[HomeAssistantEntityResponse]
    generated_at: str
    error: str | None = None


class HomeAssistantActionRequest(BaseModel):
    domain: str
    service: str
    entity_id: str


class HomeAssistantActionResponse(BaseModel):
    accepted: bool
    entity_id: str
    service: str
    generated_at: str


class PrometheusSnapshotResponse(BaseModel):
    configured: bool
    available: bool
    healthy_targets: int
    unhealthy_targets: int
    total_targets: int
    generated_at: str
    error: str | None = None


class PrometheusQueryResponse(BaseModel):
    expression: str
    result: list[dict]
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


def _metric_alert(name: str, value: float | None, warning: float, critical: float) -> AlertResponse | None:
    if value is None:
        return None
    if value >= critical:
        severity = "critical"
        threshold = critical
    elif value >= warning:
        severity = "warning"
        threshold = warning
    else:
        return None
    return AlertResponse(
        id=f"host-{name.lower()}",
        severity=severity,
        source="Host",
        title=f"High {name} usage",
        message=f"{name} is at {value:.1f}%, above the {severity} threshold of {threshold:.0f}%.",
        value=value,
        threshold=threshold,
    )


async def _probe_integration(
    *,
    key: str,
    name: str,
    base_url: str | None,
    path: str,
    headers: dict[str, str] | None = None,
    version_header: str | None = None,
) -> IntegrationStatusResponse:
    if not base_url:
        return IntegrationStatusResponse(
            key=key,
            name=name,
            configured=False,
            available=False,
            status="unconfigured",
            detail="Not configured",
        )

    started = datetime.now()
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            response = await client.get(f"{base_url.rstrip('/')}{path}", headers=headers)
        latency_ms = int((datetime.now() - started).total_seconds() * 1000)
        response.raise_for_status()
        return IntegrationStatusResponse(
            key=key,
            name=name,
            configured=True,
            available=True,
            status="healthy",
            detail="Connected",
            version=response.headers.get(version_header) if version_header else None,
            latency_ms=latency_ms,
        )
    except (httpx.HTTPError, ValueError) as exc:
        return IntegrationStatusResponse(
            key=key,
            name=name,
            configured=True,
            available=False,
            status="warning",
            detail=f"Connection failed: {type(exc).__name__}",
        )


@router.get("/alerts", response_model=AlertSummaryResponse)
async def alerts(authorization: Annotated[str | None, Header()] = None) -> AlertSummaryResponse:
    _authenticate(authorization)
    items: list[AlertResponse] = []

    host = collector.collect()
    if host.available:
        for alert in (
            _metric_alert("CPU", host.cpu_percent, CPU_WARNING, CPU_CRITICAL),
            _metric_alert("Memory", host.memory_percent, MEMORY_WARNING, MEMORY_CRITICAL),
            _metric_alert("Disk", host.disk_percent, DISK_WARNING, DISK_CRITICAL),
        ):
            if alert is not None:
                items.append(alert)

    docker = docker_monitor.collect()
    if not docker.available:
        items.append(AlertResponse(id="docker-unavailable", severity="critical", source="Docker", title="Docker monitoring unavailable", message=docker.error or "The Docker socket proxy cannot be reached."))
    else:
        for container in docker.containers:
            if container.health == "unhealthy":
                items.append(AlertResponse(id=f"container-{container.container_id}-unhealthy", severity="critical", source=container.name, title="Container unhealthy", message=f"{container.name} is reporting an unhealthy status."))
            elif container.state != "running":
                items.append(AlertResponse(id=f"container-{container.container_id}-stopped", severity="warning", source=container.name, title="Container not running", message=f"{container.name} is currently {container.state}."))
            if container.update_available:
                items.append(AlertResponse(id=f"container-{container.container_id}-update", severity="warning", source=container.name, title="Container image update available", message=f"A newer image is available for {container.image}."))

    warning_count = sum(item.severity == "warning" for item in items)
    critical_count = sum(item.severity == "critical" for item in items)
    status_value: Literal["healthy", "warning", "critical"] = "critical" if critical_count else "warning" if warning_count else "healthy"
    return AlertSummaryResponse(status=status_value, warning_count=warning_count, critical_count=critical_count, alerts=items)


@router.get("/docker/updates", response_model=DockerUpdateSummaryResponse)
async def docker_updates(
    authorization: Annotated[str | None, Header()] = None,
) -> DockerUpdateSummaryResponse:
    _authenticate(authorization)
    summary = docker_monitor.collect()
    return DockerUpdateSummaryResponse(
        available=summary.available,
        updates_available=summary.updates_available,
        containers=[
            DockerUpdateResponse(
                container_id=item.container_id,
                name=item.name,
                image=item.image,
                update_available=item.update_available,
                update_check_error=item.update_check_error,
            )
            for item in summary.containers
        ],
        generated_at=datetime.now().astimezone().isoformat(),
        error=summary.error,
    )


@router.get("/home-assistant/states", response_model=HomeAssistantSnapshotResponse)
async def home_assistant_states(
    authorization: Annotated[str | None, Header()] = None,
) -> HomeAssistantSnapshotResponse:
    _authenticate(authorization)
    snapshot = await home_assistant_service.snapshot()
    unavailable = sum(item.state in {"unavailable", "unknown"} for item in snapshot.entities)
    return HomeAssistantSnapshotResponse(
        configured=snapshot.configured,
        available=snapshot.available,
        total=len(snapshot.entities),
        unavailable=unavailable,
        entities=[HomeAssistantEntityResponse(**item.__dict__) for item in snapshot.entities],
        generated_at=datetime.now().astimezone().isoformat(),
        error=snapshot.error,
    )


@router.post("/home-assistant/action", response_model=HomeAssistantActionResponse)
async def home_assistant_action(
    request: HomeAssistantActionRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> HomeAssistantActionResponse:
    _authenticate(authorization)
    try:
        await home_assistant_service.call_service(
            request.domain,
            request.service,
            request.entity_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return HomeAssistantActionResponse(
        accepted=True,
        entity_id=request.entity_id,
        service=f"{request.domain}.{request.service}",
        generated_at=datetime.now().astimezone().isoformat(),
    )


@router.get("/prometheus", response_model=PrometheusSnapshotResponse)
async def prometheus_snapshot(
    authorization: Annotated[str | None, Header()] = None,
) -> PrometheusSnapshotResponse:
    _authenticate(authorization)
    snapshot = await prometheus_service.snapshot()
    return PrometheusSnapshotResponse(**snapshot.__dict__)


@router.get("/prometheus/query", response_model=PrometheusQueryResponse)
async def prometheus_query(
    query: Annotated[str, Query(min_length=1, max_length=1000)],
    authorization: Annotated[str | None, Header()] = None,
) -> PrometheusQueryResponse:
    _authenticate(authorization)
    try:
        result = await prometheus_service.query(query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return PrometheusQueryResponse(
        expression=query,
        result=result,
        generated_at=datetime.now().astimezone().isoformat(),
    )


@router.get("/audit", response_model=list[AuditEventResponse])
async def audit_history(
    authorization: Annotated[str | None, Header()] = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AuditEventResponse]:
    _authenticate(authorization)
    return [
        AuditEventResponse(
            id=item.id,
            occurred_at=item.occurred_at.isoformat(),
            username=item.username,
            container_id=item.container_id,
            container_name=item.container_name,
            action=item.action,
            result=item.result,
            detail=item.detail,
        )
        for item in audit_service.recent(limit=limit)
    ]


@router.get("/integrations", response_model=IntegrationDiagnosticsResponse)
async def integration_diagnostics(
    authorization: Annotated[str | None, Header()] = None,
) -> IntegrationDiagnosticsResponse:
    _authenticate(authorization)
    home_assistant_url = os.getenv("HOME_ASSISTANT_URL")
    home_assistant_token = os.getenv("HOME_ASSISTANT_TOKEN")
    plex_url = os.getenv("PLEX_URL")
    plex_token = os.getenv("PLEX_TOKEN")

    results = [
        await _probe_integration(
            key="home_assistant",
            name="Home Assistant",
            base_url=home_assistant_url if home_assistant_token else None,
            path="/api/",
            headers={"Authorization": f"Bearer {home_assistant_token}"} if home_assistant_token else None,
        ),
        await _probe_integration(
            key="prometheus",
            name="Prometheus",
            base_url=os.getenv("PROMETHEUS_URL"),
            path="/-/ready",
        ),
        await _probe_integration(
            key="plex",
            name="Plex",
            base_url=plex_url if plex_token else None,
            path="/identity",
            headers={"X-Plex-Token": plex_token} if plex_token else None,
            version_header="X-Plex-Version",
        ),
        await _probe_integration(
            key="ollama",
            name="Ollama",
            base_url=os.getenv("OLLAMA_URL"),
            path="/api/version",
        ),
    ]

    return IntegrationDiagnosticsResponse(
        integrations=results,
        healthy=sum(item.available for item in results),
        configured=sum(item.configured for item in results),
        total=len(results),
        generated_at=datetime.now().astimezone().isoformat(),
    )
