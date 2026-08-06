import os
from typing import Annotated, Literal

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.services.docker_service import DockerMonitor
from app.services.host_metrics_service import HostMetricsCollector

router = APIRouter(prefix="/api/v1/homelab/alerts", tags=["homelab"])

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


@router.get("", response_model=AlertSummaryResponse)
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

    warning_count = sum(item.severity == "warning" for item in items)
    critical_count = sum(item.severity == "critical" for item in items)
    status_value: Literal["healthy", "warning", "critical"] = "critical" if critical_count else "warning" if warning_count else "healthy"
    return AlertSummaryResponse(status=status_value, warning_count=warning_count, critical_count=critical_count, alerts=items)
