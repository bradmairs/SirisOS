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
