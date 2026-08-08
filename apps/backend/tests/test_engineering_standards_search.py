from app.services.engineering_standards_search import (
    query_terms,
    rank_pages,
    semantic_terms,
)


def test_query_terms_are_normalized_and_unique() -> None:
    assert query_terms("Minimum cover minimum PIPE") == ("minimum", "cover", "pipe")


def test_semantic_terms_expand_only_touched_domain_concepts() -> None:
    terms = semantic_terms("minimum pipe grade")

    assert "slope" in terms
    assert "gradient" in terms
    assert "conduit" in terms
    assert "least" in terms
    assert "buoyancy" not in terms


def test_rank_pages_prefers_exact_phrase_and_returns_multiple_pages() -> None:
    pages = [
        {"page": 1, "text": "Pipe cover requirements are described generally."},
        {"page": 2, "text": "The minimum cover under a roadway is specified here. Minimum cover applies."},
        {"page": 3, "text": "Minimum pipe depth and cover are discussed."},
    ]

    hits = rank_pages(pages, "minimum cover", limit=3)

    assert [hit.page for hit in hits] == [2, 3, 1]
    assert hits[0].score > hits[1].score
    assert hits[0].lexical_score > 0


def test_rank_pages_recovers_related_civil_water_terminology() -> None:
    pages = [
        {"page": 1, "text": "The conduit gradient shall not be flatter than the nominated value."},
        {"page": 2, "text": "Pump maintenance requirements are specified here."},
    ]

    hits = rank_pages(pages, "pipe slope", limit=2)

    assert [hit.page for hit in hits] == [1]
    assert hits[0].semantic_score > 0
    assert hits[0].lexical_score == 0


def test_exact_wording_still_beats_semantic_only_match() -> None:
    pages = [
        {"page": 1, "text": "The conduit gradient is specified for this reach."},
        {"page": 2, "text": "The minimum pipe slope is 0.5 percent for this example."},
    ]

    hits = rank_pages(pages, "pipe slope", limit=2)

    assert [hit.page for hit in hits] == [2, 1]
    assert hits[0].lexical_score > hits[1].lexical_score


def test_rank_pages_returns_no_hits_for_unmatched_query() -> None:
    assert rank_pages([{"page": 1, "text": "stormwater drainage"}], "earthquake", limit=5) == []
