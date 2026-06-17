"""Document ingestion pipeline services.

This package groups all code involved in parsing, chunking, embedding and
persisting uploaded documents. ``EmbeddingService`` lives here because it is
created during ingestion; it is also consumed by the retrieval pipeline.
"""

from app.services.ingestion.embeddings import EmbeddingService
from app.services.ingestion.ingestion import IngestionService
from app.services.ingestion.storage import StorageService

__all__ = [
    "EmbeddingService",
    "IngestionService",
    "StorageService",
]
