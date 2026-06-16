"""Document ingestion pipeline: parse, chunk, embed, and persist."""

import asyncio
import dataclasses
import uuid

import asyncpg

from app.config import Settings
from app.database import transaction
from app.logging_config import get_logger
from app.models.domain import Chunk, DocumentUploadResult
from app.repositories import chunk_repo, document_repo
from app.services.chunker import split_text
from app.services.embeddings import EmbeddingService
from app.services.pdf_parser import extract_text
from app.services.storage import StorageService

logger = get_logger(__name__)


class IngestionService:
    """Orchestrates the end-to-end document upload and indexing pipeline."""

    def __init__(
        self,
        settings: Settings,
        storage_service: StorageService,
        embedding_service: EmbeddingService,
    ):
        self._settings = settings
        self._storage = storage_service
        self._embeddings = embedding_service

    async def ingest(
        self,
        filename: str,
        content: bytes,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> DocumentUploadResult:
        document_id = uuid.uuid4()
        object_name = f"{document_id}_{filename}"
        effective_chunk_size = chunk_size or self._settings.chunk_size
        effective_chunk_overlap = chunk_overlap or self._settings.chunk_overlap

        await self._storage.upload(object_name, content)

        try:
            async with transaction() as conn:
                await document_repo.create(
                    conn,
                    document_id=document_id,
                    name=filename,
                    size_bytes=len(content),
                    minio_object=object_name,
                    status="processing",
                )

                pages, images_ignored = await self._extract_pages(content)
                chunks = self._build_chunks(
                    document_id, filename, pages, effective_chunk_size, effective_chunk_overlap
                )

                if chunks:
                    embeddings = await self._embeddings.embed([c.content for c in chunks])
                    chunks = [
                        dataclasses.replace(chunk, embedding=embedding)
                        for chunk, embedding in zip(chunks, embeddings)
                    ]
                    await chunk_repo.insert_many(conn, chunks)

                await document_repo.update_status(conn, document_id, "indexed")

            logger.info(
                "Ingested document %s with %d chunks, %d image(s) ignored",
                document_id,
                len(chunks),
                images_ignored,
            )
            return DocumentUploadResult(
                id=document_id,
                name=filename,
                status="indexed",
                chunks_inserted=len(chunks),
                images_ignored=images_ignored,
            )

        except Exception:
            logger.exception("Ingestion failed for %s; cleaning up storage", document_id)
            try:
                await self._storage.delete(object_name)
            except Exception:
                logger.exception("Failed to clean up object %s after ingestion error", object_name)
            raise

    async def delete_document(self, conn: asyncpg.Connection, document_id: uuid.UUID) -> None:
        """Delete a document and its stored object.

        Storage is deleted after the database transaction succeeds so that a
        failed DB delete does not leave an orphaned database record.
        """
        object_name = await document_repo.get_object_name(conn, document_id)
        await document_repo.delete(conn, document_id)
        await self._storage.delete(object_name)

    async def _extract_pages(self, content: bytes) -> tuple[list[dict], int]:
        return await asyncio.to_thread(extract_text, content)

    def _build_chunks(
        self,
        document_id: uuid.UUID,
        filename: str,
        pages: list[dict],
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        chunk_index = 0
        for page in pages:
            page_text = page.get("text") or ""
            if not page_text.strip():
                continue
            split_chunks = split_text(page_text, chunk_size, chunk_overlap)
            for text_chunk in split_chunks:
                if not text_chunk.strip():
                    continue
                chunks.append(
                    Chunk(
                        document_id=document_id,
                        document_name=filename,
                        page_number=page["page_number"],
                        chunk_index=chunk_index,
                        content=text_chunk,
                    )
                )
                chunk_index += 1
        return chunks
