import asyncio
from dataclasses import dataclass, field

import jwt

from app.api import homelab_alerts, recommendations


def _token() -> str:
    return "Bearer " + jwt.encode(
        {"sub": recommendations.AUTH_USERNAME, "iss": "sirisos-api"},
        recommendations.JWT_SECRET,
        algorithm="HS256",
    )


@dataclass(frozen=True)
class _FakeHostMetrics:
    available: bool = False
    cpu_percent: float | None = None
    memory_percent: float | None = None
    disk_percent: float | None = None


@dataclass(frozen=True)
class _FakeDockerContainer:
    container_id: str
    name: str
    image: str
    state: str
    health: str | None
    update_available: bool = False


@dataclass(frozen=True)
class _FakeDockerSummary:
    available: bool = True
    error: str | None = None
    containers: list = field(default_factory=list)


class _FakeCollector:
    def collect(self) -> _FakeHostMetrics:
        return _FakeHostMetrics()


class _FakeDockerMonitor:
    def __init__(self, containers: list | None = None) -> None:
        self._containers = containers or []

    def collect(self) -> _FakeDockerSummary:
        return _FakeDockerSummary(containers=self._containers)


class _FakeChatClient:
    def __init__(self, reply: str | None) -> None:
        self._reply = reply
        self.calls: list[str] = []

    async def complete(self, *, system: str, prompt: str) -> str | None:
        self.calls.append(prompt)
        return self._reply


def _patch_alert_sources(monkeypatch, tmp_path, *, containers: list | None = None) -> None:
    monkeypatch.setattr(homelab_alerts, "collector", _FakeCollector())
    monkeypatch.setattr(homelab_alerts, "docker_monitor", _FakeDockerMonitor(containers))
    monkeypatch.setattr(recommendations, "RECOMMENDATIONS_PATH", tmp_path / "recommendations.json")


def _unhealthy_container(container_id: str = "abc123") -> list[_FakeDockerContainer]:
    return [_FakeDockerContainer(container_id=container_id, name="plex", image="plexinc/pms", state="running", health="unhealthy")]


def test_new_recommendation_gets_a_synthesized_rationale(monkeypatch, tmp_path) -> None:
    _patch_alert_sources(monkeypatch, tmp_path, containers=_unhealthy_container())
    fake = _FakeChatClient("Plex looks unhealthy -- worth checking its logs and restarting it.")
    monkeypatch.setattr(recommendations, "chat_client", fake)

    results = asyncio.run(recommendations.list_recommendations(status=None, authorization=_token()))

    assert len(results) == 1
    assert results[0].synthesized_rationale == "Plex looks unhealthy -- worth checking its logs and restarting it."
    assert results[0].rationale  # deterministic rationale stays present, not replaced
    assert len(fake.calls) == 1


def test_falls_back_to_none_when_ollama_unconfigured(monkeypatch, tmp_path) -> None:
    # No monkeypatch of chat_client -- the real module-level singleton stays
    # disabled in this test environment (no OLLAMA_URL configured), same as
    # the Coach weekly report equivalent test.
    _patch_alert_sources(monkeypatch, tmp_path, containers=_unhealthy_container())

    results = asyncio.run(recommendations.list_recommendations(status=None, authorization=_token()))

    assert len(results) == 1
    assert results[0].synthesized_rationale is None


def test_falls_back_to_none_when_ollama_returns_nothing_usable(monkeypatch, tmp_path) -> None:
    _patch_alert_sources(monkeypatch, tmp_path, containers=_unhealthy_container())
    monkeypatch.setattr(recommendations, "chat_client", _FakeChatClient(None))

    results = asyncio.run(recommendations.list_recommendations(status=None, authorization=_token()))

    assert results[0].synthesized_rationale is None


def test_synthesis_is_not_repeated_on_later_polls_for_the_same_recommendation(monkeypatch, tmp_path) -> None:
    _patch_alert_sources(monkeypatch, tmp_path, containers=_unhealthy_container())
    fake = _FakeChatClient("Plex looks unhealthy.")
    monkeypatch.setattr(recommendations, "chat_client", fake)

    first = asyncio.run(recommendations.list_recommendations(status=None, authorization=_token()))
    second = asyncio.run(recommendations.list_recommendations(status=None, authorization=_token()))

    assert first[0].synthesized_rationale == "Plex looks unhealthy."
    assert second[0].synthesized_rationale == "Plex looks unhealthy."
    assert len(fake.calls) == 1  # only called once, at first-detection time


def test_synthesized_rationale_survives_a_dismiss(monkeypatch, tmp_path) -> None:
    _patch_alert_sources(monkeypatch, tmp_path, containers=_unhealthy_container())
    monkeypatch.setattr(recommendations, "chat_client", _FakeChatClient("Plex looks unhealthy."))

    first = asyncio.run(recommendations.list_recommendations(status=None, authorization=_token()))
    asyncio.run(
        recommendations.update_recommendation_status(
            first[0].id,
            recommendations.RecommendationStatusUpdate(status="dismissed"),
            authorization=_token(),
        )
    )

    second = asyncio.run(recommendations.list_recommendations(status=None, authorization=_token()))
    assert second[0].synthesized_rationale == "Plex looks unhealthy."
