import asyncio

import jwt

from app.api import homelab_alerts


def _token() -> str:
    return "Bearer " + jwt.encode(
        {"sub": homelab_alerts.AUTH_USERNAME, "iss": "sirisos-api"},
        homelab_alerts.JWT_SECRET,
        algorithm="HS256",
    )


class _FakeHomeAssistantService:
    def __init__(self, *, raises: Exception | None = None) -> None:
        self.raises = raises
        self.calls: list[tuple[str, str, str]] = []

    async def call_service(self, domain: str, service: str, entity_id: str) -> None:
        self.calls.append((domain, service, entity_id))
        if self.raises is not None:
            raise self.raises


def test_home_assistant_action_records_an_activity_event_on_success(monkeypatch) -> None:
    monkeypatch.setattr(homelab_alerts, "home_assistant_service", _FakeHomeAssistantService())
    recorded: list[dict] = []
    monkeypatch.setattr(
        homelab_alerts.activity_service,
        "record",
        lambda **kwargs: recorded.append(kwargs),
    )

    response = asyncio.run(
        homelab_alerts.home_assistant_action(
            homelab_alerts.HomeAssistantActionRequest(
                domain="light", service="turn_on", entity_id="light.living_room"
            ),
            authorization=_token(),
        )
    )

    assert response.accepted is True
    assert len(recorded) == 1
    assert recorded[0]["severity"] == "info"
    assert "light.living_room" in recorded[0]["message"]


def test_home_assistant_action_records_an_activity_event_on_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        homelab_alerts,
        "home_assistant_service",
        _FakeHomeAssistantService(raises=RuntimeError("Home Assistant unreachable")),
    )
    recorded: list[dict] = []
    monkeypatch.setattr(
        homelab_alerts.activity_service,
        "record",
        lambda **kwargs: recorded.append(kwargs),
    )

    try:
        asyncio.run(
            homelab_alerts.home_assistant_action(
                homelab_alerts.HomeAssistantActionRequest(
                    domain="light", service="turn_on", entity_id="light.living_room"
                ),
                authorization=_token(),
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 502
    else:
        raise AssertionError("Expected the Home Assistant failure to propagate")

    assert len(recorded) == 1
    assert recorded[0]["severity"] == "critical"
