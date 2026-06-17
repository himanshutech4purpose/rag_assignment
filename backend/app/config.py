"""Application settings and configuration."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # LLM providers
    groq_api_key: str
    openai_api_key: str | None = None

    # Default models
    llm_model: str = "llama-3.1-8b-instant"  # default Groq model
    openai_model: str = "gpt-4o-mini"  # default OpenAI model

    # Infrastructure
    database_url: str
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10
    db_command_timeout: int = 60

    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket_name: str = "documents"
    minio_use_ssl: bool = False

    # Embeddings & chunking
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size: int = 500
    chunk_overlap: int = 100

    # Retrieval
    top_k: int = 5
    semantic_top_k: int = 40
    lexical_top_k: int = 40
    rerank_top_k: int = 8
    rrf_k: int = 60
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Conversation context
    history_limit: int = 2

    # Upload limits
    max_upload_file_size: int = 10 * 1024 * 1024
    max_upload_files: int = 3

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    # Required fields are populated from environment variables / .env.
    return Settings()  # type: ignore[call-arg]
