import asyncio

import jwt

from app.api import incidents


def _token() -> str:
    return "Bearer " + jwt.encode(
        {"sub": incidents.AUTH_USERNAME, "iss": "sirisos-api"},
        incidents.JWT_SECRET,
        algorithm="HS256",
    )


def _patch_store(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(incidents, "INCIDENT_LIFECYCLE_PATH", tmp_path / "incident_lifecycle.json")


def test_list_requires_authentication() -> None:
    try:
        asyncio.run(incidents.list_incident_lifecycle(authorization=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 401
    else:
        raise AssertionError("Expected authentication failure")


def test_list_is_empty_when_nothing_has_ever_been_patched(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)
    results = asyncio.run(incidents.list_incident_lifecycle(authorization=_token()))
    assert results == []


def test_acknowledging_a_new_incident_creates_a_record(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)

    record = asyncio.run(
        incidents.update_incident_lifecycle(
            "incident.power",
            incidents.IncidentLifecycleUpdate(status="acknowledged", assigned_to="Brad"),
            authorization=_token(),
        )
    )

    assert record.id == "incident.power"
    assert record.status == "acknowledged"
    assert record.assigned_to == "Brad"
    assert record.acknowledged_at is not None
    assert record.resolved_at is None
    assert record.created_at == record.updated_at

    listed = asyncio.run(incidents.list_incident_lifecycle(authorization=_token()))
    assert len(listed) == 1
    assert listed[0].id == "incident.power"


def test_resolving_backfills_acknowledged_at_when_it_was_skipped(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)

    record = asyncio.run(
        incidents.update_incident_lifecycle(
            "incident.compute",
            incidents.IncidentLifecycleUpdate(status="resolved", notes="Restarted the container."),
            authorization=_token(),
        )
    )

    assert record.status == "resolved"
    assert record.acknowledged_at is not None
    assert record.resolved_at is not None
    assert record.notes == "Restarted the container."


def test_acknowledged_at_is_not_overwritten_on_a_later_resolve(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)

    first = asyncio.run(
        incidents.update_incident_lifecycle(
            "incident.network",
            incidents.IncidentLifecycleUpdate(status="acknowledged"),
            authorization=_token(),
        )
    )
    second = asyncio.run(
        incidents.update_incident_lifecycle(
            "incident.network",
            incidents.IncidentLifecycleUpdate(status="resolved"),
            authorization=_token(),
        )
    )

    assert second.acknowledged_at == first.acknowledged_at
    assert second.resolved_at is not None
    assert second.created_at == first.created_at


def test_reopening_clears_acknowledged_and_resolved_timestamps(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)

    asyncio.run(
        incidents.update_incident_lifecycle(
            "incident.storage",
            incidents.IncidentLifecycleUpdate(status="resolved"),
            authorization=_token(),
        )
    )
    reopened = asyncio.run(
        incidents.update_incident_lifecycle(
            "incident.storage",
            incidents.IncidentLifecycleUpdate(status="open"),
            authorization=_token(),
        )
    )

    assert reopened.status == "open"
    assert reopened.acknowledged_at is None
    assert reopened.resolved_at is None


def test_resolved_records_stay_listed_as_history(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)

    asyncio.run(
        incidents.update_incident_lifecycle(
            "incident.observability",
            incidents.IncidentLifecycleUpdate(status="resolved"),
            authorization=_token(),
        )
    )

    listed = asyncio.run(incidents.list_incident_lifecycle(authorization=_token()))
    assert len(listed) == 1
    assert listed[0].status == "resolved"


def test_updating_a_second_distinct_incident_does_not_disturb_the_first(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)

    asyncio.run(
        incidents.update_incident_lifecycle(
            "incident.power",
            incidents.IncidentLifecycleUpdate(status="acknowledged"),
            authorization=_token(),
        )
    )
    asyncio.run(
        incidents.update_incident_lifecycle(
            "incident.compute",
            incidents.IncidentLifecycleUpdate(status="resolved"),
            authorization=_token(),
        )
    )

    listed = asyncio.run(incidents.list_incident_lifecycle(authorization=_token()))
    by_id = {item.id: item for item in listed}
    assert len(listed) == 2
    assert by_id["incident.power"].status == "acknowledged"
    assert by_id["incident.compute"].status == "resolved"
