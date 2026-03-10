import os

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL", "postgresql://postgres:postgres@supabase-db:5432/postgres")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
CHAT_MODEL = os.getenv("CHAT_MODEL", "llama3.2:3b")
VECTOR_DIMENSION = int(os.getenv("VECTOR_DIMENSION", "768"))
REDIS_URL = os.getenv("REDIS_URL", "redis://ai-redis:6379")
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://ai-searxng:8080")

RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
RAG_THRESHOLD = float(os.getenv("RAG_THRESHOLD", "0.7"))
RAG_KEYWORD_WEIGHT = float(os.getenv("RAG_KEYWORD_WEIGHT", "0.3"))

LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://langfuse:3000")
