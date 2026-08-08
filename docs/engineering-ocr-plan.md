# Engineering Standards OCR Plan

OCR is the next indexing layer for standards that contain little or no extractable PDF text.

## Constraints
- OCR runs locally on the SirisOS server.
- The original licensed PDF remains unchanged and authoritative.
- OCR output is stored as derived page text with page provenance.
- Indexing failure must not make the original document unavailable.
- OCR must be asynchronous for large documents so uploads do not block for minutes.
- Index state should distinguish `searchable`, `ocr-pending`, `ocr-indexed`, and `index-failed` once the metadata model is upgraded.

## Proposed implementation
1. Detect pages with no useful extracted text after normal PDF extraction.
2. Queue OCR work for only those pages.
3. Render pages locally at a bounded resolution.
4. OCR locally and merge derived text into the existing page index.
5. Preserve extraction method per page (`pdf-text` or `ocr`).
6. Surface progress/state in the Standards Library.

No cloud OCR service should be required for the default self-hosted path.
