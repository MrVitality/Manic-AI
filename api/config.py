import logging
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All fields use the same env-var names as the old ``os.getenv`` calls so
    existing deployments keep working without changes.
    """

    # --- Core service URLs ---
    OLLAMA_URL: str = "http://ollama:11434"
    SUPABASE_DB_URL: str = ""
    REDIS_URL: str = "redis://ai-redis:6379"
    QDRANT_URL: str = "http://qdrant:6333"
    SEARXNG_URL: str = "http://ai-searxng:8080"

    # --- Model defaults ---
    # BGE-M3 produces 1024-dim embeddings. Requires: ollama pull bge-m3
    EMBEDDING_MODEL: str = "bge-m3"
    EMBEDDING_MODEL_LEGACY: str = "nomic-embed-text"  # backward compat reference
    CHAT_MODEL: str = "llama3.2:3b"
    VECTOR_DIMENSION: int = 1024

    # --- Inference backend ---
    INFERENCE_BACKEND: str = "ollama"  # "ollama", "vllm", or "openai"
    VLLM_URL: str = ""  # empty = disabled, use Ollama
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # --- RAG tuning ---
    RAG_TOP_K: int = 5
    RAG_THRESHOLD: float = 0.7
    RAG_KEYWORD_WEIGHT: float = 0.3
    RAG_CONTEXT_WINDOW: int = 4096

    # --- Langfuse observability ---
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "http://langfuse:3000"

    # --- Auth ---
    API_SECRET_KEY: str = ""

    # --- Agent ---
    AGENT_STATE_TTL_SECONDS: int = 86400  # 24 h (was hardcoded 1 h)

    # --- Rate limiting ---
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_INGEST_PER_MINUTE: int = 10

    # --- Security guardrails ---
    GUARDRAILS_ENABLED: bool = True
    PII_REDACTION_ENABLED: bool = False

    # --- CORS ---
    CORS_ORIGINS: str = ""

    @field_validator("SUPABASE_DB_URL")
    @classmethod
    def warn_default_db_credentials(cls, v: str) -> str:
        if "postgres:postgres@" in v:
            logger.warning(
                "SUPABASE_DB_URL contains default credentials (postgres:postgres). "
                "Set a strong password before deploying to production."
            )
        return v

    @field_validator("VECTOR_DIMENSION")
    @classmethod
    def dimension_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("VECTOR_DIMENSION must be a positive integer")
        return v

    @field_validator("RAG_TOP_K")
    @classmethod
    def top_k_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("RAG_TOP_K must be a positive integer")
        return v

    @field_validator("RAG_THRESHOLD")
    @classmethod
    def threshold_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("RAG_THRESHOLD must be between 0.0 and 1.0")
        return v

    @field_validator("RAG_KEYWORD_WEIGHT")
    @classmethod
    def keyword_weight_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("RAG_KEYWORD_WEIGHT must be between 0.0 and 1.0")
        return v

    def parse_cors_origins(self) -> List[str]:
        """Parse comma-separated CORS_ORIGINS into a list.

        Falls back to localhost defaults for local development.
        """
        raw = self.CORS_ORIGINS.strip()
        if raw:
            return [origin.strip() for origin in raw.split(",") if origin.strip()]
        logger.warning(
            "CORS_ORIGINS is not set -- defaulting to localhost origins. "
            "Set this environment variable in production."
        )
        return ["http://localhost:3000", "http://localhost:3006"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()

# ---------------------------------------------------------------------------
# Convenience aliases (preserves every existing ``from api.config import X``)
# ---------------------------------------------------------------------------
OLLAMA_URL = settings.OLLAMA_URL
SUPABASE_DB_URL = settings.SUPABASE_DB_URL
REDIS_URL = settings.REDIS_URL
QDRANT_URL = settings.QDRANT_URL
SEARXNG_URL = settings.SEARXNG_URL
EMBEDDING_MODEL = settings.EMBEDDING_MODEL
EMBEDDING_MODEL_LEGACY = settings.EMBEDDING_MODEL_LEGACY
CHAT_MODEL = settings.CHAT_MODEL
VECTOR_DIMENSION = settings.VECTOR_DIMENSION
RAG_TOP_K = settings.RAG_TOP_K
RAG_THRESHOLD = settings.RAG_THRESHOLD
RAG_KEYWORD_WEIGHT = settings.RAG_KEYWORD_WEIGHT
RAG_CONTEXT_WINDOW = settings.RAG_CONTEXT_WINDOW
LANGFUSE_PUBLIC_KEY = settings.LANGFUSE_PUBLIC_KEY
LANGFUSE_SECRET_KEY = settings.LANGFUSE_SECRET_KEY
LANGFUSE_HOST = settings.LANGFUSE_HOST
INFERENCE_BACKEND = settings.INFERENCE_BACKEND
VLLM_URL = settings.VLLM_URL
OPENAI_API_KEY = settings.OPENAI_API_KEY
ANTHROPIC_API_KEY = settings.ANTHROPIC_API_KEY
OPENAI_BASE_URL = settings.OPENAI_BASE_URL
