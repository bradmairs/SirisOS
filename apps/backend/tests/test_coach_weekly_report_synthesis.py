import asyncio
from pathlib import Path

import jwt
import pytest
from fastapi import HTTPException

from app.api import coach as coach_api
from app.services.coach_service import CoachService
from app.services.gym_service import GymService
from app.services.running_service import RunningService

# Matches the tmp_path/monkeypatch + direct-endpoint-call pattern
# test_health_ingest.py already established for testing a route function
# without spinning up a full TestClient.


def _service(tmp_path: Path, monkeypatch) -> CoachService:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/coach_synthesis.db")
    running = RunningService()
    running.initialise()
    gym = GymService()
    gym.initialise()
    return CoachService(running_service=running, gym_service=gym)


def _admin_token() -> str:
    return "Bearer " + jwt.encode(
        {"sub": coach_api.AUTH_USERNAME, "iss": "sirisos-api"},
        coach_api.JWT_SECRET,
        algorithm="HS256",
    )


class _FakeChatClient:
    def __init__(self, reply: str | None) -> None:
        self._reply = reply

    async def complete(self, *, system: str, prompt: str) -> str | None:
        return self._reply


def test_weekly_report_falls_back_to_deterministic_headline_when_ollama_unconfigured(
    tmp_path: Path, monkeypatch
) -> None:
    # No OLLAMA_URL/model configured in the test environment -- chat_client
    # stays disabled and returns None immediately, no network call attempted.
    monkeypatch.setattr(coach_api, "service", _service(tmp_path, monkeypatch))

    response = asyncio.run(coach_api.weekly_report(_admin_token()))

    assert response.synthesized_headline is None
    assert response.headline


def test_weekly_report_uses_synthesized_headline_when_ollama_available(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(coach_api, "service", _service(tmp_path, monkeypatch))
    monkeypatch.setattr(coach_api, "chat_client", _FakeChatClient("You're on a roll this week!"))

    response = asyncio.run(coach_api.weekly_report(_admin_token()))

    assert response.synthesized_headline == "You're on a roll this week!"
    assert response.headline  # deterministic headline stays present, not replaced


def test_weekly_report_falls_back_when_ollama_returns_nothing_usable(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(coach_api, "service", _service(tmp_path, monkeypatch))
    monkeypatch.setattr(coach_api, "chat_client", _FakeChatClient(None))

    response = asyncio.run(coach_api.weekly_report(_admin_token()))

    assert response.synthesized_headline is None


def test_weekly_report_requires_authentication(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(coach_api, "service", _service(tmp_path, monkeypatch))

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(coach_api.weekly_report(None))
    assert excinfo.value.status_code == 401
