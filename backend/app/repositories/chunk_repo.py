"""Chunk repository: data access for `document_chunks` and hybrid search."""

from uuid import UUID

import asyncpg

from app.config import get_settings
from app.models.domain import Chunk, RetrievedChunk


def _format_vector(embedding: list[float]) -> str:
    return "[" + ",".join(str(v) for v in embedding) + "]"


async def insert_many(conn: asyncpg.Connection, chunks: list[Chunk]) -> int:
    if not chunks:
        return 0

    sql = """
        INSERT INTO document_chunks
            (document_id, document_name, page_number, chunk_index, content, embedding)
        VALUES ($1, $2, $3, $4, $5, $6::vector)
    """
    await conn.executemany(
        sql,
        [
            (
                c.document_id,
                c.document_name,
                c.page_number,
                c.chunk_index,
                c.content,
                _format_vector(c.embedding) if c.embedding else None,
            )
            for c in chunks
        ],
    )
    return len(chunks)


async def semantic_search(
    conn: asyncpg.Connection, query_embedding: list[float], top_k: int
) -> list[RetrievedChunk]:
    sql = """
        SELECT id, document_name, page_number, chunk_index, content,
               1 - (embedding <=> $1::vector) AS score
        FROM document_chunks
        ORDER BY embedding <=> $1::vector
        LIMIT $2
    """
    rows = await conn.fetch(sql, _format_vector(query_embedding), top_k)
    return [_to_retrieved(r) for r in rows]


async def lexical_search(
    conn: asyncpg.Connection, query_text: str, top_k: int
) -> list[RetrievedChunk]:
    sql = """
        SELECT id, document_name, page_number, chunk_index, content,
               ts_rank_cd(search_vector, plainto_tsquery('english', $1), 32) AS score
        FROM document_chunks
        WHERE search_vector @@ plainto_tsquery('english', $1)
        ORDER BY score DESC
        LIMIT $2
    """
    rows = await conn.fetch(sql, query_text, top_k)
    return [_to_retrieved(r) for r in rows]


async def has_any(conn: asyncpg.Connection) -> bool:
    sql = "SELECT EXISTS (SELECT 1 FROM document_chunks LIMIT 1)"
    return await conn.fetchval(sql)


async def get_by_document(
    conn: asyncpg.Connection, document_id: UUID
) -> list[RetrievedChunk]:
    sql = """
        SELECT id, document_name, page_number, chunk_index, content, 1.0 AS score
        FROM document_chunks
        WHERE document_id = $1
        ORDER BY chunk_index
    """
    rows = await conn.fetch(sql, document_id)
    return [_to_retrieved(r) for r in rows]


async def delete_by_document(conn: asyncpg.Connection, document_id: UUID) -> None:
    await conn.execute("DELETE FROM document_chunks WHERE document_id = $1", document_id)


def _to_retrieved(row: asyncpg.Record) -> RetrievedChunk:
    return RetrievedChunk(
        id=row["id"],
        document_name=row["document_name"],
        page_number=row["page_number"],
        chunk_index=row["chunk_index"],
        content=row["content"],
        score=row["score"],
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
