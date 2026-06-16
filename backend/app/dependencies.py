"""FastAPI dependency providers for the application."""

from typing import Annotated

import asyncpg
from fastapi import Depends, Request

from app.database import get_pool
from app.services.conversation_service import ConversationService
from app.services.embeddings import EmbeddingService
from app.services.ingestion import IngestionService
from app.services.llm import LLMService
from app.services.reranker import RerankerService
from app.services.retrieval import RetrievalService
from app.services.storage import StorageService


async def get_db_connection() -> asyncpg.Connection:
    """Yield a single database connection from the pool."""
    async with get_pool().acquire() as conn:
        yield conn


DBConnection = Annotated[asyncpg.Connection, Depends(get_db_connection)]


def _get_app_state(request: Request):
    return request.app.state


def get_storage_service(request: Request) -> StorageService:
    return request.app.state.storage_service


StorageDep = Annotated[StorageService, Depends(get_storage_service)]


def get_embedding_service(request: Request) -> EmbeddingService:
    return request.app.state.embedding_service


EmbeddingDep = Annotated[EmbeddingService, Depends(get_embedding_service)]


def get_reranker_service(request: Request) -> RerankerService:
    return request.app.state.reranker_service


RerankerDep = Annotated[RerankerService, Depends(get_reranker_service)]


def get_llm_service(request: Request) -> LLMService:
    return request.app.state.llm_service


LLMDep = Annotated[LLMService, Depends(get_llm_service)]


def get_retrieval_service(request: Request) -> RetrievalService:
    return request.app.state.retrieval_service


RetrievalDep = Annotated[RetrievalService, Depends(get_retrieval_service)]


def get_ingestion_service(request: Request) -> IngestionService:
    return request.app.state.ingestion_service


IngestionDep = Annotated[IngestionService, Depends(get_ingestion_service)]


def get_conversation_service(request: Request) -> ConversationService:
    return request.app.state.conversation_service


ConversationServiceDep = Annotated[ConversationService, Depends(get_conversation_service)]
