import asyncio

import jwt

from app.api import digital_twin


def _token() -> str:
    return "Bearer " + jwt.encode(
        {"sub": digital_twin.AUTH_USERNAME, "iss": "sirisos-api"},
        digital_twin.JWT_SECRET,
        algorithm="HS256",
    )


def _patch_store(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(digital_twin, "DIGITAL_TWIN_EDGES_PATH", tmp_path / "digital_twin_edges.json")


def test_topology_requires_authentication() -> None:
    try:
        asyncio.run(digital_twin.get_topology(authorization=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 401
    else:
        raise AssertionError("Expected authentication failure")


def test_topology_starts_with_only_built_in_edges(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)
    topology = asyncio.run(digital_twin.get_topology(authorization=_token()))
    assert len(topology["built_in_edges"]) == 2
    assert topology["custom_edges"] == []


def test_adding_a_valid_edge_persists_it(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)

    edge = asyncio.run(
        digital_twin.add_edge(
            digital_twin.DependencyEdgeCreate(dependent_id="unifi", dependency_id="ups"),
            authorization=_token(),
        )
    )

    assert edge.dependent_id == "unifi"
    assert edge.dependency_id == "ups"
    assert "unifi" in edge.reason

    topology = asyncio.run(digital_twin.get_topology(authorization=_token()))
    assert len(topology["custom_edges"]) == 1


def test_self_dependency_is_rejected(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)
    try:
        asyncio.run(
            digital_twin.add_edge(
                digital_twin.DependencyEdgeCreate(dependent_id="ups", dependency_id="ups"),
                authorization=_token(),
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("Expected a self-dependency rejection")


def test_unknown_node_is_rejected(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)
    try:
        asyncio.run(
            digital_twin.add_edge(
                digital_twin.DependencyEdgeCreate(dependent_id="ups", dependency_id="not-a-real-node"),
                authorization=_token(),
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("Expected an unknown-node rejection")


def test_duplicate_edge_is_idempotent_not_an_error(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)
    first = asyncio.run(
        digital_twin.add_edge(
            digital_twin.DependencyEdgeCreate(dependent_id="grafana", dependency_id="prometheus"),
            authorization=_token(),
        )
    )
    second = asyncio.run(
        digital_twin.add_edge(
            digital_twin.DependencyEdgeCreate(dependent_id="grafana", dependency_id="prometheus"),
            authorization=_token(),
        )
    )
    assert first.key == second.key

    topology = asyncio.run(digital_twin.get_topology(authorization=_token()))
    assert len(topology["custom_edges"]) == 1


def test_duplicate_of_a_built_in_edge_is_idempotent(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)
    edge = asyncio.run(
        digital_twin.add_edge(
            digital_twin.DependencyEdgeCreate(dependent_id="hyper_backup", dependency_id="synology"),
            authorization=_token(),
        )
    )
    assert edge.reason == digital_twin._BUILT_IN_EDGES[0]["reason"]

    topology = asyncio.run(digital_twin.get_topology(authorization=_token()))
    assert topology["custom_edges"] == []


def test_a_cycle_is_rejected(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)
    # synology -> hyper_backup would close a cycle with the built-in
    # hyper_backup -> synology edge.
    try:
        asyncio.run(
            digital_twin.add_edge(
                digital_twin.DependencyEdgeCreate(dependent_id="synology", dependency_id="hyper_backup"),
                authorization=_token(),
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("Expected a cycle rejection")


def test_removing_an_edge_removes_it_from_topology(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)
    edge = asyncio.run(
        digital_twin.add_edge(
            digital_twin.DependencyEdgeCreate(dependent_id="grafana", dependency_id="prometheus"),
            authorization=_token(),
        )
    )

    result = asyncio.run(digital_twin.remove_edge(edge.key, authorization=_token()))
    assert result == {"removed": True}

    topology = asyncio.run(digital_twin.get_topology(authorization=_token()))
    assert topology["custom_edges"] == []


def test_removing_a_nonexistent_edge_reports_not_removed(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)
    result = asyncio.run(digital_twin.remove_edge("nope>nope", authorization=_token()))
    assert result == {"removed": False}


def test_reset_edges_clears_all_custom_edges(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)
    asyncio.run(
        digital_twin.add_edge(
            digital_twin.DependencyEdgeCreate(dependent_id="grafana", dependency_id="prometheus"),
            authorization=_token(),
        )
    )
    asyncio.run(
        digital_twin.add_edge(
            digital_twin.DependencyEdgeCreate(dependent_id="unifi", dependency_id="ups"),
            authorization=_token(),
        )
    )

    result = asyncio.run(digital_twin.reset_edges(authorization=_token()))
    assert result == {"removed": True}

    topology = asyncio.run(digital_twin.get_topology(authorization=_token()))
    assert topology["custom_edges"] == []
