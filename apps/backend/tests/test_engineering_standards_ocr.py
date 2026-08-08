from pathlib import Path
from unittest.mock import patch

from app.services.engineering_standards_ocr import (
    StandardsExtraction,
    _has_usable_native_text,
    extract_standard_pages,
)


def test_usable_native_text_requires_meaningful_page_content() -> None:
    assert not _has_usable_native_text([{"page": 1, "text": "   "}])
    assert _has_usable_native_text(
        [{"page": 1, "text": "Minimum cover beneath trafficable areas shall be checked."}]
    )


def test_native_text_bypasses_ocr() -> None:
    pages = [
        {
            "page": 1,
            "text": "This page contains enough native searchable engineering standard text.",
        }
    ]
    with patch("app.services.engineering_standards_ocr._read_pages", return_value=pages), patch(
        "app.services.engineering_standards_ocr.subprocess.run"
    ) as run:
        result = extract_standard_pages(Path("standard.pdf"))

    assert result == StandardsExtraction(
        pages=pages,
        indexed=True,
        extraction_method="native",
        ocr_attempted=False,
    )
    run.assert_not_called()


def test_missing_ocr_runtime_fails_closed_without_losing_page_index() -> None:
    native_pages = [{"page": 1, "text": ""}, {"page": 2, "text": ""}]
    with patch("app.services.engineering_standards_ocr._read_pages", return_value=native_pages), patch(
        "app.services.engineering_standards_ocr.subprocess.run", side_effect=FileNotFoundError
    ):
        result = extract_standard_pages(Path("scanned.pdf"))

    assert result.pages == native_pages
    assert result.indexed is False
    assert result.extraction_method == "none"
    assert result.ocr_attempted is True
    assert "not installed" in (result.ocr_error or "")
