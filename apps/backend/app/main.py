from datetime import datetime, timedelta, timezone
import os
import secrets
from typing import Annotated, Literal

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.engineering_standards import router as engineering_standards_router
from app.api.grafana import router as grafana_router
from app.api.gym import router as gym_router
from app.api.homelab_alerts import router as homelab_alerts_router
from app.api.host_history import router as host_history_router
from app.api.running import router as running_router
from app.api.sirishydro import router as sirishydro_router
from app.services.docker_service import DockerMonitor
from app.services.gym_service import GymService
from app.services.host_metrics_service import HostMetricsCollector
from app.services.running_service import RunningService

API_VERSION = "0.13.0"
AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
AUTH_PASSWORD = os.getenv("SIRISOS_ADMIN_PASSWORD", "change-me")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
JWT_EXPIRY_HOURS = int(os.getenv("SIRISOS_JWT_EXPIRY_HOURS", "24"))
JWT_ALGORITHM = "HS256"


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    username: str


class CurrentUserResponse(BaseModel):
    username: str


class DashboardCardResponse(BaseModel):
    title: str
    value: str
    subtitle: str
    status: Literal["healthy", "warning", "unknown"] = "unknown"


class DashboardResponse(BaseModel):
    greeting_name: str
    homelab: DashboardCardResponse
    running: DashboardCardResponse
    gym: DashboardCardResponse
    system: DashboardCardResponse
    briefing_items: list[str]
    generated_at: str


class DockerContainerResponse(BaseModel):
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


class DockerStatusResponse(BaseModel):
    available: bool
    total: int
    running: int
    stopped: int
    unhealthy: int
    containers: list[DockerContainerResponse]
    error: str | None = None


class DockerLogsResponse(BaseModel):
    container_id: str
    tail: int
    logs: str
    generated_at: str


class DockerActionResponse(BaseModel):
    container_id: str
    action: Literal["start", "stop", "restart"]
    status: str
    generated_at: str


class HostMetricsResponse(BaseModel):
    available: bool
    hostname: str | None = None
    cpu_percent: float | None = None
    memory_percent: float | None = None
    memory_used_bytes: int | None = None
    memory_total_bytes: int | None = None
    disk_percent: float | None = None
    disk_used_bytes: int | None = None
    disk_total_bytes: int | None = None
    load_1m: float | None = None
    uptime_seconds: float | None = None
    network_receive_bytes_per_second: float | None = None
    network_transmit_bytes_per_second: float | None = None
    generated_at: str
    error: str | None = None


app = FastAPI(
    title="SirisOS API",
    description="Backend API for the SirisOS personal operating system.",
    version=API_VERSION,
)
app.include_router(running_router)
app.include_router(gym_router)
app.include_router(host_history_router)
app.include_router(homelab_alerts_router)
app.include_router(grafana_router)
app.include_router(engineering_standards_router)
app.include_router(sirishydro_router)

docker_monitor = DockerMonitor()
host_metrics_collector = HostMetricsCollector()
running_service = RunningService()
gym_service = GymService()
running_service.initialise()
gym_service.initialise()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


def _create_access_token(username: str) -> tuple[str, int]:
    expires_in = JWT_EXPIRY_HOURS * 3600
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        "iss": "sirisos-api",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM), expires_in


def _current_username(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            authorization.removeprefix("Bearer ").strip(),
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            issuer="sirisos-api",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    username = payload.get("sub")
    if not isinstance(username, str) or username != AUTH_USERNAME:
        raise HTTPException(status_code=401, detail="Invalid session user.")
    return username


CurrentUsername = Annotated[str, Depends(_current_username)]


@app.get("", include_in_schema=False)
@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"name": "SirisOS API", "version": API_VERSION, "docs": "/docs"}


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="sirisos-api", version=API_VERSION)


@app.post("/api/v1/auth/login", response_model=TokenResponse, tags=["authentication"])
async def login(credentials: LoginRequest) -> TokenResponse:
    if not secrets.compare_digest(
        credentials.username, AUTH_USERNAME
    ) or not secrets.compare_digest(credentials.password, AUTH_PASSWORD):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    token, expires_in = _create_access_token(AUTH_USERNAME)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        username=AUTH_USERNAME,
    )


@app.get("/api/v1/auth/me", response_model=CurrentUserResponse, tags=["authentication"])
async def current_user(username: CurrentUsername) -> CurrentUserResponse:
    return CurrentUserResponse(username=username)


@app.get("/api/v1/homelab/host", response_model=HostMetricsResponse, tags=["homelab"])
async def host_metrics(_: CurrentUsername) -> HostMetricsResponse:
    metrics = host_metrics_collector.collect()
    return HostMetricsResponse(
        available=metrics.available,
        hostname=metrics.hostname,
        cpu_percent=metrics.cpu_percent,
        memory_percent=metrics.memory_percent,
        memory_used_bytes=metrics.memory_used_bytes,
        memory_total_bytes=metrics.memory_total_bytes,
        disk_percent=metrics.disk_percent,
        disk_used_bytes=metrics.disk_used_bytes,
        disk_total_bytes=metrics.disk_total_bytes,
        load_1m=metrics.load_1m,
        uptime_seconds=metrics.uptime_seconds,
        network_receive_bytes_per_second=metrics.network_receive_bytes_per_second,
        network_transmit_bytes_per_second=metrics.network_transmit_bytes_per_second,
        generated_at=datetime.now().astimezone().isoformat(),
        error=metrics.error,
    )


@app.get("/api/v1/homelab/docker", response_model=DockerStatusResponse, tags=["homelab"])
async def docker_status(_: CurrentUsername) -> DockerStatusResponse:
    summary = docker_monitor.collect()
    return DockerStatusResponse(
        available=summary.available,
        total=summary.total,
        running=summary.running,
        stopped=summary.stopped,
        unhealthy=summary.unhealthy,
        containers=[
            DockerContainerResponse(
                container_id=item.container_id,
                name=item.name,
                image=item.image,
                state=item.state,
                status=item.status,
                health=item.health,
                cpu_percent=item.cpu_percent,
                memory_usage_bytes=item.memory_usage_bytes,
                memory_limit_bytes=item.memory_limit_bytes,
                memory_percent=item.memory_percent,
            )
            for item in summary.containers
        ],
        error=summary.error,
    )


@app.get(
    "/api/v1/homelab/docker/{container_id}/logs",
    response_model=DockerLogsResponse,
    tags=["homelab"],
)
async def docker_logs(
    container_id: str,
    _: CurrentUsername,
    tail: Annotated[int, Query(ge=20, le=1000)] = 300,
) -> DockerLogsResponse:
    try:
        logs = docker_monitor.logs(container_id, tail=tail)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502, detail=f"Docker logs unavailable: {exc}"
        ) from exc
    return DockerLogsResponse(
        container_id=container_id,
        tail=tail,
        logs=logs,
        generated_at=datetime.now().astimezone().isoformat(),
    )


@app.post(
    "/api/v1/homelab/docker/{container_id}/{action}",
    response_model=DockerActionResponse,
    tags=["homelab"],
)
async def docker_action(
    container_id: str,
    action: Literal["start", "stop", "restart"],
    _: CurrentUsername,
) -> DockerActionResponse:
    try:
        current_status = docker_monitor.action(container_id, action)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Docker action failed: {exc}") from exc
    return DockerActionResponse(
        container_id=container_id,
        action=action,
        status=current_status,
        generated_at=datetime.now().astimezone().isoformat(),
    )


def _homelab_card() -> tuple[DashboardCardResponse, str]:
    summary = docker_monitor.collect()
    if not summary.available:
        return (
            DashboardCardResponse(
                title="Homelab",
                value="Offline",
                subtitle="Docker monitoring unavailable",
                status="warning",
            ),
            "Docker monitoring is unavailable.",
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
            f"Homelab needs attention: {summary.unhealthy} unhealthy and {summary.stopped} stopped.",
        )
    return (
        DashboardCardResponse(
            title="Homelab",
            value=f"{summary.running}/{summary.total} running",
            subtitle="All Docker containers healthy",
            status="healthy",
        ),
        f"All {summary.total} Docker containers are running normally.",
    )


def _running_card() -> tuple[DashboardCardResponse, str]:
    runs = running_service.list_runs()
    if not runs:
        return (
            DashboardCardResponse(
                title="Running",
                value="No runs yet",
                subtitle="Log your first run",
                status="unknown",
            ),
            "No running activity has been logged yet.",
        )
    latest = runs[0]
    week_start = datetime.now().astimezone().date() - timedelta(days=6)
    weekly_runs = [run for run in runs if run.run_date >= week_start]
    weekly_distance = sum(run.distance_km for run in weekly_runs)
    return (
        DashboardCardResponse(
            title="Running",
            value=f"{latest.fitness_score:.1f} fitness",
            subtitle=f"{weekly_distance:.1f} km across {len(weekly_runs)} run{'s' if len(weekly_runs) != 1 else ''} this week",
            status="healthy",
        ),
        f"Running fitness is {latest.fitness_score:.1f}, with {weekly_distance:.1f} km logged in the last seven days.",
    )


def _gym_card() -> tuple[DashboardCardResponse, str]:
    workouts = gym_service.list_workouts()
    if not workouts:
        return (
            DashboardCardResponse(
                title="Gym",
                value="No workouts yet",
                subtitle="Log your first session",
                status="unknown",
            ),
            "No gym sessions have been logged yet.",
        )
    latest = workouts[0]
    week_start = datetime.now().astimezone().date() - timedelta(days=6)
    weekly = [workout for workout in workouts if workout.workout_date >= week_start]
    weekly_volume = sum(workout.total_volume_kg for workout in weekly)
    return (
        DashboardCardResponse(
            title="Gym",
            value=f"{len(weekly)} session{'s' if len(weekly) != 1 else ''}",
            subtitle=f"{weekly_volume:,.0f} kg volume this week",
            status="healthy",
        ),
        f"Gym training includes {len(weekly)} session{'s' if len(weekly) != 1 else ''} and {weekly_volume:,.0f} kg of volume in the last seven days.",
    )


def _system_card() -> tuple[DashboardCardResponse, str]:
    metrics = host_metrics_collector.collect()
    if not metrics.available:
        return (
            DashboardCardResponse(
                title="Server",
                value="Unavailable",
                subtitle="Host metrics could not be read",
                status="warning",
            ),
            "Host resource metrics are unavailable.",
        )
    cpu = metrics.cpu_percent
    memory = metrics.memory_percent
    status_value: Literal["healthy", "warning", "unknown"] = (
        "warning"
        if (cpu is not None and cpu >= 80) or (memory is not None and memory >= 80)
        else "healthy"
    )
    return (
        DashboardCardResponse(
            title="Server",
            value=f"{cpu:.0f}% CPU" if cpu is not None else "CPU warming up",
            subtitle=f"{memory:.0f}% memory" if memory is not None else "Memory unavailable",
            status=status_value,
        ),
        f"Server usage is {cpu:.0f}% CPU and {memory:.0f}% memory."
        if cpu is not None and memory is not None
        else "Server metrics are still warming up.",
    )


@app.get("/api/v1/dashboard", response_model=DashboardResponse, tags=["dashboard"])
async def dashboard(_: CurrentUsername) -> DashboardResponse:
    homelab, homelab_briefing = _homelab_card()
    running, running_briefing = _running_card()
    gym, gym_briefing = _gym_card()
    system, system_briefing = _system_card()
    return DashboardResponse(
        greeting_name="Brad",
        homelab=homelab,
        running=running,
        gym=gym,
        system=system,
        briefing_items=[
            homelab_briefing,
            running_briefing,
            gym_briefing,
            system_briefing,
        ],
        generated_at=datetime.now().astimezone().isoformat(),
    )
