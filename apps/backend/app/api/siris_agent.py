from __future__ import annotations

import os
from typing import Annotated, Literal

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.services.siris_agent_service import SirisAgentService

router = APIRouter(prefix="/api/v1/siris/agent", tags=["siris-agent"])
AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")

agent_service = SirisAgentService()


def _authenticate(authorization: Annotated[str | None, Header()] = None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        payload = jwt.decode(
            authorization.removeprefix("Bearer ").strip(),
            JWT_SECRET,
            algorithms=["HS256"],
            issuer="sirisos-api",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session.") from exc
    if payload.get("sub") != AUTH_USERNAME:
        raise HTTPException(status_code=401, detail="Invalid session user.")


class AgentMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AgentAskRequest(BaseModel):
    messages: list[AgentMessage] = Field(min_length=1, max_length=40)


class AgentAskResponse(BaseModel):
    answer: str
    tools_used: list[str]
    available: bool


@router.post("/ask", response_model=AgentAskResponse)
async def ask_agent(
    payload: AgentAskRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> AgentAskResponse:
    _authenticate(authorization)
    result = await agent_service.ask([item.model_dump() for item in payload.messages])
    return AgentAskResponse(
        answer=result.answer,
        tools_used=result.tools_used,
        available=result.available,
    )
