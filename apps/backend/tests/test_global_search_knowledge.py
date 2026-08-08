from pathlib import Path

import pytest

from app.api import knowledge
from app.services import knowledge_global_search
from app.services.knowledge_global_search import search_knowledge_notes


def _configure_vault(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(knowledge, "VAULT_ROOT", root)
    monkeypatch.setattr(knowledge, "MAX_SCAN_FILES", 100)
    monkeypatch.setattr(knowledge, "MAX_NOTE_BYTES", 1024 * 1024)
    monkeypatch.setattr(knowledge_global_search.semantic_search, "ollama_url", "")
    monkeypatch.setattr(knowledge_global_search.semantic_search, "model", "")


@pytest.mark.asyncio
async def test_global_search_returns_knowledge_note_with_path_reference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_vault(monkeypatch, tmp_path)
    projects = tmp_path / "Projects"
    projects.mkdir()
    (projects / "Drainage.md").write_text(
        "---\ntags: [engineering, stormwater]\n---\n# Penrith drainage design\nPipe grade and detention notes.",
        encoding="utf-8",
    )

    results = await search_knowledge_notes("detention")

    assert len(results) == 1
    assert results[0].title == "Penrith drainage design"
    assert results[0].path == "Projects/Drainage.md"
    assert "#engineering" in results[0].subtitle
    assert results[0].strategy == "lexical"


@pytest.mark.asyncio
async def test_global_search_ranks_title_match_above_body_match(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_vault(monkeypatch, tmp_path)
    (tmp_path / "Hydraulics.md").write_text("# Hydraulics\nGeneral note.", encoding="utf-8")
    (tmp_path / "Meeting.md").write_text("# Meeting\nDiscuss hydraulics later.", encoding="utf-8")

    results = await search_knowledge_notes("hydraulics")

    assert [result.title for result in results] == ["Hydraulics", "Meeting"]
