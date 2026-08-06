from datetime import datetime, timedelta, timezone
import os
import secrets
from typing import Annotated, Literal

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.running import router as running_router
from app.services.docker_service import DockerMonitor

API_VERSION = "0.6.0"
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
    recovery: DashboardCardResponse
    gym: DashboardCardResponse
    today: DashboardCardResponse
    briefing: str
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


app = FastAPI(
    title="SirisOS API",
    description="Backend API for the SirisOS personal operating system.",
    version=API_VERSION,
)
app.include_router(running_router)

docker_monitor = DockerMonitor()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


def _create_access_token(username: str) -> tuple[str, int]:
    expires_in = JWT_EXPIRY_HOURS * 60 * 60
    now = datetime.now(timezone.utc)
    payload = {"sub": username, "iat": now, "exp": now + timedelta(seconds=expires_in), "iss": "sirisos-api"}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expires_in


def _current_username(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.", headers={"WWW-Authenticate": "Bearer"})
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], issuer="sirisos-api")
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.", headers={"WWW-Authenticate": "Bearer"}) from exc
    username = payload.get("sub")
    if not isinstance(username, str) or username != AUTH_USERNAME:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session user.", headers={"WWW-Authenticate": "Bearer"})
    return username


CurrentUsername = Annotated[str, Depends(_current_username)]


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"name": "SirisOS API", "version": API_VERSION, "docs": "/docs"}


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="sirisos-api", version=API_VERSION)


@app.post("/api/v1/auth/login", response_model=TokenResponse, tags=["authentication"])
async def login(credentials: LoginRequest) -> TokenResponse:
    if not secrets.compare_digest(credentials.username, AUTH_USERNAME) or not secrets.compare_digest(credentials.password, AUTH_PASSWORD):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password.")
    token, expires_in = _create_access_token(AUTH_USERNAME)
    return TokenResponse(access_token=token, expires_in=expires_in, username=AUTH_USERNAME)


@app.get("/api/v1/auth/me", response_model=CurrentUserResponse, tags=["authentication"])
async def current_user(username: CurrentUsername) -> CurrentUserResponse:
    return CurrentUserResponse(username=username)


@app.get("/api/v1/homelab/docker", response_model=DockerStatusResponse, tags=["homelab"])
async def docker_status(_: CurrentUsername) -> DockerStatusResponse:
    summary = docker_monitor.collect()
    return DockerStatusResponse(
        available=summary.available,
        total=summary.total,
        running=summary.running,
        stopped=summary.stopped,
        unhealthy=summary.unhealthy,
        containers=[DockerContainerResponse(
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
        ) for item in summary.containers],
        error=summary.error,
    )


def _homelab_card() -> tuple[DashboardCardResponse, str]:
    summary = docker_monitor.collect()
    if not summary.available:
        return DashboardCardResponse(title="Homelab", value="Offline", subtitle="Docker socket is unavailable", status="warning"), "Docker monitoring is unavailable. Check the Docker socket proxy."
    if summary.total == 0:
        return DashboardCardResponse(title="Homelab", value="No containers", subtitle="Docker is connected", status="unknown"), "Docker is connected, but no containers were found on this host."
    if summary.unhealthy > 0 or summary.stopped > 0:
        issues = summary.unhealthy + summary.stopped
        return DashboardCardResponse(title="Homelab", value=f"{summary.running}/{summary.total} running", subtitle=f"{issues} container issue{'s' if issues != 1 else ''}", status="warning"), f"Docker needs attention: {summary.running} of {summary.total} containers are running, with {summary.unhealthy} unhealthy and {summary.stopped} stopped."
    return DashboardCardResponse(title="Homelab", value=f"{summary.running}/{summary.total} running", subtitle="All Docker containers are healthy", status="healthy"), f"All {summary.total} Docker containers are running normally."


@app.get("/api/v1/dashboard", response_model=DashboardResponse, tags=["dashboard"])
async def dashboard(_: CurrentUsername) -> DashboardResponse:
    homelab, homelab_briefing = _homelab_card()
    return DashboardResponse(
        greeting_name="Brad",
        homelab=homelab,
        recovery=DashboardCardResponse(title="Recovery", value="Not connected", subtitle="Apple Health integration pending", status="unknown"),
        gym=DashboardCardResponse(title="Gym", value="No workout", subtitle="Gym programming module pending", status="unknown"),
        today=DashboardCardResponse(title="Today", value="No tasks", subtitle="Calendar and tasks are not connected yet", status="unknown"),
        briefing=f"{homelab_briefing} Health, gym, calendar, and AI integrations are still pending.",
        generated_at=datetime.now().astimezone().isoformat(),
    )
