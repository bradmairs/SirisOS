import asyncio
from pathlib import Path

from app.services.siris_memory_service import SirisMemoryService


def _service(tmp_path: Path, chat_client=None) -> SirisMemoryService:
    return SirisMemoryService(memory_path=tmp_path / "memory.json", chat_client=chat_client)


class _FakeChatClient:
    def __init__(self, response: str | None, *, enabled: bool = True) -> None:
        self._response = response
        self.enabled = enabled
        self.calls: list[dict] = []

    async def complete(self, *, system: str, prompt: str) -> str | None:
        self.calls.append({"system": system, "prompt": prompt})
        return self._response


class _FailingChatClient:
    enabled = True

    async def complete(self, *, system: str, prompt: str) -> str | None:
        raise RuntimeError("Ollama unreachable")


def test_create_list_and_delete_memory(tmp_path: Path) -> None:
    service = _service(tmp_path)

    created = service.create_memory(memory_class="fact", content="Works as a civil engineer.")
    assert (tmp_path / "memory.json").exists()

    listed = service.list_memory()
    assert [item.id for item in listed] == [created.id]

    service.delete_memory(created.id)
    assert service.list_memory() == []


def test_suggest_returns_empty_when_ollama_disabled(tmp_path: Path) -> None:
    service = _service(tmp_path, chat_client=_FakeChatClient(None, enabled=False))

    result = asyncio.run(service.suggest(user_message="hi", assistant_message="hello"))

    assert result == []


def test_suggest_fails_open_on_ollama_error(tmp_path: Path) -> None:
    service = _service(tmp_path, chat_client=_FailingChatClient())

    result = asyncio.run(service.suggest(user_message="hi", assistant_message="hello"))

    assert result == []


def test_suggest_fails_open_on_malformed_json(tmp_path: Path) -> None:
    service = _service(tmp_path, chat_client=_FakeChatClient("not json at all"))

    result = asyncio.run(service.suggest(user_message="hi", assistant_message="hello"))

    assert result == []


def test_suggest_parses_valid_extraction(tmp_path: Path) -> None:
    response = (
        '[{"memory_class": "fact", "content": "Works as a civil engineer."}, '
        '{"memory_class": "fact", "content": "Their NAS is named \\"vault\\"."}]'
    )
    service = _service(tmp_path, chat_client=_FakeChatClient(response))

    result = asyncio.run(
        service.suggest(
            user_message="I'm a civil engineer and my NAS is called vault",
            assistant_message="Good to know.",
        )
    )

    assert [item.content for item in result] == [
        "Works as a civil engineer.",
        'Their NAS is named "vault".',
    ]
    assert all(item.memory_class == "fact" for item in result)


def test_suggest_returns_empty_list_when_nothing_memory_worthy(tmp_path: Path) -> None:
    service = _service(tmp_path, chat_client=_FakeChatClient("[]"))

    result = asyncio.run(service.suggest(user_message="how strong am I?", assistant_message="94."))

    assert result == []


def test_suggest_rejects_non_suggestable_memory_classes(tmp_path: Path) -> None:
    response = '[{"memory_class": "episode", "content": "Had a long chat about pipes."}]'
    service = _service(tmp_path, chat_client=_FakeChatClient(response))

    result = asyncio.run(service.suggest(user_message="hi", assistant_message="hello"))

    assert result == []


def test_suggest_drops_items_missing_required_fields(tmp_path: Path) -> None:
    response = '[{"memory_class": "fact"}, {"content": "no class given"}, "not even a dict"]'
    service = _service(tmp_path, chat_client=_FakeChatClient(response))

    result = asyncio.run(service.suggest(user_message="hi", assistant_message="hello"))

    assert result == []


def test_suggest_caps_at_three_items(tmp_path: Path) -> None:
    items = ", ".join(f'{{"memory_class": "fact", "content": "Fact {i}"}}' for i in range(5))
    service = _service(tmp_path, chat_client=_FakeChatClient(f"[{items}]"))

    result = asyncio.run(service.suggest(user_message="hi", assistant_message="hello"))

    assert len(result) == 3


def test_suggest_dedups_against_existing_memory(tmp_path: Path) -> None:
    response = (
        '[{"memory_class": "fact", "content": "Works as a civil engineer."}, '
        '{"memory_class": "fact", "content": "New fact never seen before."}]'
    )
    service = _service(tmp_path, chat_client=_FakeChatClient(response))
    service.create_memory(memory_class="fact", content="works as a civil engineer.")  # different casing

    result = asyncio.run(service.suggest(user_message="hi", assistant_message="hello"))

    assert [item.content for item in result] == ["New fact never seen before."]
