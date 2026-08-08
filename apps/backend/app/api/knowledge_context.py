from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel

from app.api import knowledge

router = APIRouter(prefix="/api/v1/knowledge/context", tags=["knowledge"])


class KnowledgeContextResponse(BaseModel):
    context_id: str
    notes: list[knowledge.KnowledgeNoteSummary]


def _frontmatter_block(text: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end < 0:
        return ""
    return text[3:end]


def _siris_contexts(text: str) -> set[str]:
    contexts: set[str] = set()
    block = _frontmatter_block(text)
    if block:
        inline = re.search(r"(?mi)^siris\s*:\s*\[(.*?)\]\s*$", block)
        if inline:
            contexts.update(
                part.strip().strip("'\"").lower()
                for part in inline.group(1).split(",")
                if part.strip().strip("'\"")
            )
        simple = re.search(r"(?mi)^siris\s*:\s*([^\n\[]+)\s*$", block)
        if simple:
            raw = simple.group(1).replace(",", " ")
            contexts.update(
                part.strip().strip("'\"").lower()
                for part in raw.split()
                if part.strip().strip("'\"")
            )

    for tag in knowledge._tags(text):
        lowered = tag.lower()
        if lowered.startswith("siris/") and len(lowered) > len("siris/"):
            contexts.add(lowered.removeprefix("siris/"))
    return contexts


def _context_notes(context_id: str, *, limit: int = 20) -> list[knowledge.KnowledgeNoteSummary]:
    target = context_id.strip().lower()
    if not target:
        return []
    matches: list[knowledge.KnowledgeNoteSummary] = []
    for path in knowledge._markdown_files():
        try:
            text = knowledge._read_text(path)
            if target not in _siris_contexts(text):
                continue
            matches.append(knowledge._summary(path, text))
        except Exception:
            continue
    matches.sort(key=lambda item: item.modified_at, reverse=True)
    return matches[:limit]


@router.get("", response_model=KnowledgeContextResponse)
async def knowledge_context(
    context_id: Annotated[str, Query(min_length=1, max_length=120)],
    authorization: Annotated[str | None, Header()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> KnowledgeContextResponse:
    knowledge._authenticate(authorization)
    normalised = context_id.strip().lower()
    return KnowledgeContextResponse(
        context_id=normalised,
        notes=_context_notes(normalised, limit=limit),
    )
