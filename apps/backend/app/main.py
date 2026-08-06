from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


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
    generated_at: str = Field(
        description="ISO-8601 timestamp. Static placeholder until live integrations are added."
    )


app = FastAPI(
    title="SirisOS API",
    description="Backend API for the SirisOS personal operating system.",
    version="0.2.0",
)

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
        "version": "0.2.0",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="sirisos-api", version="0.2.0")


@app.get("/api/v1/dashboard", response_model=DashboardResponse, tags=["dashboard"])
async def dashboard() -> DashboardResponse:
    """Return the combined data needed by the SirisOS home dashboard.

    Values are deliberately centralised in the backend so integrations can replace
    each placeholder independently without changing the Flutter UI contract.
    """
    return DashboardResponse(
        greeting_name="Brad",
        homelab=DashboardCardResponse(
            title="Homelab",
            value="Healthy",
            subtitle="SirisOS API is online",
            status="healthy",
        ),
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
            "The SirisOS app is connected to its backend. Homelab, health, gym, "
            "calendar, and AI integrations can now be added behind this API."
        ),
        generated_at="2026-08-06T10:17:00+10:00",
    )
