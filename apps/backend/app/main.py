"""SirisOS API core: health, sign-in and the CORS policy. Feature routers
(the hub and the engineering module) are registered in app.entrypoint."""

from datetime import datetime, timedelta, timezone
import os
import secrets
from typing import Literal

import jwt
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.auth import JWT_ALGORITHM, CurrentUser
from app.service_key import ServiceKeyMiddleware

API_VERSION = "1.0.0"
AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
AUTH_PASSWORD = os.getenv("SIRISOS_ADMIN_PASSWORD", "change-me")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
JWT_EXPIRY_HOURS = int(os.getenv("SIRISOS_JWT_EXPIRY_HOURS", "24"))


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


app = FastAPI(
    title="SirisOS API",
    description="The hub for the Siris apps, plus the SirisOS engineering module (ADR 106).",
    version=API_VERSION,
)

# SirisAI's service key opens a few read/compute routes (ADR 110).
app.add_middleware(ServiceKeyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
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


@app.get("", include_in_schema=False)
@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"name": "SirisOS API", "version": API_VERSION, "docs": "/docs"}


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="sirisos-api", version=API_VERSION)


@app.post("/api/v1/auth/login", response_model=TokenResponse, tags=["authentication"])
async def login(credentials: LoginRequest) -> TokenResponse:
    if not secrets.compare_digest(credentials.username, AUTH_USERNAME) or not secrets.compare_digest(
        credentials.password, AUTH_PASSWORD
    ):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    token, expires_in = _create_access_token(AUTH_USERNAME)
    return TokenResponse(access_token=token, expires_in=expires_in, username=AUTH_USERNAME)


@app.get("/api/v1/auth/me", response_model=CurrentUserResponse, tags=["authentication"])
async def current_user(username: CurrentUser) -> CurrentUserResponse:
    return CurrentUserResponse(username=username)
