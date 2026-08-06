from datetime import datetime
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.services.docker_service import DockerMonitor


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


class DashboardCardResponse(BaseModel):
    title: str
    value: str
    subtitle: str
    status: Literal["healthy", "warning", "unknown"] = "unknown"


class DashboardResponse(BaseModel):
    greeting_name: str
    homelab: DashboardCardResponse
    recovery: DashboardCardResponse
    gym: DashboardCardResponse
    today: DashboardCardResponse
    briefing: str
    generated_at: str


class DockerContainerResponse(BaseModel):
    name: str
    image: str
    state: str
    status: str
    health: str | None


class DockerStatusResponse(BaseModel):
    available: bool
    total: int
    running: int
    stopped: int
    unhealthy: int
    containers: list[DockerContainerResponse]
    error: str | None = None


app = FastAPI(
    title="SirisOS API",
    description="Backend API for the SirisOS personal operating system.",
    version="0.3.0",
)

docker_monitor = DockerMonitor()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {
        "name": "SirisOS API",
        "version": "0.3.0",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="sirisos-api", version="0.3.0")


@app.get(
    "/api/v1/homelab/docker",
    response_model=DockerStatusResponse,
    tags=["homelab"],
)
async def docker_status() -> DockerStatusResponse:
    summary = docker_monitor.collect()
    return DockerStatusResponse(
        available=summary.available,
        total=summary.total,
        running=summary.running,
        stopped=summary.stopped,
        unhealthy=summary.unhealthy,
        containers=[
            DockerContainerResponse(
                name=item.name,
                image=item.image,
                state=item.state,
                status=item.status,
                health=item.health,
            )
            for item in summary.containers
        ],
        error=summary.error,
    )


def _homelab_card() -> tuple[DashboardCardResponse, str]:
    summary = docker_monitor.collect()

    if not summary.available:
        return (
            DashboardCardResponse(
                title="Homelab",
                value="Offline",
                subtitle="Docker socket is unavailable",
                status="warning",
            ),
            "Docker monitoring is unavailable. Check the Docker socket mount and permissions.",
        )

    if summary.total == 0:
        return (
            DashboardCardResponse(
                title="Homelab",
                value="No containers",
                subtitle="Docker is connected",
                status="unknown",
            ),
            "Docker is connected, but no containers were found on this host.",
        )

    if summary.unhealthy > 0 or summary.stopped > 0:
        issues = summary.unhealthy + summary.stopped
        return (
            DashboardCardResponse(
                title="Homelab",
                value=f"{summary.running}/{summary.total} running",
                subtitle=f"{issues} container issue{'s' if issues != 1 else ''}",
                status="warning",
            ),
            (
                f"Docker needs attention: {summary.running} of {summary.total} containers "
                f"are running, with {summary.unhealthy} unhealthy and {summary.stopped} stopped."
            ),
        )

    return (
        DashboardCardResponse(
            title="Homelab",
            value=f"{summary.running}/{summary.total} running",
            subtitle="All Docker containers are healthy",
            status="healthy",
        ),
        f"All {summary.total} Docker containers are running normally.",
    )


@app.get("/api/v1/dashboard", response_model=DashboardResponse, tags=["dashboard"])
async def dashboard() -> DashboardResponse:
    homelab, homelab_briefing = _homelab_card()

    return DashboardResponse(
        greeting_name="Brad",
        homelab=homelab,
        recovery=DashboardCardResponse(
            title="Recovery",
            value="Not connected",
            subtitle="Apple Health integration pending",
            status="unknown",
        ),
        gym=DashboardCardResponse(
            title="Gym",
            value="No workout",
            subtitle="Gym programming module pending",
            status="unknown",
        ),
        today=DashboardCardResponse(
            title="Today",
            value="No tasks",
            subtitle="Calendar and tasks are not connected yet",
            status="unknown",
        ),
        briefing=(
            f"{homelab_briefing} Health, gym, calendar, and AI integrations are still pending."
        ),
        generated_at=datetime.now().astimezone().isoformat(),
    )
