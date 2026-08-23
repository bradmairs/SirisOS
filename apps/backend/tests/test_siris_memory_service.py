import asyncio
import json
from pathlib import Path

import pytest

from app.services.project_service import ProjectService
from app.services.siris_memory_service import (
    MemorySourceNotFoundError,
    SirisMemoryService,
)


def _service(tmp_path: Path, chat_client=None, project_service=None) -> SirisMemoryService:
    return SirisMemoryService(
        memory_path=tmp_path / "memory.json", chat_client=chat_client, project_service=project_service
    )


def _project_service(tmp_path: Path) -> ProjectService:
    return ProjectService(
        projects_path=tmp_path / "projects.json", project_context_path=tmp_path / "project-context.json"
    )


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


def test_create_memory_with_no_source_stores_none(tmp_path: Path) -> None:
    service = _service(tmp_path)

    created = service.create_memory(memory_class="fact", content="Works as a civil engineer.")

    assert created.source is None


def test_create_memory_with_manual_source(tmp_path: Path) -> None:
    service = _service(tmp_path)

    created = service.create_memory(
        memory_class="decision",
        content="Used Class 3 pipe on the Sydney Water rising main.",
        source_type="manual",
        source_label="Project: Sydney Water rising main",
    )

    assert created.source is not None
    assert created.source.source_type == "manual"
    assert created.source.source_id is None
    assert created.source.source_label == "Project: Sydney Water rising main"
    assert created.source.confidence == 1.0


def test_create_memory_with_manual_source_but_blank_label_stores_none(tmp_path: Path) -> None:
    service = _service(tmp_path)

    created = service.create_memory(
        memory_class="fact", content="Works as a civil engineer.", source_type="manual", source_label="   "
    )

    assert created.source is None


def test_create_memory_with_conversation_source(tmp_path: Path) -> None:
    service = _service(tmp_path)

    created = service.create_memory(
        memory_class="fact",
        content="Works as a civil engineer.",
        source_type="conversation",
        source_label="Suggested from SirisAI chat",
    )

    assert created.source is not None
    assert created.source.source_type == "conversation"
    assert created.source.source_id is None
    assert created.source.source_label == "Suggested from SirisAI chat"


def test_create_memory_with_project_source_resolves_current_name(tmp_path: Path) -> None:
    projects = _project_service(tmp_path)
    project = projects.create_project(name="Penrith treatment plant", kind="engineering", tags=[])
    service = _service(tmp_path, project_service=projects)

    created = service.create_memory(
        memory_class="fact", content="Uses AS 3500 for hydraulics.", source_type="project", source_id=project.id
    )

    assert created.source is not None
    assert created.source.source_type == "project"
    assert created.source.source_id == project.id
    assert created.source.source_label == "Penrith treatment plant"


def test_create_memory_with_project_source_always_resolves_fresh_name(tmp_path: Path) -> None:
    projects = _project_service(tmp_path)
    project = projects.create_project(name="Old name", kind="engineering", tags=[])
    projects.update_project(project.id, {"name": "New name"})
    service = _service(tmp_path, project_service=projects)

    created = service.create_memory(
        memory_class="fact", content="Note.", source_type="project", source_id=project.id
    )

    assert created.source.source_label == "New name"


def test_create_memory_with_unknown_project_id_raises(tmp_path: Path) -> None:
    projects = _project_service(tmp_path)
    service = _service(tmp_path, project_service=projects)

    with pytest.raises(MemorySourceNotFoundError):
        service.create_memory(
            memory_class="fact", content="Note.", source_type="project", source_id="missing-id"
        )


def test_create_memory_with_project_source_missing_id_raises(tmp_path: Path) -> None:
    service = _service(tmp_path, project_service=_project_service(tmp_path))

    with pytest.raises(ValueError):
        service.create_memory(memory_class="fact", content="Note.", source_type="project", source_id=None)


def test_loading_pre_structured_provenance_string_source_wraps_as_manual(tmp_path: Path) -> None:
    memory_path = tmp_path / "memory.json"
    memory_path.write_text(
        json.dumps(
            [
                {
                    "id": "abc-123",
                    "memory_class": "fact",
                    "content": "Works as a civil engineer.",
                    "source": "Suggested from SirisAI chat",
                    "created_at": "2026-08-22T12:00:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )
    service = _service(tmp_path)

    listed = service.list_memory()

    assert len(listed) == 1
    assert listed[0].source.source_type == "manual"
    assert listed[0].source.source_id is None
    assert listed[0].source.source_label == "Suggested from SirisAI chat"


def test_loading_pre_structured_provenance_null_source_stays_none(tmp_path: Path) -> None:
    memory_path = tmp_path / "memory.json"
    memory_path.write_text(
        json.dumps(
            [
                {
                    "id": "abc-123",
                    "memory_class": "fact",
                    "content": "Works as a civil engineer.",
                    "source": None,
                    "created_at": "2026-08-22T12:00:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )
    service = _service(tmp_path)

    listed = service.list_memory()

    assert listed[0].source is None
