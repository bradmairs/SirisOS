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
        "---\ntags: [engineering, stormwater]\n---\n# Drainage design\nSee [[AS 3725|Concrete pipe]] and [[Project Alpha#Hydraulics]]. #review\n",
        encoding="utf-8",
    )

    summary = knowledge._summary(note)

    assert summary.title == "Drainage design"
    assert summary.tags == ["engineering", "review", "stormwater"]
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


def test_wikilink_resolves_relative_note_before_stem_lookup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_vault(monkeypatch, tmp_path)
    project = tmp_path / "Projects" / "Alpha"
    project.mkdir(parents=True)
    (project / "Hydraulics.md").write_text("# Project hydraulics", encoding="utf-8")
    (tmp_path / "Hydraulics.md").write_text("# General hydraulics", encoding="utf-8")

    resolved, candidates = knowledge._resolve_link("Hydraulics", "Projects/Alpha/Meeting.md")

    assert resolved is not None
    assert resolved.path == "Projects/Alpha/Hydraulics.md"
    assert len(candidates) == 1


def test_ambiguous_wikilink_is_not_silently_resolved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_vault(monkeypatch, tmp_path)
    first = tmp_path / "A"
    second = tmp_path / "B"
    first.mkdir()
    second.mkdir()
    (first / "Design.md").write_text("# Design A", encoding="utf-8")
    (second / "Design.md").write_text("# Design B", encoding="utf-8")

    resolved, candidates = knowledge._resolve_link("Design")

    assert resolved is None
    assert [item.path for item in candidates] == ["A/Design.md", "B/Design.md"]


def test_folder_and_tag_metadata_can_be_counted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_vault(monkeypatch, tmp_path)
    folder = tmp_path / "Engineering"
    folder.mkdir()
    (folder / "Drainage.md").write_text("# Drainage\n#stormwater", encoding="utf-8")
    (folder / "Roads.md").write_text("# Roads\n#transport", encoding="utf-8")

    summaries = knowledge._all_summaries()

    assert {item.path for item in summaries} == {"Engineering/Drainage.md", "Engineering/Roads.md"}
    assert {tag for item in summaries for tag in item.tags} == {"stormwater", "transport"}
