from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Iterable

import httpx


@dataclass(frozen=True)
class SemanticKnowledgeDocument:
    path: str
    title: str
    tags: tuple[str, ...]
    text: str
    cache_key: str


@dataclass(frozen=True)
class SemanticKnowledgeHit:
    path: str
    semantic_score: float


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


class KnowledgeSemanticSearch:
    """Optional local semantic ranking backed by Ollama embeddings.

    The service is deliberately fail-open: configuration/network/model failures return
    no semantic hits so callers can preserve deterministic lexical search as the
    authoritative fallback.
    """

    def __init__(self) -> None:
        self.ollama_url = os.getenv("OLLAMA_URL", "").strip().rstrip("/")
        self.model = os.getenv("SIRISOS_KNOWLEDGE_EMBEDDING_MODEL", "").strip()
        self.timeout_seconds = float(os.getenv("SIRISOS_KNOWLEDGE_SEMANTIC_TIMEOUT_SECONDS", "20"))
        self.max_notes = max(1, int(os.getenv("SIRISOS_KNOWLEDGE_SEMANTIC_MAX_NOTES", "500")))
        self._cache: dict[str, list[float]] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.ollama_url and self.model)

    async def rank(
        self,
        query: str,
        documents: Iterable[SemanticKnowledgeDocument],
        *,
        limit: int,
    ) -> list[SemanticKnowledgeHit]:
        query_value = query.strip()
        if not self.enabled or not query_value:
            return []

        values = list(documents)[: self.max_notes]
        if not values:
            return []

        try:
            query_embedding = (await self._embed([query_value]))[0]
            missing = [item for item in values if item.cache_key not in self._cache]
            if missing:
                texts = [self._embedding_text(item) for item in missing]
                embeddings = await self._embed(texts)
                for item, embedding in zip(missing, embeddings, strict=True):
                    self._cache[item.cache_key] = embedding

            ranked = [
                SemanticKnowledgeHit(
                    path=item.path,
                    semantic_score=cosine_similarity(query_embedding, self._cache[item.cache_key]),
                )
                for item in values
                if item.cache_key in self._cache
            ]
        except (httpx.HTTPError, ValueError, KeyError, IndexError):
            return []

        ranked.sort(key=lambda item: (-item.semantic_score, item.path.lower()))
        return [item for item in ranked if item.semantic_score > 0][:limit]

    async def _embed(self, inputs: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.ollama_url}/api/embed",
                json={"model": self.model, "input": inputs, "truncate": True},
            )
            response.raise_for_status()
            payload = response.json()
        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(inputs):
            raise ValueError("Ollama returned an invalid embeddings response.")
        return [[float(value) for value in embedding] for embedding in embeddings]

    @staticmethod
    def _embedding_text(item: SemanticKnowledgeDocument) -> str:
        tags = " ".join(f"#{tag}" for tag in item.tags)
        return f"Title: {item.title}\nPath: {item.path}\nTags: {tags}\n\n{item.text[:12000]}"
