from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    groq_api_key: str
    database_url: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket_name: str = "documents"
    minio_use_ssl: bool = False
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    llm_model: str = "llama-3.1-8b-instant"
    chunk_size: int = 500
    chunk_overlap: int = 100
    top_k: int = 5


settings = Settings()
