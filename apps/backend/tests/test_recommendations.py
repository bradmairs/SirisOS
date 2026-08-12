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


def _patch_alert_sources(monkeypatch, tmp_path, *, containers: list | None = None) -> None:
    monkeypatch.setattr(homelab_alerts, "collector", _FakeCollector())
    monkeypatch.setattr(homelab_alerts, "docker_monitor", _FakeDockerMonitor(containers))
    monkeypatch.setattr(recommendations, "RECOMMENDATIONS_PATH", tmp_path / "recommendations.json")


def test_list_recommendations_requires_authentication() -> None:
    try:
        asyncio.run(recommendations.list_recommendations(status=None, authorization=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 401
    else:
        raise AssertionError("Expected authentication failure")


def test_unhealthy_container_produces_a_pending_recommendation(monkeypatch, tmp_path) -> None:
    _patch_alert_sources(
        monkeypatch,
        tmp_path,
        containers=[
            _FakeDockerContainer(
                container_id="abc123", name="plex", image="plexinc/pms", state="running", health="unhealthy"
            )
        ],
    )

    results = asyncio.run(recommendations.list_recommendations(status=None, authorization=_token()))

    assert len(results) == 1
    item = results[0]
    assert item.id == "rec-container-abc123-unhealthy"
    assert item.severity == "critical"
    assert item.status == "pending"
    assert item.evidence_source == "homelab_alerts"
    assert "restart" in item.suggested_action.lower()
    assert item.capability_id == "docker.restart"
    assert item.capability_params == {"container_id": "abc123"}


def test_stopped_container_binds_to_docker_start(monkeypatch, tmp_path) -> None:
    _patch_alert_sources(
        monkeypatch,
        tmp_path,
        containers=[
            _FakeDockerContainer(
                container_id="xyz789", name="plex", image="plexinc/pms", state="stopped", health=None
            )
        ],
    )

    results = asyncio.run(recommendations.list_recommendations(status=None, authorization=_token()))

    assert len(results) == 1
    assert results[0].capability_id == "docker.start"
    assert results[0].capability_params == {"container_id": "xyz789"}


class _FakeUnavailableDockerMonitor:
    def collect(self) -> _FakeDockerSummary:
        return _FakeDockerSummary(available=False, error="Docker socket unreachable.")


def test_docker_unavailable_has_no_capability_binding(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(homelab_alerts, "collector", _FakeCollector())
    monkeypatch.setattr(homelab_alerts, "docker_monitor", _FakeUnavailableDockerMonitor())
    monkeypatch.setattr(recommendations, "RECOMMENDATIONS_PATH", tmp_path / "recommendations.json")

    results = asyncio.run(recommendations.list_recommendations(status=None, authorization=_token()))

    assert len(results) == 1
    assert results[0].evidence_id == "docker-unavailable"
    assert results[0].capability_id is None
    assert results[0].capability_params is None


def test_dismiss_status_persists_across_recompute(monkeypatch, tmp_path) -> None:
    _patch_alert_sources(
        monkeypatch,
        tmp_path,
        containers=[
            _FakeDockerContainer(
                container_id="abc123", name="plex", image="plexinc/pms", state="stopped", health=None
            )
        ],
    )

    first = asyncio.run(recommendations.list_recommendations(status=None, authorization=_token()))
    recommendation_id = first[0].id

    updated = asyncio.run(
        recommendations.update_recommendation_status(
            recommendation_id,
            recommendations.RecommendationStatusUpdate(status="dismissed"),
            authorization=_token(),
        )
    )
    assert updated.status == "dismissed"

    second = asyncio.run(recommendations.list_recommendations(status=None, authorization=_token()))
    assert second[0].status == "dismissed"

    pending_only = asyncio.run(recommendations.list_recommendations(status="pending", authorization=_token()))
    assert pending_only == []


def test_resolved_alert_removes_its_recommendation(monkeypatch, tmp_path) -> None:
    _patch_alert_sources(
        monkeypatch,
        tmp_path,
        containers=[
            _FakeDockerContainer(
                container_id="abc123", name="plex", image="plexinc/pms", state="stopped", health=None
            )
        ],
    )
    first = asyncio.run(recommendations.list_recommendations(status=None, authorization=_token()))
    assert len(first) == 1

    _patch_alert_sources(monkeypatch, tmp_path, containers=[])
    second = asyncio.run(recommendations.list_recommendations(status=None, authorization=_token()))
    assert second == []


def test_update_status_for_missing_recommendation_returns_404(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(recommendations, "RECOMMENDATIONS_PATH", tmp_path / "recommendations.json")
    try:
        asyncio.run(
            recommendations.update_recommendation_status(
                "rec-does-not-exist",
                recommendations.RecommendationStatusUpdate(status="acted"),
                authorization=_token(),
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("Expected 404 for missing recommendation")


def test_recommendation_created_only_once_across_repeated_polls(monkeypatch, tmp_path) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(
        recommendations.activity_service,
        "record",
        lambda **kwargs: calls.append(kwargs),
    )
    _patch_alert_sources(
        monkeypatch,
        tmp_path,
        containers=[
            _FakeDockerContainer(
                container_id="abc123", name="plex", image="plexinc/pms", state="stopped", health=None
            )
        ],
    )

    asyncio.run(recommendations.list_recommendations(status=None, authorization=_token()))
    asyncio.run(recommendations.list_recommendations(status=None, authorization=_token()))

    assert len(calls) == 1
