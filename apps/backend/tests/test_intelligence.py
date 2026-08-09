import asyncio

import jwt

from app.api import intelligence
from app.services.ollama_service import OllamaStatus


def _token() -> str:
    return "Bearer " + jwt.encode(
        {"sub": intelligence.AUTH_USERNAME, "iss": "sirisos-api"},
        intelligence.JWT_SECRET,
        algorithm="HS256",
    )


def test_ollama_status_requires_authentication() -> None:
    try:
        asyncio.run(intelligence.ollama_status(None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 401
    else:
        raise AssertionError("Expected authentication failure")


def test_ollama_status_reflects_connector_state(monkeypatch) -> None:
    async def fake_status() -> OllamaStatus:
        return OllamaStatus(configured=True, reachable=True, model="llama3.1", model_available=True)

    monkeypatch.setattr(intelligence.chat_client, "status", fake_status)

    response = asyncio.run(intelligence.ollama_status(_token()))

    assert response.configured is True
    assert response.reachable is True
    assert response.model == "llama3.1"
    assert response.model_available is True


def test_ollama_status_reports_not_configured(monkeypatch) -> None:
    async def fake_status() -> OllamaStatus:
        return OllamaStatus(configured=False, reachable=False, model=None, model_available=False)

    monkeypatch.setattr(intelligence.chat_client, "status", fake_status)

    response = asyncio.run(intelligence.ollama_status(_token()))

    assert response.configured is False
    assert response.model is None
