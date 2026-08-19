import asyncio

import httpx

from app.services.ollama_service import OllamaChatClient


def test_disabled_without_url_or_model() -> None:
    client = OllamaChatClient()
    client.ollama_url = ""
    client.model = ""
    assert client.enabled is False
    assert asyncio.run(client.complete(system="s", prompt="p")) is None


def test_disabled_returns_none_for_blank_prompt() -> None:
    client = OllamaChatClient()
    client.ollama_url = "http://ollama"
    client.model = "chat-model"
    assert asyncio.run(client.complete(system="s", prompt="   ")) is None


def test_complete_returns_trimmed_content_from_chat_response() -> None:
    client = OllamaChatClient()
    client.ollama_url = "http://ollama"
    client.model = "chat-model"

    async def fake_chat(*, system: str, prompt: str) -> str | None:
        assert system == "s"
        assert prompt == "p"
        return "  Answer text.  ".strip()

    client._chat = fake_chat  # type: ignore[method-assign]
    assert asyncio.run(client.complete(system="s", prompt="p")) == "Answer text."


def test_complete_fails_open_on_network_error() -> None:
    client = OllamaChatClient()
    client.ollama_url = "http://ollama"
    client.model = "chat-model"

    async def failing_chat(*, system: str, prompt: str) -> str | None:
        raise httpx.ConnectError("refused")

    client._chat = failing_chat  # type: ignore[method-assign]
    assert asyncio.run(client.complete(system="s", prompt="p")) is None


def test_complete_fails_open_on_malformed_response() -> None:
    client = OllamaChatClient()
    client.ollama_url = "http://ollama"
    client.model = "chat-model"

    async def malformed_chat(*, system: str, prompt: str) -> str | None:
        raise ValueError("Ollama returned an invalid chat response.")

    client._chat = malformed_chat  # type: ignore[method-assign]
    assert asyncio.run(client.complete(system="s", prompt="p")) is None


def test_status_reports_not_configured_without_url_or_model() -> None:
    client = OllamaChatClient()
    client.ollama_url = ""
    client.model = ""

    status = asyncio.run(client.status())

    assert status.configured is False
    assert status.reachable is False
    assert status.model_available is False


def test_status_reports_reachable_and_model_available() -> None:
    client = OllamaChatClient()
    client.ollama_url = "http://ollama"
    client.model = "llama3.1"

    async def fake_list_models() -> list[str]:
        return ["llama3.1:latest", "mistral:latest"]

    client._list_models = fake_list_models  # type: ignore[method-assign]
    status = asyncio.run(client.status())

    assert status.configured is True
    assert status.reachable is True
    assert status.model == "llama3.1"
    assert status.model_available is True


def test_status_reports_configured_model_missing_from_server() -> None:
    client = OllamaChatClient()
    client.ollama_url = "http://ollama"
    client.model = "llama3.1"

    async def fake_list_models() -> list[str]:
        return ["mistral:latest"]

    client._list_models = fake_list_models  # type: ignore[method-assign]
    status = asyncio.run(client.status())

    assert status.reachable is True
    assert status.model_available is False


def test_chat_disabled_without_url_or_model() -> None:
    client = OllamaChatClient()
    client.ollama_url = ""
    client.model = ""
    assert asyncio.run(client.chat(messages=[{"role": "user", "content": "hi"}])) is None


def test_chat_disabled_for_empty_messages() -> None:
    client = OllamaChatClient()
    client.ollama_url = "http://ollama"
    client.model = "chat-model"
    assert asyncio.run(client.chat(messages=[])) is None


def test_chat_fails_open_on_network_error() -> None:
    client = OllamaChatClient()
    client.ollama_url = "http://ollama"
    client.model = "chat-model"

    async def failing(*, messages, tools=None):
        raise httpx.ConnectError("refused")

    client._chat_with_tools = failing  # type: ignore[method-assign]
    assert asyncio.run(client.chat(messages=[{"role": "user", "content": "hi"}])) is None


def test_chat_parses_content_response_with_no_tool_calls() -> None:
    client = OllamaChatClient()
    client.ollama_url = "http://ollama"
    client.model = "chat-model"

    class _FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {"message": {"role": "assistant", "content": "  Your strength score is 94.  "}}

    async def fake_post(self, url, json):  # noqa: A002 - matches httpx.AsyncClient.post signature
        return _FakeResponse()

    import httpx as httpx_module

    original_post = httpx_module.AsyncClient.post
    httpx_module.AsyncClient.post = fake_post  # type: ignore[method-assign]
    try:
        result = asyncio.run(client.chat(messages=[{"role": "user", "content": "how strong am I"}]))
    finally:
        httpx_module.AsyncClient.post = original_post  # type: ignore[method-assign]

    assert result is not None
    assert result.content == "Your strength score is 94."
    assert result.tool_calls == []


def test_chat_parses_tool_calls_from_response() -> None:
    client = OllamaChatClient()
    client.ollama_url = "http://ollama"
    client.model = "chat-model"

    class _FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"function": {"name": "get_strength_score", "arguments": {}}},
                        {"function": {"name": "get_recent_runs", "arguments": {"limit": 3}}},
                        {"not_a_function": True},
                        {"function": {"arguments": {}}},  # missing name -- skipped
                    ],
                }
            }

    async def fake_post(self, url, json):
        return _FakeResponse()

    import httpx as httpx_module

    original_post = httpx_module.AsyncClient.post
    httpx_module.AsyncClient.post = fake_post  # type: ignore[method-assign]
    try:
        result = asyncio.run(
            client.chat(messages=[{"role": "user", "content": "how strong am I"}], tools=[{"type": "function"}])
        )
    finally:
        httpx_module.AsyncClient.post = original_post  # type: ignore[method-assign]

    assert result is not None
    assert result.content is None
    assert len(result.tool_calls) == 2
    assert result.tool_calls[0].name == "get_strength_score"
    assert result.tool_calls[0].arguments == {}
    assert result.tool_calls[1].name == "get_recent_runs"
    assert result.tool_calls[1].arguments == {"limit": 3}


def test_status_reports_unreachable_on_network_error() -> None:
    client = OllamaChatClient()
    client.ollama_url = "http://ollama"
    client.model = "llama3.1"

    async def failing_list_models() -> list[str]:
        raise httpx.ConnectError("refused")

    client._list_models = failing_list_models  # type: ignore[method-assign]
    status = asyncio.run(client.status())

    assert status.configured is True
    assert status.reachable is False
    assert status.model_available is False
