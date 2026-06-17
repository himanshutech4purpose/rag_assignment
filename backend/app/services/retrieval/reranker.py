"""Cross-encoder reranking service."""

import asyncio

from sentence_transformers import CrossEncoder

from app.config import Settings
from app.logging_config import get_logger
from app.domain import RetrievedChunk

logger = get_logger(__name__)


class RerankerService:
    """Wrapper around a cross-encoder reranker."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._model: CrossEncoder | None = None

    def _load(self) -> CrossEncoder:
        if self._model is None:
            logger.info("Loading reranker model: %s", self._settings.reranker_model)
            self._model = CrossEncoder(self._settings.reranker_model)
        return self._model

    def _rerank(
        self, query: str, chunks: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []

        pairs = [(query, chunk.content) for chunk in chunks]
        scores = self._load().predict(pairs, convert_to_numpy=True)

        scored = [
            RetrievedChunk(
                id=chunk.id,
                document_name=chunk.document_name,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                score=float(score),
            )
            for chunk, score in zip(chunks, scores)
        ]
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]

    async def rerank(
        self, query: str, chunks: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        return await asyncio.to_thread(self._rerank, query, chunks, top_k)
