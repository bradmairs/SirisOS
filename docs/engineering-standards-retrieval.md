# Engineering Standards Retrieval Contract

This is the evidence contract for future SirisHydro integration.

## Retrieval object
A standards evidence item must retain:

- `document.id`
- `document.title`
- `document.authority`
- `document.reference`
- `document.edition`
- `page`
- exact locally extracted page text or a bounded excerpt
- deterministic human-readable citation

## Answering rules
1. Search the private standards library before asking a model to answer a standards-specific question.
2. Pass only relevant retrieved evidence into the model context.
3. Require the answer to distinguish source-supported statements from general engineering reasoning.
4. Cite the local document reference/edition/page for source-supported statements.
5. If retrieval does not support a requested requirement, say that the library did not establish it rather than inventing a clause or citation.
6. Treat tables, drawings, equations and page layout as potentially lossy in extracted text; direct the user to the licensed PDF where those features are material.
7. Never treat Ollama model knowledge as a substitute for the retrieved standard.

## Next retrieval upgrades
- OCR for scanned/image-only PDFs.
- Multi-hit chunking rather than one hit per document.
- Phrase/token ranking and authority/reference filters.
- Optional embeddings for semantic recall while retaining deterministic page provenance.
- SirisHydro answer composition using the same evidence objects.
