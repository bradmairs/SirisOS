import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

import jwt
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from app.api import homelab_alerts
from app.services.activity_service import ActivityService

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])

AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
RECOMMENDATIONS_PATH = Path(os.getenv("SIRISOS_RECOMMENDATIONS_PATH", "/app/data/recommendations.json"))
MAX_RECOMMENDATION_RECORDS = 500

RecommendationStatus = Literal["pending", "dismissed", "acted"]

activity_service = ActivityService()
activity_service.initialise()


class Recommendation(BaseModel):
    id: str
    rule_id: str
    title: str
    rationale: str
    severity: Literal["warning", "critical"]
    evidence_source: str
    evidence_id: str
    suggested_action: str
    capability_id: str | None = None
    capability_params: dict[str, str] | None = None
    status: RecommendationStatus
    created_at: str
    updated_at: str


class RecommendationStatusUpdate(BaseModel):
    status: RecommendationStatus


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


def _load() -> list[Recommendation]:
    if not RECOMMENDATIONS_PATH.exists():
        return []
    try:
        raw = json.loads(RECOMMENDATIONS_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("Recommendations store root must be a list")
        return [Recommendation.model_validate(item) for item in raw]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="Recommendations store is unavailable.") from exc


def _save(records: list[Recommendation]) -> None:
    try:
        RECOMMENDATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps([item.model_dump() for item in records], indent=2, ensure_ascii=False) + "\n"
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=RECOMMENDATIONS_PATH.parent,
            prefix=".recommendations-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        temp_path.replace(RECOMMENDATIONS_PATH)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Unable to persist recommendations.") from exc


def _suggested_action(alert_id: str) -> str:
    # v1's only rule: a small deterministic mapping from alert id shape to a
    # generic, human-actionable next step. No LLM involvement.
    if alert_id.startswith("host-"):
        return "Review host resource usage in Homelab."
    if alert_id == "docker-unavailable":
        return "Check the Docker socket proxy connection."
    if alert_id.endswith("-unhealthy"):
        return "Check container logs and restart if needed."
    if alert_id.endswith("-stopped"):
        return "Start the container if it should be running."
    if alert_id.endswith("-update"):
        return "Review and apply the available image update."
    return "Review in Homelab."


def _capability_binding(alert_id: str) -> tuple[str, dict[str, str]] | None:
    # Only bind alert shapes to a capability that the Action Framework
    # (app/api/actions.py) actually has a registered, already-audited
    # handler for -- host/docker-unavailable/image-update alerts stay
    # descriptive-only rather than pretending a capability exists.
    if not alert_id.startswith("container-"):
        return None
    if alert_id.endswith("-stopped"):
        container_id = alert_id.removeprefix("container-").removesuffix("-stopped")
        return "docker.start", {"container_id": container_id}
    if alert_id.endswith("-unhealthy"):
        container_id = alert_id.removeprefix("container-").removesuffix("-unhealthy")
        return "docker.restart", {"container_id": container_id}
    return None


async def _candidates(authorization: str | None) -> list[Recommendation]:
    summary = await homelab_alerts.alerts(authorization=authorization)
    now = _now_iso()
    candidates = []
    for alert in summary.alerts:
        binding = _capability_binding(alert.id)
        candidates.append(
            Recommendation(
                id=f"rec-{alert.id}",
                rule_id="alert_to_recommendation",
                title=alert.title,
                rationale=alert.message,
                severity=alert.severity,
                evidence_source="homelab_alerts",
                evidence_id=alert.id,
                suggested_action=_suggested_action(alert.id),
                capability_id=binding[0] if binding else None,
                capability_params=binding[1] if binding else None,
                status="pending",
                created_at=now,
                updated_at=now,
            )
        )
    return candidates


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


async def _reconcile(authorization: str | None) -> list[Recommendation]:
    candidates = await _candidates(authorization)
    existing = {item.id: item for item in _load()}

    reconciled: list[Recommendation] = []
    for candidate in candidates[:MAX_RECOMMENDATION_RECORDS]:
        prior = existing.get(candidate.id)
        if prior is None:
            reconciled.append(candidate)
            activity_service.record(
                module="recommendations",
                event_type="recommendation_created",
                title=candidate.title,
                message=candidate.rationale,
                severity=candidate.severity,
            )
        else:
            reconciled.append(
                candidate.model_copy(
                    update={
                        "status": prior.status,
                        "created_at": prior.created_at,
                        "updated_at": prior.updated_at,
                    }
                )
            )

    _save(reconciled)
    return reconciled


@router.get("", response_model=list[Recommendation])
async def list_recommendations(
    status: Annotated[RecommendationStatus | None, Query()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> list[Recommendation]:
    _authenticate(authorization)
    records = await _reconcile(authorization)
    if status is not None:
        records = [item for item in records if item.status == status]
    return records


@router.patch("/{recommendation_id}", response_model=Recommendation)
async def update_recommendation_status(
    recommendation_id: str,
    request: RecommendationStatusUpdate,
    authorization: Annotated[str | None, Header()] = None,
) -> Recommendation:
    _authenticate(authorization)
    records = _load()
    for index, item in enumerate(records):
        if item.id == recommendation_id:
            updated = item.model_copy(update={"status": request.status, "updated_at": _now_iso()})
            records[index] = updated
            _save(records)
            return updated
    raise HTTPException(status_code=404, detail="Recommendation not found.")
