from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RankedTextHit:
    page: int
    text: str
    score: int
    lexical_score: int = 0
    semantic_score: int = 0


# Small, deterministic civil/water concept groups. These improve recall for
# common equivalent terminology without adding a cloud service or model
# dependency. Exact phrase/term matches always carry more weight.
_CONCEPT_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"grade", "slope", "gradient", "fall"}),
    frozenset({"cover", "depth", "burial", "embedment"}),
    frozenset({"buoyancy", "flotation", "uplift", "floatation"}),
    frozenset({"pit", "manhole", "chamber", "maintenancehole"}),
    frozenset({"detention", "storage", "basin", "pond", "attenuation"}),
    frozenset({"flow", "discharge", "capacity", "throughput"}),
    frozenset({"velocity", "speed"}),
    frozenset({"stormwater", "drainage", "runoff"}),
    frozenset({"pipe", "conduit", "pipeline", "drain"}),
    frozenset({"culvert", "crossing"}),
    frozenset({"headloss", "friction", "loss", "losses"}),
    frozenset({"pressure", "head"}),
    frozenset({"pump", "pumping"}),
    frozenset({"trench", "bedding", "embedment", "backfill"}),
    frozenset({"traffic", "vehicle", "loading", "load"}),
    frozenset({"sewer", "wastewater", "sanitary"}),
    frozenset({"watermain", "water", "pressuremain"}),
    frozenset({"minimum", "least", "min"}),
    frozenset({"maximum", "greatest", "max"}),
)


def query_terms(query: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            term for term in re.findall(r"[a-z0-9]+", query.lower()) if len(term) > 1
        )
    )


def semantic_terms(query: str) -> tuple[str, ...]:
    """Return deterministic domain-related terms for the query.

    Only concept groups touched by the original query are expanded. Original
    terms are excluded so semantic scoring cannot double-count lexical hits.
    """
    original = set(query_terms(query))
    expanded: list[str] = []
    for group in _CONCEPT_GROUPS:
        if original.intersection(group):
            expanded.extend(sorted(group - original))
    return tuple(dict.fromkeys(expanded))


def _score_page(text: str, query: str) -> tuple[int, int]:
    lowered = text.lower()
    phrase = query.strip().lower()
    terms = query_terms(query)

    lexical_score = 0
    phrase_count = lowered.count(phrase)
    if phrase_count:
        lexical_score += phrase_count * 24
    matched_original_terms = 0
    for term in terms:
        count = lowered.count(term)
        if count:
            matched_original_terms += 1
            lexical_score += min(count, 10) * 3
    if terms and matched_original_terms == len(terms):
        lexical_score += 8

    semantic_score = 0
    matched_semantic_terms = 0
    for term in semantic_terms(query):
        count = lowered.count(term)
        if count:
            matched_semantic_terms += 1
            semantic_score += min(count, 6)
    if matched_semantic_terms >= 2:
        semantic_score += 2

    return lexical_score, semantic_score


def rank_pages(pages: list[dict], query: str, limit: int = 5) -> list[RankedTextHit]:
    phrase = query.strip().lower()
    terms = query_terms(query)
    if not phrase or not terms:
        return []

    hits: list[RankedTextHit] = []
    for item in pages:
        text = str(item.get("text") or "")
        lexical_score, semantic_score = _score_page(text, query)
        score = lexical_score + semantic_score
        if score:
            hits.append(
                RankedTextHit(
                    page=int(item.get("page") or 0),
                    text=text,
                    score=score,
                    lexical_score=lexical_score,
                    semantic_score=semantic_score,
                )
            )

    # Exact lexical evidence remains the primary ordering signal. Semantic
    # expansion breaks ties and recovers related terminology when exact wording
    # is absent, while page number keeps results deterministic.
    hits.sort(
        key=lambda hit: (
            -hit.score,
            -hit.lexical_score,
            -hit.semantic_score,
            hit.page,
        )
    )
    return hits[:limit]
