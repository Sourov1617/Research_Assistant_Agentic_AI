"""
Central configuration loader.
All credentials & settings are sourced exclusively from the .env file.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env", override=True)


def _get(key: str, default=None, cast=None):
    val = os.getenv(key, default)
    if val is None:
        return default
    if cast is bool:
        return str(val).lower() in ("true", "1", "yes")
    if cast:
        return cast(val)
    return val


# ── LLM Provider ──────────────────────────────────────────────────────────────
LLM_PROVIDER: str = _get("LLM_PROVIDER", "openai")
DEFAULT_MODEL: str = _get("DEFAULT_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE: float = _get("LLM_TEMPERATURE", 0.2, float)

# ── OpenAI ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY: str = _get("OPENAI_API_KEY", "")
OPENAI_BASE_URL: str = _get("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_DEFAULT_MODEL: str = _get("OPENAI_DEFAULT_MODEL", "gpt-4o-mini")

# ── OpenRouter ────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY: str = _get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL: str = _get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_DEFAULT_MODEL: str = _get(
    "OPENROUTER_DEFAULT_MODEL", "meta-llama/llama-3.1-8b-instruct:free"
)

# ── Google Gemini ─────────────────────────────────────────────────────────────
GOOGLE_API_KEY: str = _get("GOOGLE_API_KEY", "")
GEMINI_BASE_URL: str = _get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com")
GEMINI_DEFAULT_MODEL: str = _get("GEMINI_DEFAULT_MODEL", "gemini-2.0-flash")

# ── Anthropic ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = _get("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL: str = _get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
ANTHROPIC_DEFAULT_MODEL: str = _get("ANTHROPIC_DEFAULT_MODEL", "claude-3-haiku-20240307")

# ── Ollama (local) ────────────────────────────────────────────────────────────
OLLAMA_BASE_URL: str = _get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_DEFAULT_MODEL: str = _get("OLLAMA_DEFAULT_MODEL", "llama3.2")

# ── Semantic Scholar ──────────────────────────────────────────────────────────
SEMANTIC_SCHOLAR_API_KEY: str = _get("SEMANTIC_SCHOLAR_API_KEY", "")
SEMANTIC_SCHOLAR_BASE_URL: str = _get(
    "SEMANTIC_SCHOLAR_BASE_URL", "https://api.semanticscholar.org/graph/v1"
)

# ── arXiv ─────────────────────────────────────────────────────────────────────
ARXIV_BASE_URL: str = _get("ARXIV_BASE_URL", "http://export.arxiv.org/api/query")
ARXIV_MAX_RESULTS: int = _get("ARXIV_MAX_RESULTS", 15, int)

# ── CORE API ──────────────────────────────────────────────────────────────────
CORE_API_KEY: str = _get("CORE_API_KEY", "")
CORE_BASE_URL: str = _get("CORE_BASE_URL", "https://api.core.ac.uk/v3")

# ── CrossRef ──────────────────────────────────────────────────────────────────
CROSSREF_EMAIL: str = _get("CROSSREF_EMAIL", "")
CROSSREF_BASE_URL: str = _get("CROSSREF_BASE_URL", "https://api.crossref.org/works")

# ── Web Search ────────────────────────────────────────────────────────────────
TAVILY_API_KEY: str = _get("TAVILY_API_KEY", "")
TAVILY_BASE_URL: str = _get("TAVILY_BASE_URL", "https://api.tavily.com")
SERPAPI_API_KEY: str = _get("SERPAPI_API_KEY", "")
USE_DUCKDUCKGO_FALLBACK: bool = _get("USE_DUCKDUCKGO_FALLBACK", True, bool)

# ── Vector Store ──────────────────────────────────────────────────────────────
VECTOR_STORE_TYPE: str = _get("VECTOR_STORE_TYPE", "faiss")
VECTOR_STORE_PATH: str = _get("VECTOR_STORE_PATH", "./data/vector_store")

# ── Embeddings ────────────────────────────────────────────────────────────────
EMBEDDING_PROVIDER: str = _get("EMBEDDING_PROVIDER", "huggingface")
EMBEDDING_MODEL: str = _get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
OPENAI_EMBEDDING_MODEL: str = _get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

# ── Memory ────────────────────────────────────────────────────────────────────
MEMORY_ENABLED_DEFAULT: bool = _get("MEMORY_ENABLED_DEFAULT", False, bool)
MEMORY_BACKEND: str = _get("MEMORY_BACKEND", "sqlite")
SQLITE_DB_PATH: str = _get("SQLITE_DB_PATH", "./data/memory/research_memory.db")
JSON_MEMORY_PATH: str = _get("JSON_MEMORY_PATH", "./data/memory/sessions/")
MAX_MEMORY_TURNS: int = _get("MAX_MEMORY_TURNS", 20, int)
MAX_PAPERS_IN_MEMORY: int = _get("MAX_PAPERS_IN_MEMORY", 100, int)

# ── Agent Behavior ────────────────────────────────────────────────────────────
MAX_PAPERS_PER_SOURCE: int = _get("MAX_PAPERS_PER_SOURCE", 10, int)
MAX_RANKED_PAPERS: int = _get("MAX_RANKED_PAPERS", 15, int)
MIN_RELEVANCE_SCORE: float = _get("MIN_RELEVANCE_SCORE", 0.3, float)
MAX_SYNTHESIS_TOKENS: int = _get("MAX_SYNTHESIS_TOKENS", 500, int)
MAX_INSIGHTS_TOKENS: int = _get("MAX_INSIGHTS_TOKENS", 800, int)

# ── Streamlit App ─────────────────────────────────────────────────────────────
APP_TITLE: str = _get("APP_TITLE", "Research Discovery & Synthesis Agent")
APP_ICON: str = _get("APP_ICON", "🔬")
APP_THEME: str = _get("APP_THEME", "dark")
MAX_QUERY_LENGTH: int = _get("MAX_QUERY_LENGTH", 5000, int)
DEBUG_MODE: bool = _get("DEBUG_MODE", False, bool)

# ── Derived paths (ensure directories are created at runtime) ─────────────────
SQLITE_DB_PATH = str(_ROOT / SQLITE_DB_PATH.lstrip("./"))
JSON_MEMORY_PATH = str(_ROOT / JSON_MEMORY_PATH.lstrip("./"))
VECTOR_STORE_PATH = str(_ROOT / VECTOR_STORE_PATH.lstrip("./"))

# ── Provider → model map (convenience) ───────────────────────────────────────
PROVIDER_DEFAULT_MODELS = {
    "openai": OPENAI_DEFAULT_MODEL,
    "openrouter": OPENROUTER_DEFAULT_MODEL,
    "gemini": GEMINI_DEFAULT_MODEL,
    "anthropic": ANTHROPIC_DEFAULT_MODEL,
    "ollama": OLLAMA_DEFAULT_MODEL,
}

PROVIDER_API_KEYS = {
    "openai": OPENAI_API_KEY,
    "openrouter": OPENROUTER_API_KEY,
    "gemini": GOOGLE_API_KEY,
    "anthropic": ANTHROPIC_API_KEY,
    "ollama": None,  # No key needed for local Ollama
}
