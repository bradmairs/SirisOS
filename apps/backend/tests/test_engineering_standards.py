from app.api.engineering_standards import (
    _citation,
    _normalise_metadata,
    _safe_filename,
    _snippet,
)


def test_citation_prefers_reference_and_preserves_provenance() -> None:
    metadata = {
        "title": "Concrete structures",
        "authority": "Standards Australia",
        "reference": "AS 3600",
        "edition": "2018",
    }

    assert _citation(metadata, 42) == "AS 3600 · 2018 · Standards Australia · p. 42"


def test_citation_includes_library_revision_after_replacement() -> None:
    metadata = {
        "title": "Concrete structures",
        "authority": "Standards Australia",
        "reference": "AS 3600",
        "edition": "2018",
        "revision": 3,
    }

    assert _citation(metadata, 42) == (
        "AS 3600 · 2018 · library rev. 3 · Standards Australia · p. 42"
    )


def test_citation_falls_back_to_title() -> None:
    metadata = {
        "title": "Technical specification",
        "authority": "Sydney Water",
        "reference": None,
        "edition": None,
    }

    assert _citation(metadata, 7) == "Technical specification · Sydney Water · p. 7"


def test_legacy_metadata_defaults_to_active_revision_one() -> None:
    metadata = _normalise_metadata({"id": "abc", "indexed": True})

    assert metadata["active"] is True
    assert metadata["revision"] == 1
    assert metadata["supersedes_id"] is None
    assert metadata["superseded_by_id"] is None
    assert metadata["archived_at"] is None


def test_snippet_is_compact_and_query_centred() -> None:
    text = "A" * 200 + " minimum cover is 600 mm beneath the roadway " + "B" * 200
    snippet = _snippet(text, "minimum cover", radius=30)

    assert snippet is not None
    assert "minimum cover" in snippet
    assert snippet.startswith("…")
    assert snippet.endswith("…")


def test_safe_filename_removes_path_characters() -> None:
    assert _safe_filename("../AS:3600?.pdf") == "_AS_3600_.pdf"


def test_a_standard_has_a_topic_and_its_details_can_be_corrected(tmp_path, monkeypatch) -> None:
    """11.20: standards are filed under a topic, kept through a new revision, and changed without uploading again."""
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from app.api import engineering_standards as es
    from app.entrypoint import app
    from tests.test_hub import AUTH

    monkeypatch.setattr(es, "LIBRARY_ROOT", tmp_path)
    monkeypatch.setattr(es, "extract_standard_pages", lambda path: SimpleNamespace(
        pages=[{"page": 1, "text": "Design rainfall"}], indexed=True, extraction_method="native", ocr_attempted=False, ocr_error=None))
    c = TestClient(app, headers=AUTH)
    pdf = ("arr.pdf", b"%PDF-1.4 test", "application/pdf")
    made = c.post("/api/v1/engineering/standards", files={"file": pdf},
                  data={"title": "ARR Book 2", "authority": "Geoscience Australia", "category": "Hydrology and flooding"}).json()
    assert made["category"] == "Hydrology and flooding"
    hits = c.get("/api/v1/engineering/standards", params={"query": "hydrology"}).json()["hits"]
    assert hits and hits[0]["document"]["id"] == made["id"]                    # the topic is searchable
    changed = c.patch(f"/api/v1/engineering/standards/{made['id']}", json={"category": "Flooding", "edition": "2019 v4.2"}).json()
    assert changed["category"] == "Flooding" and changed["edition"] == "2019 v4.2" and changed["title"] == "ARR Book 2"
    newer = c.post(f"/api/v1/engineering/standards/{made['id']}/replace", files={"file": pdf}).json()
    assert newer["category"] == "Flooding" and newer["revision"] == 2         # a new revision keeps its topic
    assert c.patch(f"/api/v1/engineering/standards/{made['id']}", json={"title": ""}).status_code == 422


def test_an_id_that_isnt_one_of_ours_is_not_found(tmp_path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.api import engineering_standards as es
    from app.entrypoint import app
    from tests.test_hub import AUTH

    monkeypatch.setattr(es, "LIBRARY_ROOT", tmp_path)
    c = TestClient(app, headers=AUTH)
    for bad in ("..%2F..%2Fetc", "abc", "Z" * 32):
        assert c.patch(f"/api/v1/engineering/standards/{bad}", json={"category": "x"}).status_code == 404


def test_broken_characters_in_a_pdfs_text_dont_fail_the_upload(tmp_path, monkeypatch) -> None:
    """11.20.1: ARR Book 1's maths extracts as lone surrogates, which can't be written as UTF-8."""
    from types import SimpleNamespace

    from app.api import engineering_standards as es

    monkeypatch.setattr(es, "LIBRARY_ROOT", tmp_path)
    monkeypatch.setattr(es, "extract_standard_pages", lambda path: SimpleNamespace(
        pages=[{"page": 1, "text": "Q = \ud835 x"}], indexed=True, extraction_method="native", ocr_attempted=False, ocr_error=None))
    stored = es._store_document(filename="b.pdf", data=b"%PDF", title="T", authority="A", reference=None, edition=None)
    assert "Q = ? x" in (tmp_path / stored["id"] / "index.json").read_text(encoding="utf-8")

    def boom(path):
        raise RuntimeError("extraction failed")

    monkeypatch.setattr(es, "extract_standard_pages", boom)
    try:
        es._store_document(filename="c.pdf", data=b"%PDF", title="T", authority="A", reference=None, edition=None)
    except RuntimeError:
        pass
    assert [p.name for p in tmp_path.iterdir()] == [stored["id"]]   # the failed one left nothing behind
