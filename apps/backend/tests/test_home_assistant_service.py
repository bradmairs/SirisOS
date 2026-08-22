import asyncio

import httpx
import pytest

from app.services import home_assistant_service as home_assistant_service_module
from app.services.home_assistant_service import HomeAssistantService


def _configured_service() -> HomeAssistantService:
    service = HomeAssistantService()
    service._base_url = "http://homeassistant.local:8123"
    service._token = "test-token"
    return service


def _recorder(service: HomeAssistantService) -> list[dict]:
    recorded: list[dict] = []
    service._activity.record = lambda **kwargs: recorded.append(kwargs)
    return recorded


class _FakeResponse:
    def __init__(self, *, raises: bool = False) -> None:
        self.raises = raises

    def raise_for_status(self) -> None:
        if self.raises:
            raise httpx.HTTPStatusError("boom", request=None, response=None)


class _FakeAsyncClient:
    def __init__(self, *, raises: bool = False) -> None:
        self.raises = raises

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def post(self, *args, **kwargs) -> _FakeResponse:
        return _FakeResponse(raises=self.raises)


def test_call_service_records_success(monkeypatch) -> None:
    service = _configured_service()
    recorded = _recorder(service)
    monkeypatch.setattr(
        home_assistant_service_module.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient()
    )

    asyncio.run(service.call_service("light", "turn_on", "light.living_room"))

    assert len(recorded) == 1
    assert recorded[0]["severity"] == "info"
    assert recorded[0]["event_type"] == "home_assistant_action"
    assert "light.living_room" in recorded[0]["message"]


def test_call_service_records_rejection_for_disallowed_service(monkeypatch) -> None:
    service = _configured_service()
    recorded = _recorder(service)

    with pytest.raises(ValueError):
        asyncio.run(service.call_service("light", "explode", "light.living_room"))

    assert len(recorded) == 1
    assert recorded[0]["severity"] == "warning"


def test_call_service_records_rejection_for_entity_domain_mismatch(monkeypatch) -> None:
    service = _configured_service()
    recorded = _recorder(service)

    with pytest.raises(ValueError):
        asyncio.run(service.call_service("light", "turn_on", "switch.living_room"))

    assert len(recorded) == 1
    assert recorded[0]["severity"] == "warning"


def test_call_service_records_failure_on_unreachable_home_assistant(monkeypatch) -> None:
    service = _configured_service()
    recorded = _recorder(service)
    monkeypatch.setattr(
        home_assistant_service_module.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(raises=True),
    )

    with pytest.raises(RuntimeError):
        asyncio.run(service.call_service("light", "turn_on", "light.living_room"))

    assert len(recorded) == 1
    assert recorded[0]["severity"] == "critical"


def test_call_service_records_failure_when_not_configured() -> None:
    service = HomeAssistantService()
    recorded = _recorder(service)

    with pytest.raises(RuntimeError):
        asyncio.run(service.call_service("light", "turn_on", "light.living_room"))

    assert len(recorded) == 1
    assert recorded[0]["severity"] == "critical"
