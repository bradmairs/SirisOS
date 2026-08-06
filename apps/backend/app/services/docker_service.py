from dataclasses import dataclass

import docker
from docker.errors import DockerException


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

    cpu_delta = int(cpu_usage.get("total_usage") or 0) - int(
        precpu_usage.get("total_usage") or 0
    )
    system_delta = int(cpu_stats.get("system_cpu_usage") or 0) - int(
        precpu_stats.get("system_cpu_usage") or 0
    )
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
    percent = round((usage_int / limit_int) * 100.0, 2)
    return usage_int, limit_int, percent


class DockerMonitor:
    """Read-only Docker status and resource collector.

    The Docker SDK reads its connection details from environment variables. In the
    Compose deployment, `DOCKER_HOST` points to a restricted socket proxy instead
    of mounting the host Docker socket into the API container directly.
    """

    def collect(self) -> DockerSummary:
        try:
            client = docker.from_env()
            containers = client.containers.list(all=True)
            items: list[DockerContainer] = []

            for container in containers:
                attrs = container.attrs
                state_data = attrs.get("State", {})
                health_data = state_data.get("Health") or {}
                health = health_data.get("Status")
                config_data = attrs.get("Config", {})
                image = str(config_data.get("Image") or "unknown")
                state = str(state_data.get("Status", container.status))

                cpu_percent: float | None = None
                memory_usage: int | None = None
                memory_limit: int | None = None
                memory_percent: float | None = None

                if state == "running":
                    try:
                        stats = container.stats(stream=False, one_shot=True)
                        cpu_percent = _cpu_percent(stats)
                        memory_usage, memory_limit, memory_percent = _memory_metrics(
                            stats
                        )
                    except DockerException:
                        # A container may stop between listing and reading stats.
                        pass

                items.append(
                    DockerContainer(
                        container_id=container.short_id,
                        name=container.name,
                        image=image,
                        state=state,
                        status=container.status,
                        health=str(health) if health else None,
                        cpu_percent=cpu_percent,
                        memory_usage_bytes=memory_usage,
                        memory_limit_bytes=memory_limit,
                        memory_percent=memory_percent,
                    )
                )

            running = sum(item.state == "running" for item in items)
            unhealthy = sum(item.health == "unhealthy" for item in items)

            return DockerSummary(
                available=True,
                total=len(items),
                running=running,
                stopped=len(items) - running,
                unhealthy=unhealthy,
                containers=sorted(items, key=lambda item: item.name.lower()),
            )
        except DockerException as exc:
            return DockerSummary(
                available=False,
                total=0,
                running=0,
                stopped=0,
                unhealthy=0,
                containers=[],
                error=str(exc),
            )
