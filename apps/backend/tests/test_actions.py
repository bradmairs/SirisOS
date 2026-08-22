import asyncio

import jwt

from app.api import actions
from app.main import AUTH_USERNAME, JWT_SECRET


def _token() -> str:
    return "Bearer " + jwt.encode(
        {"sub": AUTH_USERNAME, "iss": "sirisos-api"},
        JWT_SECRET,
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


class _FakeDockerMonitor:
    def __init__(self, *, raises: Exception | None = None, result: str = "running") -> None:
        self.raises = raises
        self.result = result
        self.calls: list[tuple[str, str]] = []

    def action(self, container_id: str, action: str) -> str:
        self.calls.append((container_id, action))
        if self.raises is not None:
            raise self.raises
        return self.result


def _current_username():
    from app.main import _current_username as impl

    return impl(authorization=_token())


def test_list_capabilities_requires_authentication() -> None:
    # list_capabilities/execute_capability delegate auth entirely to the
    # CurrentUsername FastAPI dependency (app.main._current_username), which
    # runs before the route body when called over HTTP. Calling the route
    # function directly bypasses that DI wiring, so the dependency itself is
    # what must be exercised here to prove auth is actually enforced.
    from app.main import _current_username

    try:
        _current_username(authorization=None)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 401
    else:
        raise AssertionError("Expected authentication failure")


def test_list_capabilities_returns_docker_actions() -> None:
    username = _current_username()
    results = asyncio.run(actions.list_capabilities(_=username))
    ids = {item.id for item in results}
    assert ids == {
        "docker.start",
        "docker.stop",
        "docker.restart",
        "home_assistant.control",
        "home_assistant.cover_control",
    }
    restart = next(item for item in results if item.id == "docker.restart")
    assert restart.requires_confirmation is True
    start = next(item for item in results if item.id == "docker.start")
    assert start.requires_confirmation is False
    cover = next(item for item in results if item.id == "home_assistant.cover_control")
    assert cover.requires_confirmation is True
    control = next(item for item in results if item.id == "home_assistant.control")
    assert control.requires_confirmation is False


def test_execute_low_risk_capability_without_confirmation(monkeypatch) -> None:
    fake = _FakeDockerMonitor(result="running")
    monkeypatch.setattr(actions, "docker_monitor", fake)
    username = _current_username()

    response = asyncio.run(
        actions.execute_capability(
            "docker.start",
            actions.ActionExecuteRequest(params={"container_id": "abc123"}, confirm=False),
            username,
        )
    )

    assert response.accepted is True
    assert response.result == "running"
    assert fake.calls == [("abc123", "start")]


def test_execute_confirmation_required_capability_without_confirm_is_rejected(monkeypatch) -> None:
    fake = _FakeDockerMonitor()
    monkeypatch.setattr(actions, "docker_monitor", fake)
    username = _current_username()

    try:
        asyncio.run(
            actions.execute_capability(
                "docker.restart",
                actions.ActionExecuteRequest(params={"container_id": "abc123"}, confirm=False),
                username,
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("Expected confirmation-required rejection")
    assert fake.calls == []


def test_execute_confirmation_required_capability_with_confirm_succeeds(monkeypatch) -> None:
    fake = _FakeDockerMonitor(result="running")
    monkeypatch.setattr(actions, "docker_monitor", fake)
    username = _current_username()

    response = asyncio.run(
        actions.execute_capability(
            "docker.restart",
            actions.ActionExecuteRequest(params={"container_id": "abc123"}, confirm=True),
            username,
        )
    )

    assert response.accepted is True
    assert fake.calls == [("abc123", "restart")]


def test_execute_unknown_capability_returns_404(monkeypatch) -> None:
    username = _current_username()
    try:
        asyncio.run(
            actions.execute_capability(
                "docker.does_not_exist",
                actions.ActionExecuteRequest(params={}, confirm=True),
                username,
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("Expected 404 for unknown capability")


def test_execute_protected_container_returns_403(monkeypatch) -> None:
    fake = _FakeDockerMonitor(raises=PermissionError("Core SirisOS containers cannot be controlled from the app."))
    monkeypatch.setattr(actions, "docker_monitor", fake)
    username = _current_username()

    try:
        asyncio.run(
            actions.execute_capability(
                "docker.restart",
                actions.ActionExecuteRequest(params={"container_id": "sirisos-api"}, confirm=True),
                username,
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
    else:
        raise AssertionError("Expected 403 for protected container")


def test_execute_missing_container_id_returns_400(monkeypatch) -> None:
    fake = _FakeDockerMonitor()
    monkeypatch.setattr(actions, "docker_monitor", fake)
    username = _current_username()

    try:
        asyncio.run(
            actions.execute_capability(
                "docker.start",
                actions.ActionExecuteRequest(params={}, confirm=False),
                username,
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("Expected 400 for missing container_id")
    assert fake.calls == []


def test_execute_home_assistant_control_without_confirmation(monkeypatch) -> None:
    fake = _FakeHomeAssistantService()
    monkeypatch.setattr(actions, "home_assistant_service", fake)
    username = _current_username()

    response = asyncio.run(
        actions.execute_capability(
            "home_assistant.control",
            actions.ActionExecuteRequest(
                params={"domain": "light", "service": "turn_on", "entity_id": "light.living_room"},
                confirm=False,
            ),
            username,
        )
    )

    assert response.accepted is True
    assert fake.calls == [("light", "turn_on", "light.living_room")]


def test_execute_home_assistant_control_rejects_cover_domain(monkeypatch) -> None:
    fake = _FakeHomeAssistantService()
    monkeypatch.setattr(actions, "home_assistant_service", fake)
    username = _current_username()

    try:
        asyncio.run(
            actions.execute_capability(
                "home_assistant.control",
                actions.ActionExecuteRequest(
                    params={"domain": "cover", "service": "open_cover", "entity_id": "cover.garage"},
                    confirm=False,
                ),
                username,
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("Expected cover domain to be rejected by home_assistant.control")
    assert fake.calls == []


def test_execute_home_assistant_cover_control_requires_confirmation(monkeypatch) -> None:
    fake = _FakeHomeAssistantService()
    monkeypatch.setattr(actions, "home_assistant_service", fake)
    username = _current_username()

    try:
        asyncio.run(
            actions.execute_capability(
                "home_assistant.cover_control",
                actions.ActionExecuteRequest(
                    params={"service": "open_cover", "entity_id": "cover.garage"},
                    confirm=False,
                ),
                username,
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("Expected confirmation-required rejection")
    assert fake.calls == []

    response = asyncio.run(
        actions.execute_capability(
            "home_assistant.cover_control",
            actions.ActionExecuteRequest(
                params={"service": "open_cover", "entity_id": "cover.garage"},
                confirm=True,
            ),
            username,
        )
    )
    assert response.accepted is True
    assert fake.calls == [("cover", "open_cover", "cover.garage")]


def test_execute_home_assistant_control_propagates_rejection_as_400(monkeypatch) -> None:
    fake = _FakeHomeAssistantService(raises=ValueError("Service light.explode is not permitted by SirisOS."))
    monkeypatch.setattr(actions, "home_assistant_service", fake)
    username = _current_username()

    try:
        asyncio.run(
            actions.execute_capability(
                "home_assistant.control",
                actions.ActionExecuteRequest(
                    params={"domain": "light", "service": "explode", "entity_id": "light.living_room"},
                    confirm=False,
                ),
                username,
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("Expected 400 for a rejected Home Assistant service")
