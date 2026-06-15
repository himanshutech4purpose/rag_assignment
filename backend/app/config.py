from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM providers
    groq_api_key: str
    openai_api_key: str | None = None

    # Default models
    llm_model: str = "llama-3.1-8b-instant"  # default Groq model
    openai_model: str = "gpt-4o-mini"  # default OpenAI model

    # Infrastructure
    database_url: str
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
    semantic_top_k: int = 20
    lexical_top_k: int = 20
    rerank_top_k: int = 5
    rrf_k: int = 60
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"


settings = Settings()
