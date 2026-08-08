from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class EngineeringEvidence:
    document_id: str
    title: str
    authority: str
    reference: str | None
    edition: str | None
    page: int
    citation: str
    excerpt: str
    score: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def evidence_from_hit(
    *,
    metadata: dict,
    page: int,
    citation: str,
    excerpt: str,
    score: int,
) -> EngineeringEvidence:
    return EngineeringEvidence(
        document_id=str(metadata["id"]),
        title=str(metadata["title"]),
        authority=str(metadata["authority"]),
        reference=str(metadata["reference"]) if metadata.get("reference") else None,
        edition=str(metadata["edition"]) if metadata.get("edition") else None,
        page=page,
        citation=citation,
        excerpt=excerpt,
        score=score,
    )
