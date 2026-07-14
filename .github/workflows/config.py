"""
Central configuration for the DevOps Runbook Assistant backend.
All values can be overridden via environment variables so this is safe
to deploy across dev/staging/prod without code changes.
"""
import os

# --- Paths -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.environ.get("RUNBOOK_DOCS_DIR", os.path.join(BASE_DIR, "data", "runbooks"))
DB_PATH = os.environ.get("RUNBOOK_DB_PATH", os.path.join(BASE_DIR, "data", "app.db"))
INDEX_PATH = os.environ.get("RUNBOOK_INDEX_PATH", os.path.join(BASE_DIR, "data", "index.pkl"))

# --- Chunking ------------------------------------------------------------
# Measured in whitespace-separated "words" as a simple, dependency-free proxy
# for tokens. ~512 tokens ≈ ~380-400 words for English prose; kept configurable.
CHUNK_SIZE_WORDS = int(os.environ.get("RUNBOOK_CHUNK_SIZE_WORDS", 220))
CHUNK_OVERLAP_WORDS = int(os.environ.get("RUNBOOK_CHUNK_OVERLAP_WORDS", 40))

# --- Retrieval -----------------------------------------------------------
TOP_K = int(os.environ.get("RUNBOOK_TOP_K", 4))
MIN_SIMILARITY = float(os.environ.get("RUNBOOK_MIN_SIMILARITY", 0.08))

# --- LLM provider ----------------------------------------------------------
# "mock"       -> deterministic, offline, extractive-summary responder (default,
#                 works with zero external dependencies or GPU — good for demos
#                 and for environments without model access).
# "huggingface"-> loads a real LLaMA 2 (or any causal LM) checkpoint locally.
# "ollama"     -> calls a local Ollama server (OpenAI-compatible-ish REST API),
#                 the easiest way to run real LLaMA 2 without managing weights.
LLM_PROVIDER = os.environ.get("RUNBOOK_LLM_PROVIDER", "mock")
HF_MODEL_NAME = os.environ.get("RUNBOOK_HF_MODEL_NAME", "meta-llama/Llama-2-7b-chat-hf")
OLLAMA_URL = os.environ.get("RUNBOOK_OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("RUNBOOK_OLLAMA_MODEL", "llama2")
MAX_RESPONSE_TOKENS = int(os.environ.get("RUNBOOK_MAX_RESPONSE_TOKENS", 400))

# --- Security --------------------------------------------------------------
# In production, put this behind corporate SSO/LDAP + a reverse proxy.
# REQUIRE_AUTH_HEADER, if set, requires every request to include the given
# header (simple stand-in for a real SSO/LDAP-integrated auth layer).
REQUIRE_AUTH_HEADER = os.environ.get("RUNBOOK_REQUIRE_AUTH_HEADER", "")  # e.g. "X-Internal-User"

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
