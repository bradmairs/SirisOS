import json
import os
import tempfile
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

# Mirrors apps/mobile's DependencyGraph exactly -- same node/built-in-edge
# catalog, same self/duplicate/cycle validation rules -- so both sides agree
# on what's valid without one silently trusting the other. "Arbitrary custom
# nodes" (letting a user declare a node this catalog doesn't know about) is
# a separate, not-yet-built roadmap item; this module's node catalog stays
# fixed on purpose until that's designed.
router = APIRouter(prefix="/api/v1/digital-twin", tags=["digital-twin"])

AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
DIGITAL_TWIN_EDGES_PATH = Path(os.getenv("SIRISOS_DIGITAL_TWIN_EDGES_PATH", "/app/data/digital_twin_edges.json"))
MAX_CUSTOM_EDGES = 200

_NODE_IDS = {
    "ups",
    "docker",
    "synology",
    "hyper_backup",
    "backup_analytics",
    "home_assistant",
    "unifi",
    "prometheus",
    "grafana",
}

_BUILT_IN_EDGES: list[dict[str, str]] = [
    {
        "dependent_id": "hyper_backup",
        "dependency_id": "synology",
        "reason": "Hyper Backup runs on Synology DSM and cannot operate when the NAS is unavailable.",
    },
    {
        "dependent_id": "backup_analytics",
        "dependency_id": "hyper_backup",
        "reason": "Backup Protection Analytics requires observed Hyper Backup completion data.",
    },
]


class DependencyEdge(BaseModel):
    dependent_id: str
    dependency_id: str
    reason: str

    @property
    def key(self) -> str:
        return f"{self.dependent_id}>{self.dependency_id}"


class DependencyEdgeCreate(BaseModel):
    dependent_id: str
    dependency_id: str
    reason: str | None = None


def _authenticate(authorization: Annotated[str | None, Header()] = None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        payload = jwt.decode(
            authorization.removeprefix("Bearer ").strip(),
            JWT_SECRET,
            algorithms=["HS256"],
            issuer="sirisos-api",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session.") from exc
    if payload.get("sub") != AUTH_USERNAME:
        raise HTTPException(status_code=401, detail="Invalid session user.")


def _load() -> list[DependencyEdge]:
    if not DIGITAL_TWIN_EDGES_PATH.exists():
        return []
    try:
        raw = json.loads(DIGITAL_TWIN_EDGES_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("Digital Twin edge store root must be a list")
        return [DependencyEdge.model_validate(item) for item in raw]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="Digital Twin topology store is unavailable.") from exc


def _save(edges: list[DependencyEdge]) -> None:
    try:
        DIGITAL_TWIN_EDGES_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps([edge.model_dump() for edge in edges], indent=2, ensure_ascii=False) + "\n"
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=DIGITAL_TWIN_EDGES_PATH.parent,
            prefix=".digital-twin-edges-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        temp_path.replace(DIGITAL_TWIN_EDGES_PATH)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Unable to persist Digital Twin topology.") from exc


def _would_create_cycle(candidate: dict[str, str], custom_edges: list[DependencyEdge]) -> bool:
    working = [*_BUILT_IN_EDGES, *(edge.model_dump() for edge in custom_edges), candidate]
    visited: set[str] = set()
    active: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in active:
            return True
        if node_id in visited:
            return False
        visited.add(node_id)
        active.add(node_id)
        for edge in working:
            if edge["dependency_id"] == node_id and visit(edge["dependent_id"]):
                return True
        active.discard(node_id)
        return False

    return any(visit(node_id) for node_id in _NODE_IDS)


@router.get("/topology")
async def get_topology(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _authenticate(authorization)
    return {
        "built_in_edges": _BUILT_IN_EDGES,
        "custom_edges": [edge.model_dump() for edge in _load()],
    }


@router.post("/edges", response_model=DependencyEdge)
async def add_edge(
    request: DependencyEdgeCreate,
    authorization: Annotated[str | None, Header()] = None,
) -> DependencyEdge:
    _authenticate(authorization)
    if request.dependent_id == request.dependency_id:
        raise HTTPException(status_code=400, detail="A component cannot depend on itself.")
    if request.dependent_id not in _NODE_IDS or request.dependency_id not in _NODE_IDS:
        raise HTTPException(status_code=400, detail="Both topology components must exist.")

    edges = _load()
    candidate = DependencyEdge(
        dependent_id=request.dependent_id,
        dependency_id=request.dependency_id,
        reason=request.reason.strip() if request.reason and request.reason.strip() else (
            f"{request.dependent_id} depends on {request.dependency_id}."
        ),
    )

    existing = next(
        (
            edge
            for edge in [*(DependencyEdge.model_validate(e) for e in _BUILT_IN_EDGES), *edges]
            if edge.key == candidate.key
        ),
        None,
    )
    if existing is not None:
        # Matches the Flutter client's own idempotent no-op on a duplicate
        # edge rather than treating a repeat submission as an error.
        return existing

    if _would_create_cycle(candidate.model_dump(), edges):
        raise HTTPException(status_code=400, detail="That dependency would create a topology cycle.")

    edges.append(candidate)
    if len(edges) > MAX_CUSTOM_EDGES:
        raise HTTPException(status_code=400, detail="Custom topology edge limit reached.")
    _save(edges)
    return candidate


@router.delete("/edges/{edge_key}")
async def remove_edge(
    edge_key: str,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, bool]:
    _authenticate(authorization)
    edges = _load()
    remaining = [edge for edge in edges if edge.key != edge_key]
    removed = len(remaining) != len(edges)
    if removed:
        _save(remaining)
    return {"removed": removed}


@router.delete("/edges")
async def reset_edges(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, bool]:
    _authenticate(authorization)
    _save([])
    return {"removed": True}
