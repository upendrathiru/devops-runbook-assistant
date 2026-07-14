# Architecture

## Data flow

```
Documents (.md, .pdf runbooks/playbooks)
        │  ingestion.py
        ▼
  Section-aware chunking (~220 words, 40-word overlap)
        │  retrieval.py
        ▼
     Embedding  →  Vector index (persisted to data/index.pkl)
        │
        │  (at query time)
        ▼
  User question → embed query → cosine-similarity search → top-k chunks
        │
        ▼
  Prompt = system instructions + retrieved chunks + question   (llm.py)
        │
        ▼
        LLM  →  grounded answer + cited sources
        │
        ▼
  storage.py logs {question, answer, sources, latency, feedback} to SQLite
        │
        ▼
  frontend/index.html renders answer, source chips, feedback buttons
```

See `docs/architecture-diagram.svg` for the visual version.

## How retrieval works

1. **Ingestion** (`ingestion.py`) walks `data/runbooks/`, extracts text from
   Markdown or PDF, and splits each document on `##` headings so every chunk
   keeps its section title. Sections are then split into ~220-word chunks
   with 40-word overlap (word count is a dependency-free proxy for the
   spec's "~512 token" target).
2. **Embedding + indexing** (`retrieval.py`) fits a TF-IDF vectorizer
   (unigrams + bigrams) over all chunks and stores the resulting sparse
   matrix + chunk metadata in a single pickle file — this plays the same
   architectural role as a FAISS/Pinecone/Weaviate vector store, behind the
   same `EmbeddingIndex.search()` interface, so it's a drop-in swap later.
3. **Query time**: the question is vectorized with the same TF-IDF model,
   cosine similarity is computed against every chunk, and the top-k
   (default 4) chunks above a minimum similarity threshold are returned.
4. **Generation** (`llm.py`): retrieved chunks + the question are assembled
   into a prompt with a system instruction that tells the model to answer
   *only* from the provided context and to say "I'm not sure" rather than
   guess if nothing relevant was retrieved. The `LLMProvider` interface has
   three implementations (`mock`, `huggingface`, `ollama`) — see README.
5. **Logging** (`storage.py`): every query, answer, source list, latency,
   and later feedback vote is written to SQLite for audit and metrics.

## Why TF-IDF instead of a neural embedding model by default

This environment has no GPU and no external network access, so downloading
a real embedding model or calling an API isn't possible in the default
config. TF-IDF is a legitimate, fully-offline embedding baseline that works
well for keyword-heavy operational text (service names, command flags,
runbook terminology) — the automated test suite (`tests/`) shows 20/20
retrieval-and-fallback tests passing against it. `retrieval.py` is written
against an `EmbeddingIndex` interface specifically so a sentence-transformers
or OpenAI-embedding-backed index can be substituted without touching
ingestion, the API, or the frontend.

## Limitations

- **Hallucination risk**: even with retrieval, an LLM can still misstate a
  detail not explicitly in the retrieved chunks. Mitigations in place: the
  system prompt instructs "answer only from context," a "not sure" fallback
  is required when no relevant chunk is retrieved, and every answer displays
  its source chunks so a human can verify before acting — this tool assists,
  it doesn't replace human judgment on production changes.
- **Out-of-date docs**: retrieval is only as good as the last reindex. If a
  runbook changes and the index isn't rebuilt, the assistant will confidently
  cite the stale version. See the maintenance plan below.
- **TF-IDF is keyword-based, not semantic**: it won't handle paraphrases as
  gracefully as a neural embedding model (e.g. it may not connect "roll
  back" and "revert" as strongly as a sentence-transformer would). Retrieval
  quality should be periodically reviewed against real user queries.
- **Chunk-boundary loss**: a procedure that spans a chunk boundary may be
  only partially retrieved; overlap (40 words) mitigates but doesn't
  eliminate this.
- **No OCR for scanned PDFs**: `ingestion.py` extracts text via `pypdf`,
  which does not handle image-only/scanned PDF pages. Add an OCR step
  (e.g. Tesseract) if your runbooks include scanned documents.
- **Mock LLM provider is extractive, not generative**: the default offline
  mode produces a templated answer built from the top retrieved chunk. It
  demonstrates the full pipeline and passes citation/fallback tests, but for
  natural, synthesized multi-source answers, configure a real
  `huggingface` or `ollama` provider.

## Maintenance plan

- **Re-ingest monthly at minimum**, or immediately after any significant
  runbook update (schedule a cron job hitting `POST /api/ingest/reindex`,
  or trigger it from your docs repo's CI on merge to `main`).
- **Review the "queries with no answer" metric** (`GET /api/metrics`)
  periodically — a rising count often means either a documentation gap or a
  retrieval-quality issue worth investigating.
- **Review "not helpful" feedback** in the exported audit log
  (`GET /api/logs/export`) to find systematic gaps in the runbook corpus.
- **Rotate/encrypt the SQLite (or Postgres) audit log** per your internal
  data-retention policy, since it contains real user queries.

## Security notes

- Default deployment target is **internal-only, behind the corporate VPC**,
  with SSO/LDAP enforced at the reverse-proxy layer (`app.py`'s
  `RUNBOOK_REQUIRE_AUTH_HEADER` is the integration point for a real auth
  middleware).
- No external model/API calls in the default (`mock`) or `ollama` (local)
  configurations — only `huggingface` mode downloads a model from Hugging
  Face, and that only happens once at first load.
- All queries and answers are logged for audit; treat the log store as
  containing potentially sensitive operational data.
