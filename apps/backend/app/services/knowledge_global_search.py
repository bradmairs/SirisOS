from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

from app.api import knowledge


@dataclass(frozen=True)
class KnowledgeGlobalSearchHit:
    title: str
    subtitle: str
    path: str
    score: int


def search_knowledge_notes(term: str, limit: int = 20) -> list[KnowledgeGlobalSearchHit]:
    needle = term.strip().lower()
    if not needle:
        return []

    scored: list[KnowledgeGlobalSearchHit] = []
    for path in knowledge._markdown_files():
        try:
            text = knowledge._read_text(path)
            summary = knowledge._summary(path, text)
        except (OSError, HTTPException):
            continue

        title = summary.title.lower()
        relative = summary.path.lower()
        body = text.lower()
        tags = " ".join(summary.tags).lower()
        score = 0
        if needle == title:
            score += 120
        elif needle in title:
            score += 80
        if needle in relative:
            score += 40
        if needle in tags:
            score += 30
        score += min(body.count(needle), 10) * 5
        if score <= 0:
            continue

        details: list[str] = [summary.path]
        if summary.tags:
            details.append(" ".join(f"#{tag}" for tag in summary.tags[:4]))
        scored.append(
            KnowledgeGlobalSearchHit(
                title=summary.title,
                subtitle=" · ".join(details),
                path=summary.path,
                score=score,
            )
        )

    scored.sort(key=lambda item: (-item.score, item.title.lower()))
    return scored[:limit]
