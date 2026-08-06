from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


app = FastAPI(
    title="SirisOS API",
    description="Backend API for the SirisOS personal operating system.",
    version="0.1.0",
)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {
        "name": "SirisOS API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="sirisos-api", version="0.1.0")
