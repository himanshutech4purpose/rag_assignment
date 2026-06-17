"""Chunk repository: data access for ``document_chunks`` and hybrid search."""

from uuid import UUID

from sqlalchemy import delete, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.domain import Chunk, RetrievedChunk
from app.models.tables import DocumentChunk as DocumentChunkORM


def _format_vector(embedding: list[float]) -> str:
    return "[" + ",".join(str(v) for v in embedding) + "]"


async def insert_many(session: AsyncSession, chunks: list[Chunk]) -> int:
    if not chunks:
        return 0

    values = [
        {
            "document_id": chunk.document_id,
            "document_name": chunk.document_name,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "embedding": chunk.embedding,
        }
        for chunk in chunks
    ]

    await session.execute(insert(DocumentChunkORM), values)
    return len(chunks)


async def semantic_search(
    session: AsyncSession, query_embedding: list[float], top_k: int
) -> list[RetrievedChunk]:
    sql = text("""
        SELECT id, document_name, page_number, chunk_index, content,
               1 - (embedding <=> (:embedding)::vector) AS score
        FROM document_chunks
        ORDER BY embedding <=> (:embedding)::vector
        LIMIT :limit
    """)
    result = await session.execute(
        sql,
        {
            "embedding": _format_vector(query_embedding),
            "limit": top_k,
        },
    )
    return [_to_retrieved(row) for row in result.mappings().all()]


async def lexical_search(
    session: AsyncSession, query_text: str, top_k: int
) -> list[RetrievedChunk]:
    sql = text("""
        SELECT id, document_name, page_number, chunk_index, content,
               ts_rank_cd(search_vector, plainto_tsquery('english', :query), 32) AS score
        FROM document_chunks
        WHERE search_vector @@ plainto_tsquery('english', :query)
        ORDER BY score DESC
        LIMIT :limit
    """)
    result = await session.execute(
        sql,
        {
            "query": query_text,
            "limit": top_k,
        },
    )
    return [_to_retrieved(row) for row in result.mappings().all()]


async def has_any(session: AsyncSession) -> bool:
    result = await session.execute(
        select(DocumentChunkORM.id).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def get_by_document(
    session: AsyncSession, document_id: UUID
) -> list[RetrievedChunk]:
    result = await session.execute(
        select(DocumentChunkORM)
        .where(DocumentChunkORM.document_id == document_id)
        .order_by(DocumentChunkORM.chunk_index)
    )
    return [
        RetrievedChunk(
            id=chunk.id,
            document_name=chunk.document_name,
            page_number=chunk.page_number,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            score=1.0,
        )
        for chunk in result.scalars().all()
    ]


async def delete_by_document(session: AsyncSession, document_id: UUID) -> None:
    await session.execute(
        delete(DocumentChunkORM).where(DocumentChunkORM.document_id == document_id)
    )


def fuse_rrf(
    semantic_chunks: list[RetrievedChunk],
    lexical_chunks: list[RetrievedChunk],
) -> list[RetrievedChunk]:
    """Combine two ranked lists using Reciprocal Rank Fusion."""
    k = get_settings().rrf_k
    fused: dict[int, RetrievedChunk] = {}

    for rank, chunk in enumerate(semantic_chunks, start=1):
        existing = fused.get(chunk.id)
        if existing is None:
            fused[chunk.id] = RetrievedChunk(
                id=chunk.id,
                document_name=chunk.document_name,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                score=1.0 / (k + rank),
            )
        else:
            existing.score += 1.0 / (k + rank)

    for rank, chunk in enumerate(lexical_chunks, start=1):
        existing = fused.get(chunk.id)
        if existing is None:
            fused[chunk.id] = RetrievedChunk(
                id=chunk.id,
                document_name=chunk.document_name,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                score=1.0 / (k + rank),
            )
        else:
            existing.score += 1.0 / (k + rank)

    return sorted(fused.values(), key=lambda x: x.score, reverse=True)


def _to_retrieved(row: dict) -> RetrievedChunk:
    return RetrievedChunk(
        id=row["id"],
        document_name=row["document_name"],
        page_number=row["page_number"],
        chunk_index=row["chunk_index"],
        content=row["content"],
        score=row["score"],
    )
