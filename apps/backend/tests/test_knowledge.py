from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api import knowledge


def _configure_vault(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(knowledge, "VAULT_ROOT", root)
    monkeypatch.setattr(knowledge, "MAX_SCAN_FILES", 100)
    monkeypatch.setattr(knowledge, "MAX_NOTE_BYTES", 1024 * 1024)


def test_summary_extracts_title_tags_wikilinks_and_daily_note(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_vault(monkeypatch, tmp_path)
    note = tmp_path / "2026-08-08.md"
    note.write_text(
        "---\ntags: [engineering, stormwater]\n---\n# Drainage design\nSee [[AS 3725|Concrete pipe]] and [[Project Alpha#Hydraulics]].\n",
        encoding="utf-8",
    )

    summary = knowledge._summary(note)

    assert summary.title == "Drainage design"
    assert summary.tags == ["engineering", "stormwater"]
    assert summary.wikilinks == ["AS 3725", "Project Alpha"]
    assert summary.is_daily_note is True


def test_markdown_scan_ignores_hidden_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_vault(monkeypatch, tmp_path)
    (tmp_path / "Visible.md").write_text("# Visible", encoding="utf-8")
    hidden = tmp_path / ".obsidian"
    hidden.mkdir()
    (hidden / "Internal.md").write_text("# Internal", encoding="utf-8")

    files = knowledge._markdown_files()

    assert [path.name for path in files] == ["Visible.md"]


def test_safe_note_path_rejects_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_vault(monkeypatch, tmp_path)
    outside = tmp_path.parent / "outside.md"
    outside.write_text("secret", encoding="utf-8")

    with pytest.raises(HTTPException) as exc_info:
        knowledge._safe_note_path("../outside.md")

    assert exc_info.value.status_code == 400


def test_title_falls_back_to_filename(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_vault(monkeypatch, tmp_path)
    note = tmp_path / "Project Notes.md"
    note.write_text("No heading here", encoding="utf-8")

    assert knowledge._summary(note).title == "Project Notes"
