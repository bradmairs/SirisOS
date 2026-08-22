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


def test_home_assistant_action_succeeds_and_calls_the_service(monkeypatch) -> None:
    fake = _FakeHomeAssistantService()
    monkeypatch.setattr(homelab_alerts, "home_assistant_service", fake)

    response = asyncio.run(
        homelab_alerts.home_assistant_action(
            homelab_alerts.HomeAssistantActionRequest(
                domain="light", service="turn_on", entity_id="light.living_room"
            ),
            authorization=_token(),
        )
    )

    assert response.accepted is True
    assert fake.calls == [("light", "turn_on", "light.living_room")]


def test_home_assistant_action_propagates_failure_as_502(monkeypatch) -> None:
    monkeypatch.setattr(
        homelab_alerts,
        "home_assistant_service",
        _FakeHomeAssistantService(raises=RuntimeError("Home Assistant unreachable")),
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


def test_home_assistant_action_propagates_rejection_as_400(monkeypatch) -> None:
    monkeypatch.setattr(
        homelab_alerts,
        "home_assistant_service",
        _FakeHomeAssistantService(raises=ValueError("Service light.explode is not permitted by SirisOS.")),
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
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("Expected the rejection to propagate")
