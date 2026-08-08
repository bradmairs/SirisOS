from __future__ import annotations

import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])
AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
VAULT_ROOT = Path(os.getenv("SIRISOS_KNOWLEDGE_VAULT_PATH", "/app/data/knowledge"))
MAX_NOTE_BYTES = int(os.getenv("SIRISOS_KNOWLEDGE_MAX_NOTE_KB", "1024")) * 1024
MAX_SCAN_FILES = int(os.getenv("SIRISOS_KNOWLEDGE_MAX_SCAN_FILES", "5000"))


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


def _markdown_files() -> list[Path]:
    if not VAULT_ROOT.exists() or not VAULT_ROOT.is_dir():
        return []
    files: list[Path] = []
    for path in VAULT_ROOT.rglob("*.md"):
        try:
            relative = path.relative_to(VAULT_ROOT)
        except ValueError:
            continue
        if any(part.startswith(".") for part in relative.parts):
            continue
        files.append(path)
        if len(files) >= MAX_SCAN_FILES:
            break
    return files


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
    size = path.stat().st_size
    if size > MAX_NOTE_BYTES:
        raise HTTPException(status_code=413, detail="Knowledge note exceeds the configured read limit.")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _frontmatter_tags(text: str) -> list[str]:
    if not text.startswith("---"):
        return []
    end = text.find("\n---", 3)
    if end < 0:
        return []
    block = text[3:end]
    tags: list[str] = []
    inline = re.search(r"(?mi)^tags\s*:\s*\[(.*?)\]\s*$", block)
    if inline:
        tags.extend(part.strip().strip("'\"") for part in inline.group(1).split(","))
    simple = re.search(r"(?mi)^tags\s*:\s*([^\n\[]+)\s*$", block)
    if simple:
        tags.extend(part.strip().lstrip("#") for part in simple.group(1).split())
    return [tag for tag in tags if tag]


def _tags(text: str) -> list[str]:
    values = list(_frontmatter_tags(text))
    values.extend(re.findall(r"(?<![\w#])#([A-Za-z0-9][A-Za-z0-9_/-]*)", text))
    return sorted({value.strip().lstrip("#") for value in values if value.strip()})[:100]


def _wikilinks(text: str) -> list[str]:
    values = []
    for raw in re.findall(r"\[\[([^\]]+)\]\]", text):
        target = raw.split("|", 1)[0].split("#", 1)[0].strip()
        if target:
            values.append(target)
    return sorted(set(values))[:100]


def _title(path: Path, text: str) -> str:
    heading = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    if heading:
        return heading.group(1).strip()
    return path.stem


def _is_daily(path: Path) -> bool:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.stem):
        return True
    return any(part.lower() in {"daily", "daily notes", "journal"} for part in path.parts)


def _summary(path: Path, text: str | None = None) -> KnowledgeNoteSummary:
    stat = path.stat()
    content = text if text is not None else _read_text(path)
    return KnowledgeNoteSummary(
        path=path.relative_to(VAULT_ROOT).as_posix(),
        title=_title(path, content),
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        size_bytes=stat.st_size,
        tags=_tags(content),
        wikilinks=_wikilinks(content),
        is_daily_note=_is_daily(path.relative_to(VAULT_ROOT)),
    )


def _all_summaries() -> list[KnowledgeNoteSummary]:
    summaries: list[KnowledgeNoteSummary] = []
    for path in _markdown_files():
        try:
            summaries.append(_summary(path))
        except (OSError, HTTPException):
            continue
    return summaries


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

    direct = by_path.get(value.lower())
    if direct is not None:
        return direct, [direct]

    if source_path:
        parent = Path(source_path).parent.as_posix()
        relative_key = f"{parent}/{value}".strip("/").lower()
        relative = by_path.get(relative_key)
        if relative is not None:
            return relative, [relative]

    matches_by_path: dict[str, KnowledgeNoteSummary] = {}
    for item in by_stem.get(Path(value).name.lower(), []):
        matches_by_path[item.path] = item
    for item in by_title.get(value.lower(), []):
        matches_by_path[item.path] = item
    matches = sorted(matches_by_path.values(), key=lambda item: item.path.lower())
    return (matches[0], matches) if len(matches) == 1 else (None, matches)


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
    needle = query.strip().lower()
    folder_value = folder.strip("/ ").lower() if folder else None
    tag_value = tag.strip().lstrip("#").lower() if tag else None
    scored: list[tuple[int, KnowledgeNoteSummary]] = []
    for path in _markdown_files():
        try:
            text = _read_text(path)
            summary = _summary(path, text)
        except (OSError, HTTPException):
            continue
        if folder_value and not summary.path.lower().startswith(f"{folder_value}/"):
            continue
        if tag_value and tag_value not in {value.lower() for value in summary.tags}:
            continue
        title = summary.title.lower()
        relative = summary.path.lower()
        body = text.lower()
        score = 1 if not needle else 0
        if needle:
            if needle == title:
                score += 100
            elif needle in title:
                score += 60
            if needle in relative:
                score += 30
            score += min(body.count(needle), 10) * 5
        if score > 0:
            scored.append((score, summary))
    scored.sort(key=lambda item: (-item[0], item[1].title.lower()))
    return KnowledgeSearchResponse(query=query.strip(), hits=[item[1] for item in scored[:limit]])


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


@router.get("/note", response_model=KnowledgeNoteResponse)
async def get_knowledge_note(
    path: Annotated[str, Query(min_length=1, max_length=1000)],
    authorization: Annotated[str | None, Header()] = None,
) -> KnowledgeNoteResponse:
    _authenticate(authorization)
    note_path = _safe_note_path(path)
    text = _read_text(note_path)
    summary = _summary(note_path, text)
    return KnowledgeNoteResponse(**summary.model_dump(), content=text)
