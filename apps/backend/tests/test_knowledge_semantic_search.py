import asyncio

from app.services.knowledge_semantic_search import (
    KnowledgeSemanticSearch,
    SemanticKnowledgeDocument,
    cosine_similarity,
)


def test_cosine_similarity_prefers_aligned_vectors() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_semantic_search_is_disabled_without_model_or_endpoint() -> None:
    service = KnowledgeSemanticSearch()
    service.ollama_url = ""
    service.model = ""
    documents = [
        SemanticKnowledgeDocument(
            path="Hydraulics.md",
            title="Hydraulics",
            tags=("water",),
            text="Pipe flow and headloss notes.",
            cache_key="one",
        )
    ]

    assert asyncio.run(service.rank("pressure loss", documents, limit=10)) == []


def test_semantic_search_can_return_note_without_lexical_overlap() -> None:
    service = KnowledgeSemanticSearch()
    service.ollama_url = "http://ollama"
    service.model = "embedding-model"
    documents = [
        SemanticKnowledgeDocument(
            path="Hydraulics.md",
            title="Hydraulics",
            tags=("water",),
            text="Friction effects in a closed conduit.",
            cache_key="hydraulics",
        ),
        SemanticKnowledgeDocument(
            path="Gardening.md",
            title="Gardening",
            tags=("home",),
            text="Vegetable garden notes.",
            cache_key="gardening",
        ),
    ]

    async def fake_embed(inputs: list[str]) -> list[list[float]]:
        if len(inputs) == 1:
            return [[1.0, 0.0]]
        return [[1.0, 0.0], [0.0, 1.0]]

    service._embed = fake_embed  # type: ignore[method-assign]
    hits = asyncio.run(service.rank("pressure loss", documents, limit=10))

    assert hits[0].path == "Hydraulics.md"
    assert hits[0].semantic_score == 1.0
