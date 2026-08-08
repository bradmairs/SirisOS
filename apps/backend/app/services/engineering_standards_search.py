from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RankedTextHit:
    page: int
    text: str
    score: int


def query_terms(query: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(term for term in re.findall(r"[a-z0-9]+", query.lower()) if len(term) > 1))


def rank_pages(pages: list[dict], query: str, limit: int = 5) -> list[RankedTextHit]:
    phrase = query.strip().lower()
    terms = query_terms(query)
    if not phrase or not terms:
        return []

    hits: list[RankedTextHit] = []
    for item in pages:
        text = str(item.get("text") or "")
        lowered = text.lower()
        score = 0
        phrase_count = lowered.count(phrase)
        if phrase_count:
            score += phrase_count * 20
        for term in terms:
            score += min(lowered.count(term), 10) * 2
        if score:
            hits.append(
                RankedTextHit(
                    page=int(item.get("page") or 0),
                    text=text,
                    score=score,
                )
            )

    hits.sort(key=lambda hit: (-hit.score, hit.page))
    return hits[:limit]
