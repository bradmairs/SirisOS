from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_SEARCH_LIMIT = 30


@dataclass(frozen=True)
class KnowledgeNote:
    path: str
    title: str
    modified_at: str
    size_bytes: int
    tags: list[str]
    wikilinks: list[str]
    is_daily_note: bool


@dataclass(frozen=True)
class KnowledgeNoteContent:
    path: str
    title: str
    modified_at: str
    size_bytes: int
    tags: list[str]
    wikilinks: list[str]
    is_daily_note: bool
    content: str


@dataclass(frozen=True)
class KnowledgeSearchResult:
    query: str
    hits: list[KnowledgeNote] = field(default_factory=list)


def _vault_root() -> Path:
    return Path(os.getenv("SIRISOS_KNOWLEDGE_VAULT_PATH", "/app/data/knowledge"))


def _max_note_bytes() -> int:
    return int(os.getenv("SIRISOS_KNOWLEDGE_MAX_NOTE_KB", "1024")) * 1024


def _max_scan_files() -> int:
    return int(os.getenv("SIRISOS_KNOWLEDGE_MAX_SCAN_FILES", "5000"))


def markdown_files(vault_root: Path, *, max_files: int | None = None) -> list[Path]:
    if not vault_root.exists() or not vault_root.is_dir():
        return []
    files: list[Path] = []
    limit = max_files if max_files is not None else _max_scan_files()
    for path in vault_root.rglob("*.md"):
        try:
            relative = path.relative_to(vault_root)
        except ValueError:
            continue
        if any(part.startswith(".") for part in relative.parts):
            continue
        files.append(path)
        if len(files) >= limit:
            break
    return files


def safe_note_path(vault_root: Path, relative_path: str) -> Path | None:
    candidate = (vault_root / relative_path).resolve()
    root = vault_root.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if candidate.suffix.lower() != ".md" or not candidate.is_file():
        return None
    return candidate


def read_text(path: Path, *, max_bytes: int | None = None) -> str | None:
    limit = max_bytes if max_bytes is not None else _max_note_bytes()
    size = path.stat().st_size
    if size > limit:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None


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


def note_tags(text: str) -> list[str]:
    values = list(_frontmatter_tags(text))
    values.extend(re.findall(r"(?<![\w#])#([A-Za-z0-9][A-Za-z0-9_/-]*)", text))
    return sorted({value.strip().lstrip("#") for value in values if value.strip()})[:100]


def note_wikilinks(text: str) -> list[str]:
    values = []
    for raw in re.findall(r"\[\[([^\]]+)\]\]", text):
        target = raw.split("|", 1)[0].split("#", 1)[0].strip()
        if target:
            values.append(target)
    return sorted(set(values))[:100]


def note_title(path: Path, text: str) -> str:
    heading = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    if heading:
        return heading.group(1).strip()
    return path.stem


def is_daily_note(relative_path: Path) -> bool:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", relative_path.stem):
        return True
    return any(part.lower() in {"daily", "daily notes", "journal"} for part in relative_path.parts)


def summarise(
    vault_root: Path, path: Path, text: str | None = None, *, max_bytes: int | None = None
) -> KnowledgeNote | None:
    stat = path.stat()
    content = text if text is not None else read_text(path, max_bytes=max_bytes)
    if content is None:
        return None
    return KnowledgeNote(
        path=path.relative_to(vault_root).as_posix(),
        title=note_title(path, content),
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        size_bytes=stat.st_size,
        tags=note_tags(content),
        wikilinks=note_wikilinks(content),
        is_daily_note=is_daily_note(path.relative_to(vault_root)),
    )


def all_summaries(vault_root: Path, *, max_files: int | None = None, max_bytes: int | None = None) -> list[KnowledgeNote]:
    summaries: list[KnowledgeNote] = []
    for path in markdown_files(vault_root, max_files=max_files):
        try:
            summary = summarise(vault_root, path, max_bytes=max_bytes)
        except OSError:
            continue
        if summary is not None:
            summaries.append(summary)
    return summaries


class KnowledgeService:
    """Read access to the Knowledge vault for callers that only need to find
    and read notes -- SirisAgent, and the `/search` and `/note` API routes.
    The richer navigation features (browse, backlinks, related notes, the
    graph view) stay directly in app/api/knowledge.py, which imports the
    scanning primitives from this module rather than duplicating them."""

    def __init__(self, vault_root: Path | None = None) -> None:
        self._vault_root = vault_root or _vault_root()

    def search(
        self,
        query: str,
        *,
        limit: int = DEFAULT_SEARCH_LIMIT,
        folder: str | None = None,
        tag: str | None = None,
    ) -> KnowledgeSearchResult:
        needle = query.strip().lower()
        # A query is more often several keywords (typed by a person, or a
        # whole phrase generated by SirisAgent from a free-text question)
        # than one exact contiguous phrase -- "drainage design pipe grade"
        # never appears verbatim in a note that separately says "drainage
        # design" and "pipe grade". Word-level scoring below finds that real
        # match; the exact-phrase scoring stays first/highest so a genuine
        # phrase match still ranks above a same-word-count coincidence.
        words = needle.split()
        folder_value = folder.strip("/ ").lower() if folder else None
        tag_value = tag.strip().lstrip("#").lower() if tag else None

        scored: list[tuple[int, KnowledgeNote]] = []
        for path in markdown_files(self._vault_root):
            try:
                text = read_text(path)
            except OSError:
                continue
            if text is None:
                continue
            summary = summarise(self._vault_root, path, text)
            if summary is None:
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
                if len(words) > 1:
                    for word in words:
                        if word in title:
                            score += 20
                        score += min(body.count(word), 5) * 2
            if score > 0:
                scored.append((score, summary))
        scored.sort(key=lambda item: (-item[0], item[1].title.lower()))
        return KnowledgeSearchResult(query=query.strip(), hits=[item[1] for item in scored[:limit]])

    def read_note(self, path: str) -> KnowledgeNoteContent | None:
        note_path = safe_note_path(self._vault_root, path)
        if note_path is None:
            return None
        text = read_text(note_path)
        if text is None:
            return None
        summary = summarise(self._vault_root, note_path, text)
        if summary is None:
            return None
        return KnowledgeNoteContent(
            path=summary.path,
            title=summary.title,
            modified_at=summary.modified_at,
            size_bytes=summary.size_bytes,
            tags=summary.tags,
            wikilinks=summary.wikilinks,
            is_daily_note=summary.is_daily_note,
            content=text,
        )
