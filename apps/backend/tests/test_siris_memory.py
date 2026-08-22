import asyncio

import jwt

from app.api import siris_memory
from app.services import siris_memory_service


def _token() -> str:
    return "Bearer " + jwt.encode(
        {"sub": siris_memory.AUTH_USERNAME, "iss": "sirisos-api"},
        siris_memory.JWT_SECRET,
        algorithm="HS256",
    )


def test_list_memory_requires_authentication(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(siris_memory, "MEMORY_PATH", tmp_path / "memory.json")
    try:
        asyncio.run(siris_memory.list_memory(None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 401
    else:
        raise AssertionError("Expected authentication failure")


def test_create_list_and_delete_memory(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(siris_memory, "MEMORY_PATH", tmp_path / "memory.json")
    authorization = _token()

    created = asyncio.run(
        siris_memory.create_memory(
            siris_memory.MemoryCreateRequest(
                memory_class="decision",
                content="Used Class 3 pipe on the Sydney Water rising main.",
                source="Project: Sydney Water rising main",
            ),
            authorization,
        )
    )
    assert created.memory_class == "decision"
    assert created.content == "Used Class 3 pipe on the Sydney Water rising main."
    assert created.source == "Project: Sydney Water rising main"
    assert siris_memory.MEMORY_PATH.exists()

    listed = asyncio.run(siris_memory.list_memory(authorization))
    assert [item.id for item in listed.memory] == [created.id]

    asyncio.run(siris_memory.delete_memory(created.id, authorization))
    listed_after = asyncio.run(siris_memory.list_memory(authorization))
    assert listed_after.memory == []


def test_create_memory_without_source_defaults_to_none(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(siris_memory, "MEMORY_PATH", tmp_path / "memory.json")
    authorization = _token()

    created = asyncio.run(
        siris_memory.create_memory(
            siris_memory.MemoryCreateRequest(memory_class="fact", content="Homelab runs on a Linux server."),
            authorization,
        )
    )
    assert created.source is None


def test_list_memory_filters_by_class(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(siris_memory, "MEMORY_PATH", tmp_path / "memory.json")
    authorization = _token()

    asyncio.run(
        siris_memory.create_memory(
            siris_memory.MemoryCreateRequest(memory_class="fact", content="Fact one"), authorization
        )
    )
    asyncio.run(
        siris_memory.create_memory(
            siris_memory.MemoryCreateRequest(memory_class="preference", content="Prefers Class 3 pipe"),
            authorization,
        )
    )

    facts_only = asyncio.run(siris_memory.list_memory(authorization, memory_class="fact"))
    assert len(facts_only.memory) == 1
    assert facts_only.memory[0].memory_class == "fact"


def test_delete_missing_memory_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(siris_memory, "MEMORY_PATH", tmp_path / "memory.json")
    try:
        asyncio.run(siris_memory.delete_memory("missing-id", authorization=_token()))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("Expected missing memory record rejection")


class _FakeChatClient:
    def __init__(self, response: str | None) -> None:
        self._response = response
        self.enabled = True

    async def complete(self, *, system: str, prompt: str) -> str | None:
        return self._response


def test_suggest_memory_route_returns_parsed_suggestions(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(siris_memory, "MEMORY_PATH", tmp_path / "memory.json")
    monkeypatch.setattr(
        siris_memory_service,
        "_default_chat_client",
        _FakeChatClient('[{"memory_class": "fact", "content": "Works as a civil engineer."}]'),
    )

    result = asyncio.run(
        siris_memory.suggest_memory(
            siris_memory.MemorySuggestRequest(
                user_message="I'm a civil engineer", assistant_message="Good to know."
            ),
            authorization=_token(),
        )
    )

    assert len(result.suggestions) == 1
    assert result.suggestions[0].content == "Works as a civil engineer."
    assert result.suggestions[0].memory_class == "fact"


def test_suggest_memory_route_returns_empty_when_ollama_disabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(siris_memory, "MEMORY_PATH", tmp_path / "memory.json")
    disabled = _FakeChatClient(None)
    disabled.enabled = False
    monkeypatch.setattr(siris_memory_service, "_default_chat_client", disabled)

    result = asyncio.run(
        siris_memory.suggest_memory(
            siris_memory.MemorySuggestRequest(user_message="hi", assistant_message="hello"),
            authorization=_token(),
        )
    )

    assert result.suggestions == []


def test_create_memory_rejects_invalid_memory_class() -> None:
    try:
        siris_memory.MemoryCreateRequest(memory_class="invalid-class", content="x")
    except Exception:
        pass
    else:
        raise AssertionError("Expected validation failure for an invalid memory_class")
