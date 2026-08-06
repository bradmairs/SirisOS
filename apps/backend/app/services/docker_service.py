from dataclasses import dataclass

import docker
from docker.errors import DockerException


@dataclass(frozen=True)
class DockerContainer:
    name: str
    image: str
    state: str
    status: str
    health: str | None


@dataclass(frozen=True)
class DockerSummary:
    available: bool
    total: int
    running: int
    stopped: int
    unhealthy: int
    containers: list[DockerContainer]
    error: str | None = None


class DockerMonitor:
    """Read-only Docker status collector.

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

                items.append(
                    DockerContainer(
                        name=container.name,
                        image=image,
                        state=str(state_data.get("Status", container.status)),
                        status=container.status,
                        health=str(health) if health else None,
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
