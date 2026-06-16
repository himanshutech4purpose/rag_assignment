"""Sentence-transformer embedding service."""

import asyncio

import torch
from sentence_transformers import SentenceTransformer

from app.config import Settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """Wrapper around a SentenceTransformer model that keeps CPU-bound work
    off the async event loop.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._model: SentenceTransformer | None = None

    def _load(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("Loading embedding model: %s", self._settings.embedding_model)
            self._model = SentenceTransformer(self._settings.embedding_model, device="cpu")
            logger.info("Embedding model loaded on device: cpu")
        return self._model

    def _encode(self, texts: list[str]) -> list[list[float]]:
        return self._load().encode(texts).tolist()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await asyncio.to_thread(self._encode, texts)
