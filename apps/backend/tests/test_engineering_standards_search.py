from app.services.engineering_standards_search import query_terms, rank_pages


def test_query_terms_are_normalized_and_unique() -> None:
    assert query_terms("Minimum cover minimum PIPE") == ("minimum", "cover", "pipe")


def test_rank_pages_prefers_exact_phrase_and_returns_multiple_pages() -> None:
    pages = [
        {"page": 1, "text": "Pipe cover requirements are described generally."},
        {"page": 2, "text": "The minimum cover under a roadway is specified here. Minimum cover applies."},
        {"page": 3, "text": "Minimum pipe depth and cover are discussed."},
    ]

    hits = rank_pages(pages, "minimum cover", limit=3)

    assert [hit.page for hit in hits] == [2, 3, 1]
    assert hits[0].score > hits[1].score


def test_rank_pages_returns_no_hits_for_unmatched_query() -> None:
    assert rank_pages([{"page": 1, "text": "stormwater drainage"}], "earthquake", limit=5) == []
