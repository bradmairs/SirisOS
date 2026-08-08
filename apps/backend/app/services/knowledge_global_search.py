from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

from app.api import knowledge
from app.services.knowledge_semantic_search import (
    KnowledgeSemanticSearch,
    SemanticKnowledgeDocument,
)


@dataclass(frozen=True)
class KnowledgeGlobalSearchHit:
    title: str
    subtitle: str
    path: str
    score: int
    strategy: str = "lexical"


semantic_search = KnowledgeSemanticSearch()


async def search_knowledge_notes(term: str, limit: int = 20) -> list[KnowledgeGlobalSearchHit]:
    needle = term.strip().lower()
    if not needle:
        return []

    lexical_scores: dict[str, int] = {}
    summaries: dict[str, knowledge.KnowledgeNoteSummary] = {}
    documents: list[SemanticKnowledgeDocument] = []

    for path in knowledge._markdown_files():
        try:
            text = knowledge._read_text(path)
            summary = knowledge._summary(path, text)
            stat = path.stat()
        except (OSError, HTTPException):
            continue

        summaries[summary.path] = summary
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
        lexical_scores[summary.path] = score

        documents.append(
            SemanticKnowledgeDocument(
                path=summary.path,
                title=summary.title,
                tags=tuple(summary.tags),
                text=text,
                cache_key=f"{summary.path}:{stat.st_mtime_ns}:{stat.st_size}",
            )
        )

    # Prefer recently modified notes when a very large vault is bounded by the
    # semantic max-note configuration. Deterministic lexical search still scans all notes.
    documents.sort(
        key=lambda item: summaries[item.path].modified_at,
        reverse=True,
    )
    semantic_hits = await semantic_search.rank(
        term,
        documents,
        limit=max(limit * 3, 30),
    )
    semantic_scores = {
        item.path: max(0, round(item.semantic_score * 50))
        for item in semantic_hits
    }

    ranked: list[KnowledgeGlobalSearchHit] = []
    candidate_paths = set(path for path, score in lexical_scores.items() if score > 0)
    candidate_paths.update(semantic_scores)
    for path in candidate_paths:
        summary = summaries.get(path)
        if summary is None:
            continue
        lexical_score = lexical_scores.get(path, 0)
        semantic_score = semantic_scores.get(path, 0)
        combined = lexical_score + semantic_score
        if combined <= 0:
            continue

        details: list[str] = [summary.path]
        if summary.tags:
            details.append(" ".join(f"#{tag}" for tag in summary.tags[:4]))
        strategy = "hybrid" if lexical_score > 0 and semantic_score > 0 else "semantic" if semantic_score > 0 else "lexical"
        if strategy == "semantic":
            details.append("semantic match")

        ranked.append(
            KnowledgeGlobalSearchHit(
                title=summary.title,
                subtitle=" · ".join(details),
                path=summary.path,
                score=combined,
                strategy=strategy,
            )
        )

    ranked.sort(key=lambda item: (-item.score, item.title.lower(), item.path.lower()))
    return ranked[:limit]
