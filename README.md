# DevOps Runbook Assistant

An internal RAG (retrieval-augmented generation) chat tool that answers
operational questions — deployments, rollbacks, migrations, pipelines,
incident response — grounded in your team's actual runbooks, playbooks, and
docs. Every answer cites the runbook section it came from.

Built following the architecture in `docs/ARCHITECTURE.md`, based on the
LLaMA 2 paper (Touvron et al., 2023) as the base model target, with a
pluggable LLM layer (see [LLM providers](#llm-providers) below).

## What's in the box

```
devops-runbook-assistant/
├── backend/            FastAPI-style API (Flask), ingestion, retrieval, LLM layer, storage
│   ├── app.py           API server & routes
│   ├── config.py         All settings (env-var driven)
│   ├── ingestion.py      Doc ingestion module (Markdown + PDF → chunks)
│   ├── retrieval.py      Retrieval module (embeddings + vector index + search)
│   ├── llm.py             Model inference module (pluggable: mock / HF LLaMA2 / Ollama)
│   └── storage.py        Storage & audit-log module (SQLite; Postgres-compatible SQL)
├── frontend/           Chat UI module (index.html — vanilla JS, no build step)
├── data/runbooks/      Sample internal runbooks (replace with your real docs)
├── tests/               20 test questions + automated runner (see checklist)
├── docs/
│   ├── ARCHITECTURE.md   How retrieval works, limitations, maintenance plan
│   └── architecture-diagram.svg
├── requirements.txt
└── run.sh               One-command local start
```

This maps directly onto the required module breakdown: **ingestion module**,
**retrieval module**, **model inference module**, **UI module**.

## Quick start (local, fully offline demo)

Requires Python 3.10+. No GPU, API key, or internet connection needed for the
default mode — it runs entirely offline using TF-IDF retrieval and a
grounded, extractive "mock" LLM provider, so you (and reviewers) can see the
full ingestion → retrieval → chat → citation → audit-log flow end to end
before wiring up a real model.

```bash
cd devops-runbook-assistant
pip install -r requirements.txt
./run.sh
```

Then open **http://localhost:8000** — the Flask server serves both the API
and the chat UI.

To re-index after adding/editing runbooks:
```bash
curl -X POST http://localhost:8000/api/ingest/reindex
# or: cd backend && python3 retrieval.py
```

## Adding your real runbooks

Drop `.md` or `.pdf` files into `data/runbooks/` (subfolders are fine), then
reindex. The ingestion module splits each doc on `##` headings so citations
point to the actual section, not just the filename.

```bash
export RUNBOOK_DOCS_DIR=/path/to/your/internal/docs
```

## LLM providers

Set `RUNBOOK_LLM_PROVIDER` to switch model backends — no other code changes
needed:

| Value | What it does | Requirements |
|---|---|---|
| `mock` (default) | Offline, deterministic, grounded extractive answers. Good for demos, CI, and testing retrieval quality without a GPU. | None |
| `huggingface` | Loads a real LLaMA 2 checkpoint locally via `transformers`. | GPU with sufficient VRAM, `pip install transformers accelerate torch`, HF token with LLaMA 2 license accepted. Set `RUNBOOK_HF_MODEL_NAME` (default `meta-llama/Llama-2-7b-chat-hf`; use the `13b` variant if hardware allows). |
| `ollama` | Calls a local [Ollama](https://ollama.com) server running `llama2`. Easiest path to a real model. | `ollama pull llama2` running locally; `pip install requests`. Set `RUNBOOK_OLLAMA_URL` / `RUNBOOK_OLLAMA_MODEL` if non-default. |

```bash
# Example: real LLaMA 2 via Ollama
ollama pull llama2
export RUNBOOK_LLM_PROVIDER=ollama
./run.sh
```

## Key environment variables

| Variable | Default | Purpose |
|---|---|---|
| `RUNBOOK_DOCS_DIR` | `data/runbooks` | Where ingestion reads source docs from |
| `RUNBOOK_DB_PATH` | `data/app.db` | SQLite audit-log DB path |
| `RUNBOOK_INDEX_PATH` | `data/index.pkl` | Persisted vector index |
| `RUNBOOK_CHUNK_SIZE_WORDS` | `220` | Chunk size (~word proxy for ~512 tokens) |
| `RUNBOOK_TOP_K` | `4` | Chunks retrieved per query |
| `RUNBOOK_LLM_PROVIDER` | `mock` | `mock` / `huggingface` / `ollama` |
| `RUNBOOK_REQUIRE_AUTH_HEADER` | *(unset)* | If set, gates `/api/*` behind a header — stand-in for real SSO/LDAP at the reverse-proxy layer |
| `PORT` | `8000` | API/UI port |

## Testing

```bash
./run.sh                                  # in one terminal
python3 tests/run_test_questions.py       # in another
```

Runs all 20 questions from `tests/test_questions.md` (deployment, rollback,
migration, nightly build, incident response, plus two out-of-scope
questions that must trigger the "not sure" fallback rather than a
hallucinated answer) and reports pass/fail on citation presence. See that
file's grading rubric for the manual correctness/citation-accuracy check.

## Exporting audit logs

`GET /api/logs/export` (or the "Export logs" button in the UI) downloads a
CSV of every query, answer, feedback flag, and timestamp — the audit trail
required for internal-tool compliance.

## Production deployment notes

This repo runs the Flask dev server for local/demo use. For production:
- Run behind Gunicorn/uWSGI + a reverse proxy (nginx) inside your corporate VPC.
- Put real SSO/LDAP auth at the reverse-proxy layer (see `RUNBOOK_REQUIRE_AUTH_HEADER`
  as the integration point in `app.py`).
- Swap SQLite for PostgreSQL — `storage.py` uses standard SQL only, so this is
  a driver/connection-string change, not a rewrite.
- Swap the TF-IDF index for a real embedding model (sentence-transformers or
  an internal embedding API) + FAISS/Pinecone/Weaviate for larger corpora —
  implement the `EmbeddingIndex` interface in `retrieval.py`.
- Containerize with Docker (backend + model server) and deploy to a
  GPU-enabled instance if using `huggingface` provider mode.

See `docs/ARCHITECTURE.md` for the full design, limitations, and monthly
re-ingestion maintenance plan.
