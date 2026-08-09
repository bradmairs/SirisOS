from __future__ import annotations

import os

import httpx


class OllamaChatClient:
    """Optional local chat completion backed by a directly-connected Ollama server.

    Fail-open: disabled configuration, network errors and malformed responses all
    return None so callers can fall back to their existing deterministic behaviour
    (see ADR 057 and the sibling embeddings client in knowledge_semantic_search.py).
    """

    def __init__(self) -> None:
        self.ollama_url = os.getenv("OLLAMA_URL", "").strip().rstrip("/")
        self.model = os.getenv("SIRISOS_OLLAMA_CHAT_MODEL", "").strip()
        self.timeout_seconds = float(os.getenv("SIRISOS_OLLAMA_CHAT_TIMEOUT_SECONDS", "30"))

    @property
    def enabled(self) -> bool:
        return bool(self.ollama_url and self.model)

    async def complete(self, *, system: str, prompt: str) -> str | None:
        if not self.enabled or not prompt.strip():
            return None
        try:
            return await self._chat(system=system, prompt=prompt)
        except (httpx.HTTPError, ValueError, KeyError):
            return None

    async def _chat(self, *, system: str, prompt: str) -> str | None:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                },
            )
            response.raise_for_status()
            payload = response.json()
        message = payload.get("message")
        if not isinstance(message, dict):
            raise ValueError("Ollama returned an invalid chat response.")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            return None
        return content.strip()


chat_client = OllamaChatClient()
