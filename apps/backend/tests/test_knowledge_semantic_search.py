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
