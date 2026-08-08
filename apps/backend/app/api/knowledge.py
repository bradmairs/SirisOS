from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

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
    return sorted({tag for tag in tags if tag})


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
        tags=_frontmatter_tags(content),
        wikilinks=_wikilinks(content),
        is_daily_note=_is_daily(path.relative_to(VAULT_ROOT)),
    )


@router.get("/overview", response_model=KnowledgeOverviewResponse)
async def knowledge_overview(
    authorization: Annotated[str | None, Header()] = None,
) -> KnowledgeOverviewResponse:
    _authenticate(authorization)
    files = _markdown_files()
    summaries = []
    for path in files:
        try:
            summaries.append(_summary(path))
        except (OSError, HTTPException):
            continue
    summaries.sort(key=lambda item: item.modified_at, reverse=True)
    daily = [item for item in summaries if item.is_daily_note][:10]
    return KnowledgeOverviewResponse(
        available=VAULT_ROOT.exists() and VAULT_ROOT.is_dir(),
        vault_name=VAULT_ROOT.name or "Knowledge",
        note_count=len(summaries),
        recent=summaries[:20],
        daily=daily,
    )


@router.get("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    query: Annotated[str, Query(min_length=1, max_length=200)],
    authorization: Annotated[str | None, Header()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> KnowledgeSearchResponse:
    _authenticate(authorization)
    needle = query.strip().lower()
    scored: list[tuple[int, KnowledgeNoteSummary]] = []
    for path in _markdown_files():
        try:
            text = _read_text(path)
            summary = _summary(path, text)
        except (OSError, HTTPException):
            continue
        title = summary.title.lower()
        relative = summary.path.lower()
        body = text.lower()
        score = 0
        if needle == title:
            score += 100
        elif needle in title:
            score += 60
        if needle in relative:
            score += 30
        occurrences = body.count(needle)
        score += min(occurrences, 10) * 5
        if score > 0:
            scored.append((score, summary))
    scored.sort(key=lambda item: (-item[0], item[1].title.lower()))
    return KnowledgeSearchResponse(query=query.strip(), hits=[item[1] for item in scored[:limit]])


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
