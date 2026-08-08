from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from app.services.engineering_standards_evidence import EngineeringEvidence, evidence_from_hit
from app.services.engineering_standards_search import rank_pages

router = APIRouter(prefix="/api/v1/engineering/sirishydro", tags=["engineering"])
AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
LIBRARY_ROOT = Path(os.getenv("SIRISOS_STANDARDS_PATH", "/app/data/standards"))
RETRIEVAL_STRATEGY = "hybrid-lexical-civil-water-semantic-v1"


class SirisHydroEvidenceItem(BaseModel):
    document_id: str
    title: str
    authority: str
    reference: str | None = None
    edition: str | None = None
    page: int
    citation: str
    excerpt: str
    score: int


class SirisHydroEvidenceResponse(BaseModel):
    question: str
    sufficient_evidence: bool
    evidence: list[SirisHydroEvidenceItem]
    context_text: str
    guidance: str
    retrieval_strategy: str = RETRIEVAL_STRATEGY


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


def _citation(metadata: dict, page: int) -> str:
    identity = str(metadata.get("reference") or metadata.get("title") or "Standard")
    edition = str(metadata.get("edition") or "").strip()
    authority = str(metadata.get("authority") or "").strip()
    revision = int(metadata.get("revision") or 1)
    parts = [identity]
    if edition:
        parts.append(edition)
    if revision > 1:
        parts.append(f"library rev. {revision}")
    if authority:
        parts.append(authority)
    return f"{' · '.join(parts)} · p. {page}"


def _excerpt(text: str, max_chars: int = 1800) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars].rstrip() + "…"


def assemble_evidence(question: str, limit: int = 6) -> list[EngineeringEvidence]:
    LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
    evidence: list[EngineeringEvidence] = []

    for metadata_path in LIBRARY_ROOT.glob("*/metadata.json"):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        # Historical revisions remain directly retrievable for old citations,
        # but new SirisHydro answers should use only the active library view.
        if metadata.get("active") is False:
            continue
        if not metadata.get("indexed"):
            continue
        index_path = metadata_path.parent / "index.json"
        if not index_path.exists():
            continue
        try:
            pages = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(pages, list):
            continue

        for hit in rank_pages(pages, question, limit=min(4, limit)):
            if hit.page < 1:
                continue
            evidence.append(
                evidence_from_hit(
                    metadata=metadata,
                    page=hit.page,
                    citation=_citation(metadata, hit.page),
                    excerpt=_excerpt(hit.text),
                    score=hit.score,
                )
            )

    evidence.sort(key=lambda item: (-item.score, item.citation))
    deduped: list[EngineeringEvidence] = []
    seen: set[tuple[str, int]] = set()
    for item in evidence:
        key = (item.document_id, item.page)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def _context_text(question: str, evidence: list[EngineeringEvidence]) -> str:
    if not evidence:
        return ""
    blocks = [
        f"Question: {question}",
        f"Retrieval strategy: {RETRIEVAL_STRATEGY}",
        "",
        "Retrieved engineering evidence:",
    ]
    for index, item in enumerate(evidence, start=1):
        blocks.extend(["", f"[{index}] {item.citation}", item.excerpt])
    blocks.extend(
        [
            "",
            "Answering rule: source-supported claims must cite the evidence above. If the evidence does not establish a requirement, say so rather than inventing a clause or value.",
        ]
    )
    return "\n".join(blocks)


@router.get("/evidence", response_model=SirisHydroEvidenceResponse)
async def sirishydro_evidence(
    authorization: Annotated[str | None, Header()] = None,
    question: Annotated[str, Query(min_length=2, max_length=500)] = "",
    limit: Annotated[int, Query(ge=1, le=12)] = 6,
) -> SirisHydroEvidenceResponse:
    _authenticate(authorization)
    question_value = question.strip()
    if len(question_value) < 2:
        raise HTTPException(status_code=422, detail="Enter an engineering question to retrieve evidence.")

    evidence = assemble_evidence(question_value, limit=limit)
    sufficient = bool(evidence)
    guidance = (
        "Evidence found using local hybrid retrieval. Review the cited pages before relying on tables, figures, equations or layout-sensitive requirements."
        if sufficient
        else "The private standards library did not establish this question. Upload or index the relevant source rather than relying on an invented standards answer."
    )
    return SirisHydroEvidenceResponse(
        question=question_value,
        sufficient_evidence=sufficient,
        evidence=[SirisHydroEvidenceItem(**item.as_dict()) for item in evidence],
        context_text=_context_text(question_value, evidence),
        guidance=guidance,
        retrieval_strategy=RETRIEVAL_STRATEGY,
    )
