from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

from app.services.docker_service import DockerMonitor
from app.services.host_metrics_service import HostMetricsCollector

CPU_WARNING = float(os.getenv("SIRISOS_CPU_WARNING_PERCENT", "80"))
CPU_CRITICAL = float(os.getenv("SIRISOS_CPU_CRITICAL_PERCENT", "95"))
MEMORY_WARNING = float(os.getenv("SIRISOS_MEMORY_WARNING_PERCENT", "80"))
MEMORY_CRITICAL = float(os.getenv("SIRISOS_MEMORY_CRITICAL_PERCENT", "95"))
DISK_WARNING = float(os.getenv("SIRISOS_DISK_WARNING_PERCENT", "80"))
DISK_CRITICAL = float(os.getenv("SIRISOS_DISK_CRITICAL_PERCENT", "90"))


@dataclass(frozen=True)
class HomelabAlert:
    id: str
    severity: Literal["warning", "critical"]
    source: str
    title: str
    message: str
    value: float | None = None
    threshold: float | None = None


@dataclass(frozen=True)
class HomelabAlertSummary:
    status: Literal["healthy", "warning", "critical"]
    warning_count: int
    critical_count: int
    alerts: list[HomelabAlert] = field(default_factory=list)


def _metric_alert(name: str, value: float | None, warning: float, critical: float) -> HomelabAlert | None:
    if value is None:
        return None
    if value >= critical:
        severity: Literal["warning", "critical"] = "critical"
        threshold = critical
    elif value >= warning:
        severity = "warning"
        threshold = warning
    else:
        return None
    return HomelabAlert(
        id=f"host-{name.lower()}",
        severity=severity,
        source="Host",
        title=f"High {name} usage",
        message=f"{name} is at {value:.1f}%, above the {severity} threshold of {threshold:.0f}%.",
        value=value,
        threshold=threshold,
    )


class HomelabAlertService:
    def __init__(
        self,
        host_metrics_collector: HostMetricsCollector | None = None,
        docker_monitor: DockerMonitor | None = None,
    ) -> None:
        self._collector = host_metrics_collector or HostMetricsCollector()
        self._docker_monitor = docker_monitor or DockerMonitor()

    def get_summary(self) -> HomelabAlertSummary:
        items: list[HomelabAlert] = []

        host = self._collector.collect()
        if host.available:
            for alert in (
                _metric_alert("CPU", host.cpu_percent, CPU_WARNING, CPU_CRITICAL),
                _metric_alert("Memory", host.memory_percent, MEMORY_WARNING, MEMORY_CRITICAL),
                _metric_alert("Disk", host.disk_percent, DISK_WARNING, DISK_CRITICAL),
            ):
                if alert is not None:
                    items.append(alert)

        docker = self._docker_monitor.collect()
        if not docker.available:
            items.append(
                HomelabAlert(
                    id="docker-unavailable",
                    severity="critical",
                    source="Docker",
                    title="Docker monitoring unavailable",
                    message=docker.error or "The Docker socket proxy cannot be reached.",
                )
            )
        else:
            for container in docker.containers:
                if container.health == "unhealthy":
                    items.append(
                        HomelabAlert(
                            id=f"container-{container.container_id}-unhealthy",
                            severity="critical",
                            source=container.name,
                            title="Container unhealthy",
                            message=f"{container.name} is reporting an unhealthy status.",
                        )
                    )
                elif container.state != "running":
                    items.append(
                        HomelabAlert(
                            id=f"container-{container.container_id}-stopped",
                            severity="warning",
                            source=container.name,
                            title="Container not running",
                            message=f"{container.name} is currently {container.state}.",
                        )
                    )
                if container.update_available:
                    items.append(
                        HomelabAlert(
                            id=f"container-{container.container_id}-update",
                            severity="warning",
                            source=container.name,
                            title="Container image update available",
                            message=f"A newer image is available for {container.image}.",
                        )
                    )

        warning_count = sum(item.severity == "warning" for item in items)
        critical_count = sum(item.severity == "critical" for item in items)
        status: Literal["healthy", "warning", "critical"] = (
            "critical" if critical_count else "warning" if warning_count else "healthy"
        )
        return HomelabAlertSummary(
            status=status, warning_count=warning_count, critical_count=critical_count, alerts=items
        )
