from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass(frozen=True)
class OllamaStatus:
    configured: bool
    reachable: bool
    model: str | None
    model_available: bool


@dataclass(frozen=True)
class OllamaToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class OllamaChatResult:
    content: str | None
    tool_calls: list[OllamaToolCall] = field(default_factory=list)


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
        model = await self._resolve_model()
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": model,
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

    async def chat(
        self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> OllamaChatResult | None:
        """Multi-turn chat with optional tool/function-calling support, for an
        agent loop (see SirisAgentService) rather than the single system+prompt
        rephrase `complete()` serves. Same fail-open contract: disabled
        configuration, network errors and malformed responses all return None."""
        if not self.enabled or not messages:
            return None
        try:
            return await self._chat_with_tools(messages=messages, tools=tools)
        except (httpx.HTTPError, ValueError, KeyError):
            return None

    async def _chat_with_tools(
        self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> OllamaChatResult:
        model = await self._resolve_model()
        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": False}
        if tools:
            payload["tools"] = tools
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(f"{self.ollama_url}/api/chat", json=payload)
            response.raise_for_status()
            payload_response = response.json()
        message = payload_response.get("message")
        if not isinstance(message, dict):
            raise ValueError("Ollama returned an invalid chat response.")
        content = message.get("content")
        tool_calls: list[OllamaToolCall] = []
        for item in message.get("tool_calls") or []:
            if not isinstance(item, dict):
                continue
            function = item.get("function")
            if not isinstance(function, dict):
                continue
            name = function.get("name")
            if not isinstance(name, str) or not name:
                continue
            arguments = function.get("arguments")
            tool_calls.append(
                OllamaToolCall(name=name, arguments=arguments if isinstance(arguments, dict) else {})
            )
        return OllamaChatResult(
            content=content.strip() if isinstance(content, str) and content.strip() else None,
            tool_calls=tool_calls,
        )

    async def status(self) -> OllamaStatus:
        model = self.model or None
        if not self.enabled:
            return OllamaStatus(configured=False, reachable=False, model=model, model_available=False)
        try:
            available = await self._list_models()
        except (httpx.HTTPError, ValueError, KeyError):
            return OllamaStatus(configured=True, reachable=False, model=model, model_available=False)
        model_available = any(self._matches_configured_model(candidate) for candidate in available)
        return OllamaStatus(configured=True, reachable=True, model=model, model_available=model_available)

    async def _list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(f"{self.ollama_url}/api/tags")
            response.raise_for_status()
            payload = response.json()
        models = payload.get("models")
        if not isinstance(models, list):
            raise ValueError("Ollama returned an invalid tags response.")
        return [str(item["name"]) for item in models if isinstance(item, dict) and item.get("name")]

    def _matches_configured_model(self, candidate: str) -> bool:
        return candidate == self.model or candidate.split(":")[0] == self.model

    async def _resolve_model(self) -> str:
        """SIRISOS_OLLAMA_CHAT_MODEL is deliberately allowed to be configured
        without a tag (e.g. "llama3.1"), and status()'s model_available check
        already matches that leniently against whatever's actually pulled
        (e.g. "llama3.1:8b"). But Ollama's own /api/chat has no such leniency
        -- a bare model name is treated as an implicit ":latest", and if
        nothing is pulled under that exact tag, every real chat call 404s
        even though status() reports the model as available. Found live
        against a real deployment (llama3.1:8b pulled, SIRISOS_OLLAMA_CHAT_MODEL
        left as "llama3.1"): status() correctly said available, every chat
        request instantly failed. Resolves to the real matching tag before
        every chat call; falls back to the configured name unchanged if the
        tags list can't be fetched, so a genuinely wrong/unpulled model still
        surfaces its own real error rather than being silently masked."""
        try:
            available = await self._list_models()
        except (httpx.HTTPError, ValueError, KeyError):
            return self.model
        return next((candidate for candidate in available if self._matches_configured_model(candidate)), self.model)


chat_client = OllamaChatClient()
