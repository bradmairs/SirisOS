from dataclasses import dataclass
import os

import docker
from docker.errors import DockerException, NotFound

from app.services.homelab_audit_service import HomelabAuditService


PROTECTED_CONTAINERS = {
    "sirisos-web",
    "sirisos-api",
    "sirisos-postgres",
    "sirisos-docker-proxy",
    "sirisos-node-exporter",
}


@dataclass(frozen=True)
class DockerContainer:
    container_id: str
    name: str
    image: str
    state: str
    status: str
    health: str | None
    cpu_percent: float | None
    memory_usage_bytes: int | None
    memory_limit_bytes: int | None
    memory_percent: float | None


@dataclass(frozen=True)
class DockerSummary:
    available: bool
    total: int
    running: int
    stopped: int
    unhealthy: int
    containers: list[DockerContainer]
    error: str | None = None


def _cpu_percent(stats: dict) -> float | None:
    cpu_stats = stats.get("cpu_stats") or {}
    precpu_stats = stats.get("precpu_stats") or {}
    cpu_usage = cpu_stats.get("cpu_usage") or {}
    precpu_usage = precpu_stats.get("cpu_usage") or {}
    cpu_delta = int(cpu_usage.get("total_usage") or 0) - int(precpu_usage.get("total_usage") or 0)
    system_delta = int(cpu_stats.get("system_cpu_usage") or 0) - int(precpu_stats.get("system_cpu_usage") or 0)
    online_cpus = int(cpu_stats.get("online_cpus") or 0)
    if online_cpus <= 0:
        online_cpus = len(cpu_usage.get("percpu_usage") or []) or 1
    if cpu_delta <= 0 or system_delta <= 0:
        return 0.0
    return round((cpu_delta / system_delta) * online_cpus * 100.0, 2)


def _memory_metrics(stats: dict) -> tuple[int | None, int | None, float | None]:
    memory_stats = stats.get("memory_stats") or {}
    usage = memory_stats.get("usage")
    limit = memory_stats.get("limit")
    if usage is None or limit in (None, 0):
        return None, None, None
    usage_int = int(usage)
    limit_int = int(limit)
    return usage_int, limit_int, round((usage_int / limit_int) * 100.0, 2)


class DockerMonitor:
    """Docker status, logs, and tightly constrained lifecycle controls."""

    def __init__(self) -> None:
        self._audit = HomelabAuditService()
        self._audit.initialise()
        self._username = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")

    def collect(self) -> DockerSummary:
        try:
            client = docker.from_env()
            containers = client.containers.list(all=True)
            items: list[DockerContainer] = []
            for container in containers:
                attrs = container.attrs
                state_data = attrs.get("State", {})
                health_data = state_data.get("Health") or {}
                config_data = attrs.get("Config", {})
                state = str(state_data.get("Status", container.status))
                cpu_percent = memory_usage = memory_limit = memory_percent = None
                if state == "running":
                    try:
                        stats = container.stats(stream=False, one_shot=True)
                        cpu_percent = _cpu_percent(stats)
                        memory_usage, memory_limit, memory_percent = _memory_metrics(stats)
                    except DockerException:
                        pass
                items.append(DockerContainer(
                    container_id=container.short_id,
                    name=container.name,
                    image=str(config_data.get("Image") or "unknown"),
                    state=state,
                    status=container.status,
                    health=str(health_data.get("Status")) if health_data.get("Status") else None,
                    cpu_percent=cpu_percent,
                    memory_usage_bytes=memory_usage,
                    memory_limit_bytes=memory_limit,
                    memory_percent=memory_percent,
                ))
            running = sum(item.state == "running" for item in items)
            unhealthy = sum(item.health == "unhealthy" for item in items)
            return DockerSummary(True, len(items), running, len(items) - running, unhealthy, sorted(items, key=lambda item: item.name.lower()))
        except DockerException as exc:
            return DockerSummary(False, 0, 0, 0, 0, [], str(exc))

    def logs(self, container_id: str, *, tail: int = 300) -> str:
        safe_tail = max(20, min(tail, 1000))
        try:
            container = docker.from_env().containers.get(container_id)
            output = container.logs(stdout=True, stderr=True, timestamps=True, tail=safe_tail)
            return output.decode("utf-8", errors="replace")
        except NotFound as exc:
            raise LookupError("Container not found.") from exc
        except DockerException as exc:
            raise RuntimeError(str(exc)) from exc

    def action(self, container_id: str, action: str) -> str:
        if action not in {"start", "stop", "restart"}:
            raise ValueError("Unsupported container action.")

        container_name: str | None = None
        try:
            container = docker.from_env().containers.get(container_id)
            container_name = container.name
            if container.name in PROTECTED_CONTAINERS:
                raise PermissionError("Core SirisOS containers cannot be controlled from the app.")
            if action == "start":
                container.start()
            elif action == "stop":
                container.stop(timeout=10)
            else:
                container.restart(timeout=10)
            container.reload()
            status = str(container.status)
            self._record_audit(container_id, container_name, action, "success", status)
            return status
        except PermissionError as exc:
            self._record_audit(container_id, container_name, action, "blocked", str(exc))
            raise
        except NotFound as exc:
            self._record_audit(container_id, container_name, action, "failed", "Container not found.")
            raise LookupError("Container not found.") from exc
        except DockerException as exc:
            self._record_audit(container_id, container_name, action, "failed", str(exc))
            raise RuntimeError(str(exc)) from exc

    def _record_audit(
        self,
        container_id: str,
        container_name: str | None,
        action: str,
        result: str,
        detail: str | None,
    ) -> None:
        try:
            self._audit.record(
                username=self._username,
                container_id=container_id,
                container_name=container_name,
                action=action,
                result=result,
                detail=detail,
            )
        except Exception:
            # Audit persistence must not obscure the underlying Docker result.
            pass
