from dataclasses import dataclass
import os
from threading import Lock, Thread
from time import monotonic

import docker
from docker.errors import DockerException, ImageNotFound, NotFound

from app.services.activity_service import ActivityService
from app.services.homelab_audit_service import HomelabAuditService


PROTECTED_CONTAINERS = {
    "sirisos-web",
    "sirisos-api",
    "sirisos-postgres",
    "sirisos-docker-proxy",
    "sirisos-node-exporter",
}
UPDATE_CACHE_TTL_SECONDS = 15 * 60


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
    update_available: bool = False
    update_check_error: str | None = None


@dataclass(frozen=True)
class DockerSummary:
    available: bool
    total: int
    running: int
    stopped: int
    unhealthy: int
    updates_available: int
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


def _digest(value: str | None) -> str | None:
    if not value:
        return None
    return value.split("@", 1)[-1] if "@" in value else value


class DockerMonitor:
    """Docker status, cached image-update checks, logs, and lifecycle controls."""

    def __init__(self) -> None:
        self._audit = HomelabAuditService()
        self._audit.initialise()
        self._activity = ActivityService()
        self._activity.initialise()
        self._username = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
        self._update_cache: dict[str, tuple[bool, str | None]] = {}
        self._update_cache_at = 0.0
        self._update_refresh_running = False
        self._update_lock = Lock()

    def _update_status(self, client, image_name: str) -> tuple[bool, str | None]:
        if image_name in {"", "unknown"} or "@sha256:" in image_name:
            return False, None
        try:
            local = client.images.get(image_name)
            repo_digests = local.attrs.get("RepoDigests") or []
            local_digests = {_digest(str(item)) for item in repo_digests}
            local_digests.discard(None)
            if not local_digests:
                return False, "Local image has no repository digest."
            remote = client.images.get_registry_data(image_name)
            remote_digest = _digest(str(remote.id))
            return remote_digest is not None and remote_digest not in local_digests, None
        except (DockerException, ImageNotFound) as exc:
            return False, str(exc)

    def _schedule_update_refresh(self, image_names: set[str]) -> None:
        with self._update_lock:
            cache_fresh = (
                bool(self._update_cache)
                and monotonic() - self._update_cache_at < UPDATE_CACHE_TTL_SECONDS
            )
            if cache_fresh or self._update_refresh_running or not image_names:
                return
            self._update_refresh_running = True

        Thread(
            target=self._refresh_update_cache,
            args=(image_names,),
            name="sirisos-docker-update-check",
            daemon=True,
        ).start()

    def _refresh_update_cache(self, image_names: set[str]) -> None:
        refreshed: dict[str, tuple[bool, str | None]] = {}
        try:
            client = docker.from_env(timeout=5)
            for image_name in sorted(image_names):
                refreshed[image_name] = self._update_status(client, image_name)
        except DockerException:
            # Keep the previous cache when Docker itself is temporarily unavailable.
            refreshed = {}
        finally:
            with self._update_lock:
                if refreshed:
                    self._update_cache = refreshed
                    self._update_cache_at = monotonic()
                self._update_refresh_running = False

    def _cached_update_status(self, image_name: str) -> tuple[bool, str | None]:
        with self._update_lock:
            return self._update_cache.get(image_name, (False, None))

    def collect(self, *, check_updates: bool = False) -> DockerSummary:
        """Collect live Docker state without waiting on external registries.

        `check_updates` is retained for API compatibility, but registry access is
        always performed asynchronously and cached. This keeps authentication,
        dashboards, alerts, and connector refreshes responsive even when a
        registry is slow or unavailable.
        """
        try:
            client = docker.from_env(timeout=5)
            containers = client.containers.list(all=True)
            image_names = {
                str((container.attrs.get("Config", {}) or {}).get("Image") or "unknown")
                for container in containers
            }
            self._schedule_update_refresh(image_names)

            items: list[DockerContainer] = []
            for container in containers:
                attrs = container.attrs
                state_data = attrs.get("State", {})
                health_data = state_data.get("Health") or {}
                config_data = attrs.get("Config", {})
                image_name = str(config_data.get("Image") or "unknown")
                state = str(state_data.get("Status", container.status))
                cpu_percent = memory_usage = memory_limit = memory_percent = None
                if state == "running":
                    try:
                        stats = container.stats(stream=False, one_shot=True)
                        cpu_percent = _cpu_percent(stats)
                        memory_usage, memory_limit, memory_percent = _memory_metrics(stats)
                    except DockerException:
                        pass
                update_available, update_error = self._cached_update_status(image_name)
                items.append(DockerContainer(
                    container_id=container.short_id,
                    name=container.name,
                    image=image_name,
                    state=state,
                    status=container.status,
                    health=str(health_data.get("Status")) if health_data.get("Status") else None,
                    cpu_percent=cpu_percent,
                    memory_usage_bytes=memory_usage,
                    memory_limit_bytes=memory_limit,
                    memory_percent=memory_percent,
                    update_available=update_available,
                    update_check_error=update_error,
                ))
            running = sum(item.state == "running" for item in items)
            unhealthy = sum(item.health == "unhealthy" for item in items)
            updates_available = sum(item.update_available for item in items)
            return DockerSummary(
                True,
                len(items),
                running,
                len(items) - running,
                unhealthy,
                updates_available,
                sorted(items, key=lambda item: item.name.lower()),
            )
        except DockerException as exc:
            return DockerSummary(False, 0, 0, 0, 0, 0, [], str(exc))

    def logs(self, container_id: str, *, tail: int = 300) -> str:
        safe_tail = max(20, min(tail, 1000))
        try:
            container = docker.from_env(timeout=5).containers.get(container_id)
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
            container = docker.from_env(timeout=5).containers.get(container_id)
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
            self._record(container_id, container_name, action, "success", status)
            return status
        except PermissionError as exc:
            self._record(container_id, container_name, action, "blocked", str(exc))
            raise
        except NotFound as exc:
            self._record(container_id, container_name, action, "failed", "Container not found.")
            raise LookupError("Container not found.") from exc
        except DockerException as exc:
            self._record(container_id, container_name, action, "failed", str(exc))
            raise RuntimeError(str(exc)) from exc

    def _record(self, container_id: str, container_name: str | None, action: str, result: str, detail: str | None) -> None:
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
            pass
        try:
            name = container_name or container_id
            severity = "success" if result == "success" else "warning" if result == "blocked" else "critical"
            title = f"Container {action} {result}"
            message = f"{name}: {detail or result}."
            self._activity.record(
                module="homelab",
                event_type=f"container_{action}_{result}",
                title=title,
                message=message,
                severity=severity,
                user=self._username,
            )
        except Exception:
            pass
