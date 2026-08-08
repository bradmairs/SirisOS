# Knowledge semantic search

SirisOS can optionally use a local Ollama embedding model to broaden Knowledge results in Global Search.

Deterministic title/path/tag/content search always remains enabled. If Ollama is unavailable, the configured embedding model is missing, the request times out, or embeddings fail, SirisOS silently falls back to deterministic search.

## Configuration

```env
OLLAMA_URL=http://192.168.0.100:11434
SIRISOS_KNOWLEDGE_EMBEDDING_MODEL=<your-installed-embedding-model>
SIRISOS_KNOWLEDGE_SEMANTIC_TIMEOUT_SECONDS=20
SIRISOS_KNOWLEDGE_SEMANTIC_MAX_NOTES=500
```

Leave `SIRISOS_KNOWLEDGE_EMBEDDING_MODEL` blank to disable semantic search.

The model named in `SIRISOS_KNOWLEDGE_EMBEDDING_MODEL` must already be available to the configured Ollama instance. SirisOS does not automatically download models.

## Ranking behavior

- exact note-title matches receive the strongest deterministic weight;
- partial title, path, tag and body matches retain deterministic weights;
- Ollama cosine similarity adds a bounded semantic contribution;
- semantic-only results are allowed when they meaningfully match the query;
- cached note embeddings are invalidated automatically when the note modification time or size changes.

The semantic scan is bounded to protect a home server from an unexpectedly expensive first search. When a vault is larger than the configured bound, recently modified notes are embedded first. Deterministic lexical search still covers the full configured vault scan limit.
