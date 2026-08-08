# ADR 033 — Private Engineering Standards Library

## Status
Accepted

## Context
SirisOS needs a standards-search foundation for Engineering/SirisHydro. Some authoritative standards are publicly accessible while others are licensed documents that the user is legally entitled to store locally. SirisOS must not scrape, redistribute, or silently substitute protected standards content.

## Decision
SirisOS will support a private, authenticated standards library alongside authoritative external-source metadata.

- Licensed PDFs are uploaded explicitly by the authenticated SirisOS administrator.
- Raw documents are persisted under `data/standards` and are not bundled into the application image or repository.
- Each document records title, authority/publisher, optional reference, optional edition/revision, filename, upload timestamp, page count, and indexing status.
- Text-based PDFs are indexed locally page-by-page using `pypdf`; search returns short snippets with page provenance.
- Image/scanned PDFs are retained but marked not indexed. OCR is a separate future capability and must not block upload.
- Search and file retrieval endpoints require the normal SirisOS bearer session.
- The Engineering UI also links to authoritative external catalogues for discovery, but SirisOS does not scrape or redistribute their protected content.
- Uploaded document content remains a private local source for future citation-first SirisHydro retrieval and Ollama/RAG workflows.

## Safety and provenance
A model-generated engineering answer must never obscure its source. Future SirisHydro retrieval should cite the exact local document, reference/edition, and page where possible, and distinguish local licensed copies from public authority material.

## Storage and limits
The default upload limit is 100 MB per PDF and is configurable through `SIRISOS_STANDARDS_MAX_UPLOAD_MB`. `make up` creates `data/standards`, which is bind-mounted into the API container.

## Consequences
This provides useful local search immediately without making an LLM a dependency. OCR, semantic/vector indexing, document deletion/version replacement, authority profiles, and SirisHydro question answering remain follow-on work.
