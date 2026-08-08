from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

OCR_ENABLED = os.getenv("SIRISOS_STANDARDS_OCR_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
OCR_LANGUAGE = os.getenv("SIRISOS_STANDARDS_OCR_LANGUAGE", "eng")
OCR_TIMEOUT_SECONDS = int(os.getenv("SIRISOS_STANDARDS_OCR_TIMEOUT_SECONDS", "300"))
MIN_NATIVE_TEXT_CHARS = int(os.getenv("SIRISOS_STANDARDS_MIN_NATIVE_TEXT_CHARS", "40"))


@dataclass(frozen=True)
class StandardsExtraction:
    pages: list[dict[str, object]]
    indexed: bool
    extraction_method: str
    ocr_attempted: bool
    ocr_error: str | None = None


def _read_pages(pdf_path: Path) -> list[dict[str, object]]:
    reader = PdfReader(str(pdf_path))
    return [
        {"page": number, "text": page.extract_text() or ""}
        for number, page in enumerate(reader.pages, start=1)
    ]


def _has_usable_native_text(pages: list[dict[str, object]]) -> bool:
    return any(len(str(item.get("text") or "").strip()) >= MIN_NATIVE_TEXT_CHARS for item in pages)


def extract_standard_pages(pdf_path: Path) -> StandardsExtraction:
    """Extract page text, preferring native PDF text and falling back to local OCR.

    OCRmyPDF is only invoked when native extraction yields no useful page text. The
    searchable OCR PDF is temporary; the user's original PDF remains untouched and
    page numbering therefore remains aligned with citations.
    """
    try:
        native_pages = _read_pages(pdf_path)
    except Exception as exc:
        native_pages = []
        native_error = f"Native PDF extraction failed: {exc}"
    else:
        native_error = None

    if _has_usable_native_text(native_pages):
        return StandardsExtraction(
            pages=native_pages,
            indexed=True,
            extraction_method="native",
            ocr_attempted=False,
        )

    if not OCR_ENABLED:
        return StandardsExtraction(
            pages=native_pages,
            indexed=False,
            extraction_method="none",
            ocr_attempted=False,
            ocr_error=native_error,
        )

    with tempfile.TemporaryDirectory(prefix="sirisos-ocr-") as temporary_directory:
        output_path = Path(temporary_directory) / "searchable.pdf"
        command = [
            "ocrmypdf",
            "--skip-text",
            "--deskew",
            "--rotate-pages",
            "--output-type",
            "pdf",
            "-l",
            OCR_LANGUAGE,
            str(pdf_path),
            str(output_path),
        ]
        try:
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=OCR_TIMEOUT_SECONDS,
            )
            ocr_pages = _read_pages(output_path)
        except FileNotFoundError:
            return StandardsExtraction(
                pages=native_pages,
                indexed=False,
                extraction_method="none",
                ocr_attempted=True,
                ocr_error="OCRmyPDF is not installed in the SirisOS API container.",
            )
        except subprocess.TimeoutExpired:
            return StandardsExtraction(
                pages=native_pages,
                indexed=False,
                extraction_method="none",
                ocr_attempted=True,
                ocr_error=f"OCR exceeded the {OCR_TIMEOUT_SECONDS} second timeout.",
            )
        except Exception as exc:
            return StandardsExtraction(
                pages=native_pages,
                indexed=False,
                extraction_method="none",
                ocr_attempted=True,
                ocr_error=f"OCR failed: {exc}",
            )

    indexed = _has_usable_native_text(ocr_pages)
    return StandardsExtraction(
        pages=ocr_pages,
        indexed=indexed,
        extraction_method="ocr" if indexed else "none",
        ocr_attempted=True,
        ocr_error=None if indexed else "OCR completed but did not produce searchable text.",
    )
