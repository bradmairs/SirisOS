from __future__ import annotations

import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.knowledge_service import KnowledgeService
from app.services.knowledge_service import all_summaries as _service_all_summaries
from app.services.knowledge_service import markdown_files as _service_markdown_files
from app.services.knowledge_service import note_tags as _service_note_tags
from app.services.knowledge_service import read_text as _service_read_text
from app.services.knowledge_service import summarise as _service_summarise

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])
AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
VAULT_ROOT = Path(os.getenv("SIRISOS_KNOWLEDGE_VAULT_PATH", "/app/data/knowledge"))
MAX_NOTE_BYTES = int(os.getenv("SIRISOS_KNOWLEDGE_MAX_NOTE_KB", "1024")) * 1024
MAX_SCAN_FILES = int(os.getenv("SIRISOS_KNOWLEDGE_MAX_SCAN_FILES", "5000"))
knowledge_service = KnowledgeService(vault_root=VAULT_ROOT)


class KnowledgeNoteSummary(BaseModel):
    path: str
    title: str
    modified_at: str
    size_bytes: int
    tags: list[str]
    wikilinks: list[str]
    is_daily_note: bool


class KnowledgeNoteResponse(KnowledgeNoteSummary):
    content: str


class KnowledgeOverviewResponse(BaseModel):
    available: bool
    vault_name: str
    note_count: int
    recent: list[KnowledgeNoteSummary]
    daily: list[KnowledgeNoteSummary]


class KnowledgeSearchResponse(BaseModel):
    query: str
    hits: list[KnowledgeNoteSummary]


class KnowledgeFolderSummary(BaseModel):
    path: str
    name: str
    note_count: int


class KnowledgeTagSummary(BaseModel):
    tag: str
    note_count: int


class KnowledgeBrowseResponse(BaseModel):
    folders: list[KnowledgeFolderSummary]
    tags: list[KnowledgeTagSummary]


class KnowledgeBacklinksResponse(BaseModel):
    path: str
    backlinks: list[KnowledgeNoteSummary]


class KnowledgeLinkResolutionResponse(BaseModel):
    target: str
    resolved: bool
    ambiguous: bool
    note: KnowledgeNoteSummary | None = None
    candidates: list[KnowledgeNoteSummary] = Field(default_factory=list)


class KnowledgeRelatedNote(BaseModel):
    note: KnowledgeNoteSummary
    score: int
    reasons: list[str]


class KnowledgeRelatedResponse(BaseModel):
    path: str
    related: list[KnowledgeRelatedNote]


class KnowledgeGraphNode(BaseModel):
    id: str
    title: str
    center: bool = False


class KnowledgeGraphEdge(BaseModel):
    source: str
    target: str
    kind: str
    label: str


class KnowledgeGraphResponse(BaseModel):
    center_path: str
    nodes: list[KnowledgeGraphNode]
    edges: list[KnowledgeGraphEdge]


LinkIndex = tuple[
    dict[str, KnowledgeNoteSummary],
    dict[str, list[KnowledgeNoteSummary]],
    dict[str, list[KnowledgeNoteSummary]],
]


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


# Note-scanning primitives (frontmatter/tag/wikilink parsing, safe path
# resolution, summarising) live in app.services.knowledge_service, shared
# with KnowledgeService.search()/read_note() (the two SirisAgent uses). The
# thin wrappers below just translate that service's None-on-failure
# contract into this route file's existing HTTPException behaviour, so the
# richer navigation routes below (browse, resolve, backlinks, related,
# graph) -- which aren't needed by the agent and stay here -- don't change.


def _tags(text: str) -> list[str]:
    return _service_note_tags(text)


def _markdown_files() -> list[Path]:
    return _service_markdown_files(VAULT_ROOT, max_files=MAX_SCAN_FILES)


def _safe_note_path(relative_path: str) -> Path:
    candidate = (VAULT_ROOT / relative_path).resolve()
    root = VAULT_ROOT.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid note path.") from exc
    if candidate.suffix.lower() != ".md" or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Knowledge note not found.")
    return candidate


def _read_text(path: Path) -> str:
    text = _service_read_text(path, max_bytes=MAX_NOTE_BYTES)
    if text is None:
        raise HTTPException(status_code=413, detail="Knowledge note exceeds the configured read limit.")
    return text


def _summary(path: Path, text: str | None = None) -> KnowledgeNoteSummary:
    note = _service_summarise(VAULT_ROOT, path, text, max_bytes=MAX_NOTE_BYTES)
    if note is None:
        raise HTTPException(status_code=413, detail="Knowledge note exceeds the configured read limit.")
    return KnowledgeNoteSummary(**note.__dict__)


def _all_summaries() -> list[KnowledgeNoteSummary]:
    return [
        KnowledgeNoteSummary(**note.__dict__)
        for note in _service_all_summaries(VAULT_ROOT, max_files=MAX_SCAN_FILES, max_bytes=MAX_NOTE_BYTES)
    ]


def _normalise_target(target: str) -> str:
    value = target.split("|", 1)[0].split("#", 1)[0].strip().replace("\\", "/")
    if value.lower().endswith(".md"):
        value = value[:-3]
    return value.strip("/")


def _build_link_index(summaries: list[KnowledgeNoteSummary]) -> LinkIndex:
    by_path: dict[str, KnowledgeNoteSummary] = {}
    by_stem: dict[str, list[KnowledgeNoteSummary]] = defaultdict(list)
    by_title: dict[str, list[KnowledgeNoteSummary]] = defaultdict(list)
    for item in summaries:
        path_key = item.path[:-3] if item.path.lower().endswith(".md") else item.path
        by_path[path_key.lower()] = item
        by_stem[Path(item.path).stem.lower()].append(item)
        by_title[item.title.strip().lower()].append(item)
    return by_path, dict(by_stem), dict(by_title)


def _resolve_link(
    target: str,
    source_path: str | None = None,
    *,
    summaries: list[KnowledgeNoteSummary] | None = None,
    index: LinkIndex | None = None,
) -> tuple[KnowledgeNoteSummary | None, list[KnowledgeNoteSummary]]:
    value = _normalise_target(target)
    if not value:
        return None, []
    values = summaries if summaries is not None else _all_summaries()
    by_path, by_stem, by_title = index if index is not None else _build_link_index(values)
    path_qualified = "/" in value

    if path_qualified:
        direct = by_path.get(value.lower())
        if direct is not None:
            return direct, [direct]

    if source_path:
        parent = Path(source_path).parent.as_posix()
        relative_key = f"{parent}/{value}".strip("/").lower()
        relative = by_path.get(relative_key)
        if relative is not None:
            return relative, [relative]

    if not path_qualified:
        direct = by_path.get(value.lower())
        if direct is not None:
            return direct, [direct]

    matches_by_path: dict[str, KnowledgeNoteSummary] = {}
    for item in by_stem.get(Path(value).name.lower(), []):
        matches_by_path[item.path] = item
    for item in by_title.get(value.lower(), []):
        matches_by_path[item.path] = item
    matches = sorted(matches_by_path.values(), key=lambda item: item.path.lower())
    return (matches[0], matches) if len(matches) == 1 else (None, matches)


def _related_notes(
    target_summary: KnowledgeNoteSummary,
    summaries: list[KnowledgeNoteSummary],
    index: LinkIndex,
    *,
    limit: int = 12,
) -> list[KnowledgeRelatedNote]:
    target_tags = {tag.lower() for tag in target_summary.tags}
    target_parent = Path(target_summary.path).parent.as_posix().lower()
    outgoing: set[str] = set()
    for link in target_summary.wikilinks:
        resolved, _ = _resolve_link(link, target_summary.path, summaries=summaries, index=index)
        if resolved is not None:
            outgoing.add(resolved.path)

    ranked: list[KnowledgeRelatedNote] = []
    for candidate in summaries:
        if candidate.path == target_summary.path:
            continue
        score = 0
        reasons: list[str] = []

        if candidate.path in outgoing:
            score += 100
            reasons.append("linked from this note")

        links_back = False
        for link in candidate.wikilinks:
            resolved, _ = _resolve_link(link, candidate.path, summaries=summaries, index=index)
            if resolved is not None and resolved.path == target_summary.path:
                links_back = True
                break
        if links_back:
            score += 90
            reasons.append("links back to this note")

        shared_tags = sorted(target_tags & {tag.lower() for tag in candidate.tags})
        if shared_tags:
            score += min(len(shared_tags), 4) * 15
            reasons.append("shared tags: " + ", ".join(f"#{tag}" for tag in shared_tags[:4]))

        candidate_parent = Path(candidate.path).parent.as_posix().lower()
        if target_parent != "." and candidate_parent == target_parent:
            score += 5
            reasons.append("same folder")

        if score > 0:
            ranked.append(KnowledgeRelatedNote(note=candidate, score=score, reasons=reasons))

    ranked.sort(key=lambda item: (-item.score, item.note.title.lower(), item.note.path.lower()))
    return ranked[:limit]


def _graph_for(target_summary: KnowledgeNoteSummary, related: list[KnowledgeRelatedNote]) -> KnowledgeGraphResponse:
    nodes = [KnowledgeGraphNode(id=target_summary.path, title=target_summary.title, center=True)]
    edges: list[KnowledgeGraphEdge] = []
    for item in related:
        nodes.append(KnowledgeGraphNode(id=item.note.path, title=item.note.title))
        for reason in item.reasons:
            if reason == "linked from this note":
                kind = "outgoing"
            elif reason == "links back to this note":
                kind = "backlink"
            elif reason.startswith("shared tags"):
                kind = "tag"
            else:
                kind = "folder"
            edges.append(
                KnowledgeGraphEdge(
                    source=target_summary.path,
                    target=item.note.path,
                    kind=kind,
                    label=reason,
                )
            )
    return KnowledgeGraphResponse(center_path=target_summary.path, nodes=nodes, edges=edges)


@router.get("/overview", response_model=KnowledgeOverviewResponse)
async def knowledge_overview(
    authorization: Annotated[str | None, Header()] = None,
) -> KnowledgeOverviewResponse:
    _authenticate(authorization)
    summaries = _all_summaries()
    summaries.sort(key=lambda item: item.modified_at, reverse=True)
    daily = [item for item in summaries if item.is_daily_note][:10]
    return KnowledgeOverviewResponse(
        available=VAULT_ROOT.exists() and VAULT_ROOT.is_dir(),
        vault_name=VAULT_ROOT.name or "Knowledge",
        note_count=len(summaries),
        recent=summaries[:20],
        daily=daily,
    )


@router.get("/browse", response_model=KnowledgeBrowseResponse)
async def browse_knowledge(
    authorization: Annotated[str | None, Header()] = None,
) -> KnowledgeBrowseResponse:
    _authenticate(authorization)
    summaries = _all_summaries()
    folder_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
    for item in summaries:
        parent = Path(item.path).parent.as_posix()
        if parent != ".":
            folder_counts[parent] += 1
        for tag in item.tags:
            tag_counts[tag] += 1
    folders = [
        KnowledgeFolderSummary(path=path, name=Path(path).name, note_count=count)
        for path, count in sorted(folder_counts.items(), key=lambda value: value[0].lower())
    ]
    tags = [
        KnowledgeTagSummary(tag=tag, note_count=count)
        for tag, count in sorted(tag_counts.items(), key=lambda value: (-value[1], value[0].lower()))
    ]
    return KnowledgeBrowseResponse(folders=folders, tags=tags)


@router.get("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    query: Annotated[str, Query(max_length=200)] = "",
    authorization: Annotated[str | None, Header()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    folder: Annotated[str | None, Query(max_length=500)] = None,
    tag: Annotated[str | None, Query(max_length=120)] = None,
) -> KnowledgeSearchResponse:
    _authenticate(authorization)
    result = knowledge_service.search(query, limit=limit, folder=folder, tag=tag)
    return KnowledgeSearchResponse(
        query=result.query,
        hits=[KnowledgeNoteSummary(**note.__dict__) for note in result.hits],
    )


@router.get("/resolve", response_model=KnowledgeLinkResolutionResponse)
async def resolve_knowledge_link(
    target: Annotated[str, Query(min_length=1, max_length=1000)],
    authorization: Annotated[str | None, Header()] = None,
    source_path: Annotated[str | None, Query(max_length=1000)] = None,
) -> KnowledgeLinkResolutionResponse:
    _authenticate(authorization)
    summaries = _all_summaries()
    note, candidates = _resolve_link(target, source_path, summaries=summaries, index=_build_link_index(summaries))
    return KnowledgeLinkResolutionResponse(
        target=target,
        resolved=note is not None,
        ambiguous=note is None and len(candidates) > 1,
        note=note,
        candidates=candidates[:20],
    )


@router.get("/backlinks", response_model=KnowledgeBacklinksResponse)
async def knowledge_backlinks(
    path: Annotated[str, Query(min_length=1, max_length=1000)],
    authorization: Annotated[str | None, Header()] = None,
) -> KnowledgeBacklinksResponse:
    _authenticate(authorization)
    target_path = _safe_note_path(path)
    summaries = _all_summaries()
    index = _build_link_index(summaries)
    target_summary = next((item for item in summaries if item.path == target_path.relative_to(VAULT_ROOT).as_posix()), _summary(target_path))
    backlinks: list[KnowledgeNoteSummary] = []
    for candidate in summaries:
        if candidate.path == target_summary.path:
            continue
        for link in candidate.wikilinks:
            resolved, _ = _resolve_link(link, candidate.path, summaries=summaries, index=index)
            if resolved is not None and resolved.path == target_summary.path:
                backlinks.append(candidate)
                break
    backlinks.sort(key=lambda item: item.modified_at, reverse=True)
    return KnowledgeBacklinksResponse(path=target_summary.path, backlinks=backlinks[:100])


@router.get("/related", response_model=KnowledgeRelatedResponse)
async def knowledge_related(
    path: Annotated[str, Query(min_length=1, max_length=1000)],
    authorization: Annotated[str | None, Header()] = None,
    limit: Annotated[int, Query(ge=1, le=30)] = 12,
) -> KnowledgeRelatedResponse:
    _authenticate(authorization)
    target_path = _safe_note_path(path)
    summaries = _all_summaries()
    index = _build_link_index(summaries)
    relative = target_path.relative_to(VAULT_ROOT).as_posix()
    target_summary = next((item for item in summaries if item.path == relative), _summary(target_path))
    return KnowledgeRelatedResponse(
        path=target_summary.path,
        related=_related_notes(target_summary, summaries, index, limit=limit),
    )


@router.get("/graph", response_model=KnowledgeGraphResponse)
async def knowledge_graph(
    path: Annotated[str, Query(min_length=1, max_length=1000)],
    authorization: Annotated[str | None, Header()] = None,
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> KnowledgeGraphResponse:
    _authenticate(authorization)
    target_path = _safe_note_path(path)
    summaries = _all_summaries()
    index = _build_link_index(summaries)
    relative = target_path.relative_to(VAULT_ROOT).as_posix()
    target_summary = next((item for item in summaries if item.path == relative), _summary(target_path))
    related = _related_notes(target_summary, summaries, index, limit=limit)
    return _graph_for(target_summary, related)


@router.get("/note", response_model=KnowledgeNoteResponse)
async def get_knowledge_note(
    path: Annotated[str, Query(min_length=1, max_length=1000)],
    authorization: Annotated[str | None, Header()] = None,
) -> KnowledgeNoteResponse:
    _authenticate(authorization)
    note = knowledge_service.read_note(path)
    if note is None:
        raise HTTPException(status_code=404, detail="Knowledge note not found.")
    return KnowledgeNoteResponse(**note.__dict__)
