"""Retrieval service: hybrid search, RRF fusion, and reranking."""

import asyncpg

from app.config import Settings
from app.logging_config import get_logger
from app.models.domain import RetrievedChunk
from app.repositories import chunk_repo
from app.services.embeddings import EmbeddingService
from app.services.reranker import RerankerService

logger = get_logger(__name__)


class RetrievalService:
    """Coordinates semantic + lexical search, RRF fusion, and reranking."""

    def __init__(
        self,
        settings: Settings,
        embedding_service: EmbeddingService,
        reranker_service: RerankerService,
    ):
        self._settings = settings
        self._embeddings = embedding_service
        self._reranker = reranker_service

    async def search(
        self, conn: asyncpg.Connection, query_text: str, top_k: int | None = None
    ) -> list[RetrievedChunk]:
        top_k = top_k or self._settings.top_k

        query_embedding = (await self._embeddings.embed([query_text]))[0]

        semantic_chunks = await chunk_repo.semantic_search(
            conn, query_embedding, self._settings.semantic_top_k
        )
        lexical_chunks = await chunk_repo.lexical_search(
            conn, query_text, self._settings.lexical_top_k
        )

        fused = chunk_repo.fuse_rrf(semantic_chunks, lexical_chunks)
        candidates = fused[: max(self._settings.semantic_top_k, self._settings.lexical_top_k)]

        reranked = await self._reranker.rerank(query_text, candidates, top_k)
        logger.info(
            "Retrieved %d chunks for query (semantic=%d, lexical=%d, fused=%d)",
            len(reranked),
            len(semantic_chunks),
            len(lexical_chunks),
            len(fused),
        )
        return reranked

    @staticmethod
    async def has_chunks(conn: asyncpg.Connection) -> bool:
        return await chunk_repo.has_any(conn)
