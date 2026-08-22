from pathlib import Path

from app.services.knowledge_service import KnowledgeService


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_search_ranks_title_match_above_body_match(tmp_path: Path) -> None:
    _write(tmp_path, "Hydraulics.md", "# Hydraulics\nGeneral note.")
    _write(tmp_path, "Meeting.md", "# Meeting\nDiscuss hydraulics later.")
    service = KnowledgeService(vault_root=tmp_path)

    result = service.search("hydraulics")

    assert result.query == "hydraulics"
    assert [note.title for note in result.hits] == ["Hydraulics", "Meeting"]


def test_search_respects_folder_and_tag_filters(tmp_path: Path) -> None:
    _write(tmp_path, "Projects/Drainage.md", "---\ntags: [engineering]\n---\n# Drainage\nStormwater notes.")
    _write(tmp_path, "Personal/Drainage.md", "# Drainage\nUnrelated personal note.")
    service = KnowledgeService(vault_root=tmp_path)

    by_folder = service.search("drainage", folder="Projects")
    assert [note.path for note in by_folder.hits] == ["Projects/Drainage.md"]

    by_tag = service.search("drainage", tag="engineering")
    assert [note.path for note in by_tag.hits] == ["Projects/Drainage.md"]


def test_search_matches_a_multi_word_query_not_present_as_one_exact_phrase(tmp_path: Path) -> None:
    # A model-generated (or human-typed) query is usually several keywords,
    # not one exact contiguous phrase -- "drainage design pipe grade" never
    # appears verbatim in a note that separately says "Drainage Design" and
    # "pipe grade". This must still find it via word-level scoring.
    _write(tmp_path, "Drainage Design.md", "# Drainage Design\nUse AS 3725 for pipe grade calculations.")
    service = KnowledgeService(vault_root=tmp_path)

    result = service.search("drainage design pipe grade")

    assert [note.path for note in result.hits] == ["Drainage Design.md"]


def test_search_still_ranks_an_exact_phrase_match_first(tmp_path: Path) -> None:
    _write(tmp_path, "Exact.md", "# Drainage pipe grade\nExact phrase in the title.")
    _write(tmp_path, "Partial.md", "# Notes\nMentions drainage somewhere and pipe grade elsewhere.")
    service = KnowledgeService(vault_root=tmp_path)

    result = service.search("drainage pipe grade")

    assert result.hits[0].path == "Exact.md"


def test_search_respects_limit(tmp_path: Path) -> None:
    for index in range(5):
        _write(tmp_path, f"Note{index}.md", f"# Note {index}\nmatch")
    service = KnowledgeService(vault_root=tmp_path)

    result = service.search("match", limit=2)

    assert len(result.hits) == 2


def test_search_with_no_query_returns_all_notes(tmp_path: Path) -> None:
    _write(tmp_path, "One.md", "# One")
    _write(tmp_path, "Two.md", "# Two")
    service = KnowledgeService(vault_root=tmp_path)

    result = service.search("")

    assert {note.title for note in result.hits} == {"One", "Two"}


def test_read_note_returns_full_content(tmp_path: Path) -> None:
    _write(tmp_path, "Notes/Idea.md", "---\ntags: [siris]\n---\n# Idea\nBody text here.")
    service = KnowledgeService(vault_root=tmp_path)

    note = service.read_note("Notes/Idea.md")

    assert note is not None
    assert note.title == "Idea"
    assert note.tags == ["siris"]
    assert note.content == "---\ntags: [siris]\n---\n# Idea\nBody text here."


def test_read_note_returns_none_for_missing_note(tmp_path: Path) -> None:
    service = KnowledgeService(vault_root=tmp_path)

    assert service.read_note("Nowhere.md") is None


def test_read_note_returns_none_for_path_escaping_the_vault(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.md"
    outside.write_text("# Outside", encoding="utf-8")
    service = KnowledgeService(vault_root=tmp_path)

    assert service.read_note("../outside.md") is None


def test_read_note_returns_none_for_non_markdown_file(tmp_path: Path) -> None:
    _write(tmp_path, "notes.txt", "not markdown")
    service = KnowledgeService(vault_root=tmp_path)

    assert service.read_note("notes.txt") is None
