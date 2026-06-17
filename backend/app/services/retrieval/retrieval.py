"""Retrieval service: hybrid search, RRF fusion, and reranking."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.logging_config import get_logger
from app.domain import RetrievedChunk
from app.repositories import chunk_repo
from app.services.ingestion.embeddings import EmbeddingService
from app.services.retrieval.reranker import RerankerService

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
        self, session: AsyncSession, query_text: str, top_k: int | None = None
    ) -> list[RetrievedChunk]:
        top_k = top_k or self._settings.top_k

        query_embedding = (await self._embeddings.embed([query_text]))[0]

        semantic_chunks = await chunk_repo.semantic_search(
            session, query_embedding, self._settings.semantic_top_k
        )
        lexical_chunks = await chunk_repo.lexical_search(
            session, query_text, self._settings.lexical_top_k
        )

        fused = chunk_repo.fuse_rrf(semantic_chunks, lexical_chunks)
        candidates = fused[: max(self._settings.semantic_top_k, self._settings.lexical_top_k)]

        # If the same document was uploaded multiple times, identical chunks will
        # have different IDs. Deduplicate by content so the user does not see the
        # same passage twice.
        unique_candidates = _deduplicate_chunks(candidates)

        reranked = await self._reranker.rerank(query_text, unique_candidates, top_k)
        logger.info(
            "Retrieved %d chunks for query (semantic=%d, lexical=%d, fused=%d)",
            len(reranked),
            len(semantic_chunks),
            len(lexical_chunks),
            len(fused),
        )
        return reranked

    @staticmethod
    async def has_chunks(session: AsyncSession) -> bool:
        return await chunk_repo.has_any(session)


def _deduplicate_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Return chunks with duplicate content removed, preserving order."""
    seen: set[str] = set()
    unique: list[RetrievedChunk] = []
    for chunk in chunks:
        # Normalise whitespace so tiny formatting differences do not defeat dedup.
        key = " ".join(chunk.content.split())
        if key not in seen:
            seen.add(key)
            unique.append(chunk)
    return unique
