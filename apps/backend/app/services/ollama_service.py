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
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "stream": False}
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
        model_available = any(
            candidate == self.model or candidate.split(":")[0] == self.model for candidate in available
        )
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


chat_client = OllamaChatClient()
