from app.api.engineering_standards import _citation, _safe_filename, _snippet


def test_citation_prefers_reference_and_preserves_provenance() -> None:
    metadata = {
        "title": "Concrete structures",
        "authority": "Standards Australia",
        "reference": "AS 3600",
        "edition": "2018",
    }

    assert _citation(metadata, 42) == "AS 3600 · 2018 · Standards Australia · p. 42"


def test_citation_falls_back_to_title() -> None:
    metadata = {
        "title": "Technical specification",
        "authority": "Sydney Water",
        "reference": None,
        "edition": None,
    }

    assert _citation(metadata, 7) == "Technical specification · Sydney Water · p. 7"


def test_snippet_is_compact_and_query_centred() -> None:
    text = "A" * 200 + " minimum cover is 600 mm beneath the roadway " + "B" * 200
    snippet = _snippet(text, "minimum cover", radius=30)

    assert snippet is not None
    assert "minimum cover" in snippet
    assert snippet.startswith("…")
    assert snippet.endswith("…")


def test_safe_filename_removes_path_characters() -> None:
    assert _safe_filename("../AS:3600?.pdf") == "_AS_3600_.pdf"
