"""
Centralised configuration for BantenPedia.
All environment variables are read here and exported as typed constants.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

# ── Gemini ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str   = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
# Newer options (may need allowlist or may be under load):
# "gemini-3.8-flash" — latest, but high demand / may 503
# "gemini-2.5-flash" — unavailable to new API keys

# ── Embedding ─────────────────────────────────────────────────────────────────
EMBEDDING_MODEL: str     = os.getenv("EMBEDDING_MODEL", "gemini-embedding-2")
EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "768"))

# ── Retrieval defaults ────────────────────────────────────────────────────────
DEFAULT_TOP_K: int              = int(os.getenv("DEFAULT_TOP_K", "5"))
SIMILARITY_THRESHOLD: float     = float(os.getenv("SIMILARITY_THRESHOLD", "0.70"))

# ── Chunking ──────────────────────────────────────────────────────────────────
CHUNK_SIZE_TOKENS: int  = int(os.getenv("CHUNK_SIZE_TOKENS", "750"))
CHUNK_OVERLAP_TOKENS: int = int(os.getenv("CHUNK_OVERLAP_TOKENS", "100"))

# ── Ingestion ─────────────────────────────────────────────────────────────────
EMBEDDING_BATCH_SIZE: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "20"))

# ── Validation ────────────────────────────────────────────────────────────────
_required = {
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_KEY": SUPABASE_KEY,
    "GEMINI_API_KEY": GEMINI_API_KEY,
}

def validate_config() -> None:
    """Raise ValueError if any required env var is missing."""
    missing = [k for k, v in _required.items() if not v]
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )
