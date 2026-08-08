# ADR 036 — Local OCR for engineering standards

## Status
Accepted

## Context
The private Engineering Standards Library can index PDFs containing native text, but scanned/image-only standards remain unavailable to deterministic search and SirisHydro evidence retrieval.

## Decision
- Prefer native `pypdf` extraction whenever a PDF already contains usable text.
- Fall back to OCRmyPDF + Tesseract only when native extraction produces no meaningful searchable page text.
- Run OCR entirely inside the self-hosted SirisOS API container; no standards content is sent to external OCR or AI services.
- Keep the originally uploaded licensed PDF unchanged. OCR produces a temporary searchable copy used only to extract page text, preserving original page numbering for citations.
- Persist page text into the existing local index and record `extraction_method`, `ocr_attempted`, and any soft OCR error in document metadata.
- OCR failure is non-fatal: the original PDF remains stored and the document remains clearly unindexed.
- SirisHydro continues to cite the original document/reference/edition/page, regardless of whether page text came from native extraction or OCR.

## Configuration
OCR is enabled by default and can be controlled with `SIRISOS_STANDARDS_OCR_ENABLED`, `SIRISOS_STANDARDS_OCR_LANGUAGE`, `SIRISOS_STANDARDS_OCR_TIMEOUT_SECONDS`, and `SIRISOS_STANDARDS_MIN_NATIVE_TEXT_CHARS`.

## Consequences
The API image becomes larger because it includes OCRmyPDF, Tesseract and Ghostscript. Uploading scanned standards may also take materially longer than native-text PDFs, but all processing remains private and traceable.
