import asyncio
import json

import jwt

from app.api import sirishydro


def _token() -> str:
    return "Bearer " + jwt.encode(
        {"sub": sirishydro.AUTH_USERNAME, "iss": "sirisos-api"},
        sirishydro.JWT_SECRET,
        algorithm="HS256",
    )


def _write_document(
    root,
    document_id,
    *,
    title,
    authority,
    reference,
    edition,
    pages,
    active=True,
    revision=1,
):
    directory = root / document_id
    directory.mkdir(parents=True)
    metadata = {
        "id": document_id,
        "title": title,
        "authority": authority,
        "reference": reference,
        "edition": edition,
        "filename": f"{document_id}.pdf",
        "uploaded_at": "2026-08-08T00:00:00+00:00",
        "pages": len(pages),
        "indexed": True,
        "active": active,
        "revision": revision,
    }
    (directory / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (directory / "index.json").write_text(
        json.dumps(
            [
                {"page": index + 1, "text": text}
                for index, text in enumerate(pages)
            ]
        ),
        encoding="utf-8",
    )


def test_assemble_evidence_ranks_and_preserves_citations(tmp_path, monkeypatch):
    monkeypatch.setattr(sirishydro, "LIBRARY_ROOT", tmp_path)
    _write_document(
        tmp_path,
        "as3725",
        title="Loads on buried concrete pipes",
        authority="Standards Australia",
        reference="AS/NZS 3725",
        edition="2007",
        pages=[
            "General introduction.",
            "Minimum cover beneath road traffic depends on installation and design loading. minimum cover road traffic.",
        ],
    )
    _write_document(
        tmp_path,
        "other",
        title="Other specification",
        authority="Example Authority",
        reference="SPEC 1",
        edition="2024",
        pages=["This page discusses landscaping only."],
    )

    evidence = sirishydro.assemble_evidence("minimum cover road traffic", limit=4)

    assert evidence
    assert evidence[0].document_id == "as3725"
    assert evidence[0].page == 2
    assert evidence[0].citation == "AS/NZS 3725 · 2007 · Standards Australia · p. 2"
    assert "minimum cover" in evidence[0].excerpt.lower()


def test_assemble_evidence_can_recover_semantically_related_wording(tmp_path, monkeypatch):
    monkeypatch.setattr(sirishydro, "LIBRARY_ROOT", tmp_path)
    _write_document(
        tmp_path,
        "drainage",
        title="Drainage specification",
        authority="Example Authority",
        reference="DRAIN 1",
        edition="Rev B",
        pages=["The conduit gradient shall be no flatter than the nominated design value."],
    )

    evidence = sirishydro.assemble_evidence("pipe slope", limit=3)

    assert evidence
    assert evidence[0].document_id == "drainage"
    assert evidence[0].page == 1


def test_assemble_evidence_ignores_archived_or_superseded_revisions(tmp_path, monkeypatch):
    monkeypatch.setattr(sirishydro, "LIBRARY_ROOT", tmp_path)
    _write_document(
        tmp_path,
        "old",
        title="Old drainage standard",
        authority="Example Authority",
        reference="SPEC 3",
        edition="2020",
        pages=["Minimum pipe slope is 1 percent."],
        active=False,
        revision=1,
    )
    _write_document(
        tmp_path,
        "current",
        title="Current drainage standard",
        authority="Example Authority",
        reference="SPEC 3",
        edition="2026",
        pages=["Minimum pipe slope is 0.5 percent."],
        active=True,
        revision=2,
    )

    evidence = sirishydro.assemble_evidence("minimum pipe slope", limit=3)

    assert evidence
    assert [item.document_id for item in evidence] == ["current"]
    assert "library rev. 2" in evidence[0].citation


def test_assemble_evidence_returns_empty_when_library_does_not_support_question(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(sirishydro, "LIBRARY_ROOT", tmp_path)
    _write_document(
        tmp_path,
        "spec",
        title="Drainage specification",
        authority="Example Authority",
        reference="SPEC 2",
        edition=None,
        pages=["Pipe bedding requirements only."],
    )

    assert sirishydro.assemble_evidence("earthquake bridge bearings", limit=6) == []


def test_context_text_contains_source_strategy_and_non_invention_rule(tmp_path, monkeypatch):
    monkeypatch.setattr(sirishydro, "LIBRARY_ROOT", tmp_path)
    _write_document(
        tmp_path,
        "spec",
        title="Drainage specification",
        authority="Sydney Water",
        reference="DSPEC",
        edition="Rev A",
        pages=["Buoyancy shall be considered where groundwater can submerge the structure."],
    )

    evidence = sirishydro.assemble_evidence("buoyancy groundwater", limit=3)
    context = sirishydro._context_text("When is buoyancy considered?", evidence)

    assert "DSPEC · Rev A · Sydney Water · p. 1" in context
    assert sirishydro.RETRIEVAL_STRATEGY in context
    assert "must cite the evidence" in context
    assert "rather than inventing" in context


def test_evidence_endpoint_has_no_synthesized_answer_when_ollama_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(sirishydro, "LIBRARY_ROOT", tmp_path)
    _write_document(
        tmp_path,
        "spec",
        title="Drainage specification",
        authority="Sydney Water",
        reference="DSPEC",
        edition="Rev A",
        pages=["Buoyancy shall be considered where groundwater can submerge the structure."],
    )

    response = asyncio.run(
        sirishydro.sirishydro_evidence(authorization=_token(), question="buoyancy groundwater", limit=6)
    )

    assert response.sufficient_evidence is True
    assert response.synthesized_answer is None


def test_evidence_endpoint_includes_synthesized_answer_when_ollama_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(sirishydro, "LIBRARY_ROOT", tmp_path)
    _write_document(
        tmp_path,
        "spec",
        title="Drainage specification",
        authority="Sydney Water",
        reference="DSPEC",
        edition="Rev A",
        pages=["Buoyancy shall be considered where groundwater can submerge the structure."],
    )

    async def fake_complete(*, system: str, prompt: str) -> str | None:
        assert system == sirishydro.SYNTHESIS_SYSTEM_PROMPT
        assert "DSPEC" in prompt
        return "Buoyancy must be considered [1]."

    monkeypatch.setattr(sirishydro.chat_client, "complete", fake_complete)

    response = asyncio.run(
        sirishydro.sirishydro_evidence(authorization=_token(), question="buoyancy groundwater", limit=6)
    )

    assert response.synthesized_answer == "Buoyancy must be considered [1]."


def test_evidence_endpoint_skips_synthesis_when_evidence_insufficient(tmp_path, monkeypatch):
    monkeypatch.setattr(sirishydro, "LIBRARY_ROOT", tmp_path)

    async def fail_if_called(*, system: str, prompt: str) -> str | None:
        raise AssertionError("Synthesis must not be attempted without evidence.")

    monkeypatch.setattr(sirishydro.chat_client, "complete", fail_if_called)

    response = asyncio.run(
        sirishydro.sirishydro_evidence(authorization=_token(), question="earthquake bridge bearings", limit=6)
    )

    assert response.sufficient_evidence is False
    assert response.synthesized_answer is None
