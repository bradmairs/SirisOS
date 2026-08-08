from pathlib import Path

import pytest

from app.api import knowledge, knowledge_context


def _configure_vault(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(knowledge, "VAULT_ROOT", root)
    monkeypatch.setattr(knowledge, "MAX_SCAN_FILES", 100)
    monkeypatch.setattr(knowledge, "MAX_NOTE_BYTES", 1024 * 1024)


def test_siris_contexts_support_frontmatter_list_and_obsidian_tag() -> None:
    text = """---
siris: [engineering, homelab]
tags: [stormwater]
---
# Note
Also useful for #siris/briefings.
"""

    assert knowledge_context._siris_contexts(text) == {"engineering", "homelab", "briefings"}


def test_context_notes_return_only_explicitly_related_notes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_vault(monkeypatch, tmp_path)
    (tmp_path / "Drainage.md").write_text(
        "---\nsiris: [engineering]\n---\n# Drainage\nHydraulic notes.",
        encoding="utf-8",
    )
    (tmp_path / "Server.md").write_text(
        "# Server\n#siris/homelab\nDocker notes.",
        encoding="utf-8",
    )
    (tmp_path / "General.md").write_text("# General\nUnrelated.", encoding="utf-8")

    engineering = knowledge_context._context_notes("engineering")
    homelab = knowledge_context._context_notes("homelab")

    assert [item.title for item in engineering] == ["Drainage"]
    assert [item.title for item in homelab] == ["Server"]


def test_context_notes_are_most_recent_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_vault(monkeypatch, tmp_path)
    older = tmp_path / "Older.md"
    newer = tmp_path / "Newer.md"
    older.write_text("---\nsiris: engineering\n---\n# Older", encoding="utf-8")
    newer.write_text("---\nsiris: engineering\n---\n# Newer", encoding="utf-8")
    older.touch()
    newer.touch()
    older_stat = older.stat()
    newer_stat = newer.stat()
    # Give deterministic ordering without relying on filesystem creation timing.
    import os
    os.utime(older, (older_stat.st_atime, 1000))
    os.utime(newer, (newer_stat.st_atime, 2000))

    assert [item.title for item in knowledge_context._context_notes("engineering")] == ["Newer", "Older"]
