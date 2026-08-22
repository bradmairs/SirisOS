import json
from typing import Annotated
import os

import jwt
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from app.api import engineering_calculations, engineering_standards, projects, siris_memory
from app.services.activity_service import ActivityService
from app.services.docker_service import DockerMonitor
from app.services.gym_service import GymService
from app.services.knowledge_global_search import search_knowledge_notes
from app.services.project_service import ProjectService, ProjectStoreUnavailableError
from app.services.running_service import RunningService

router = APIRouter(prefix="/search", tags=["search"])

AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")

running_service = RunningService()
gym_service = GymService()
activity_service = ActivityService()
docker_monitor = DockerMonitor()
running_service.initialise()
gym_service.initialise()
activity_service.initialise()


class SearchResult(BaseModel):
    module: str
    title: str
    subtitle: str
    target: str
    reference_id: str | None = None


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


@router.get("", response_model=list[SearchResult])
async def search(
    q: Annotated[str, Query(min_length=2, max_length=100)],
    authorization: Annotated[str | None, Header()] = None,
) -> list[SearchResult]:
    _authenticate(authorization)
    term = q.strip().lower()
    results: list[SearchResult] = []

    docker = docker_monitor.collect()
    if docker.available:
        for item in docker.containers:
            haystack = f"{item.name} {item.image} {item.state} {item.status} {item.health or ''}".lower()
            if term in haystack:
                results.append(SearchResult(
                    module="homelab",
                    title=item.name,
                    subtitle=f"{item.image} · {item.state}",
                    target="homelab",
                    reference_id=item.container_id,
                ))

    for run in running_service.list_runs():
        pace = f"{run.average_pace_seconds_per_km // 60}:{run.average_pace_seconds_per_km % 60:02d}/km"
        haystack = f"{run.run_type} {run.distance_km} {pace} {run.average_heart_rate} {run.run_date}".lower()
        if term in haystack:
            results.append(SearchResult(
                module="running",
                title=f"{run.distance_km:.1f} km {run.run_type} run",
                subtitle=f"{run.run_date.isoformat()} · {pace} · {run.average_heart_rate} bpm",
                target="running",
                reference_id=str(run.id),
            ))

    for workout in gym_service.list_workouts():
        exercises = ", ".join(sorted({item.exercise for item in workout.sets}))
        haystack = f"{workout.name} {workout.notes or ''} {exercises} {workout.workout_date}".lower()
        if term in haystack:
            results.append(SearchResult(
                module="gym",
                title=workout.name,
                subtitle=f"{workout.workout_date.isoformat()} · {len(workout.sets)} sets · {exercises}",
                target="gym",
                reference_id=str(workout.id),
            ))

    for item in await search_knowledge_notes(term):
        results.append(SearchResult(
            module="knowledge",
            title=item.title,
            subtitle=item.subtitle,
            target="knowledge",
            reference_id=item.path,
        ))

    for event in activity_service.list_events(limit=100):
        haystack = f"{event.module} {event.title} {event.message} {event.event_type}".lower()
        if term in haystack:
            results.append(SearchResult(
                module="activity",
                title=event.title,
                subtitle=f"{event.module.title()} · {event.message}",
                target="notifications",
                reference_id=str(event.id),
            ))

    try:
        project_records = ProjectService(
            projects_path=projects.PROJECTS_PATH, project_context_path=projects.PROJECT_CONTEXT_PATH
        ).list_projects()
    except ProjectStoreUnavailableError:
        # Search degrades gracefully per-source: a corrupted store must not
        # take down search for everything else.
        project_records = []
    for project in project_records:
        haystack = f"{project.name} {project.description} {project.kind} {' '.join(project.tags)}".lower()
        if term in haystack:
            results.append(SearchResult(
                module="projects",
                title=project.name,
                subtitle=f"{project.kind.title()} · {project.status.title()}",
                target="projects",
                reference_id=project.id,
            ))

    try:
        calculation_records = engineering_calculations._load()
    except HTTPException:
        calculation_records = []
    for calculation in calculation_records:
        haystack = f"{calculation.title} {calculation.calculator_id} {calculation.notes}".lower()
        if term in haystack:
            results.append(SearchResult(
                module="engineering",
                title=calculation.title,
                subtitle=f"Saved calculation · {calculation.calculator_id}",
                target="engineering",
                reference_id=calculation.id,
            ))

    engineering_standards.LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
    for metadata_path in sorted(engineering_standards.LIBRARY_ROOT.glob("*/metadata.json")):
        try:
            metadata = engineering_standards._normalise_metadata(
                json.loads(metadata_path.read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError):
            continue
        if not metadata["active"]:
            continue
        haystack = " ".join(
            str(metadata.get(key) or "") for key in ("title", "authority", "reference", "edition")
        ).lower()
        if term in haystack:
            results.append(SearchResult(
                module="engineering",
                title=str(metadata.get("reference") or metadata.get("title")),
                subtitle=f"Standard · {metadata.get('authority') or 'Unknown authority'}",
                target="engineering",
                reference_id=str(metadata.get("id")),
            ))

    try:
        memory_records = siris_memory._load()
    except HTTPException:
        memory_records = []
    for memory in memory_records:
        haystack = f"{memory.memory_class} {memory.content} {memory.source or ''}".lower()
        if term in haystack:
            results.append(SearchResult(
                module="siris",
                title=memory.content[:80],
                subtitle=f"Siris Memory · {memory.memory_class.title()}",
                target="siris",
                reference_id=memory.id,
            ))

    return results[:50]
