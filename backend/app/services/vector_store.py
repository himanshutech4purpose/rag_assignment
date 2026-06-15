import asyncpg

from app.config import settings
from app.services.embeddings import embed
from app.services.reranker import rerank


def _format_vector(embedding: list[float]) -> str:
    return "[" + ",".join(str(v) for v in embedding) + "]"


async def insert_chunks(pool: asyncpg.Pool, chunks: list[dict]):
    sql = """
        INSERT INTO document_chunks
            (document_id, document_name, page_number, chunk_index, content, embedding)
        VALUES ($1, $2, $3, $4, $5, $6::vector)
    """
    async with pool.acquire() as conn:
        await conn.executemany(
            sql,
            [
                (
                    c["document_id"],
                    c["document_name"],
                    c["page_number"],
                    c["chunk_index"],
                    c["content"],
                    _format_vector(c["embedding"]),
                )
                for c in chunks
            ],
        )


async def semantic_search(
    pool: asyncpg.Pool, query_embedding: list[float], top_k: int
) -> list[dict]:
    sql = """
        SELECT id, document_name, page_number, chunk_index, content,
               1 - (embedding <=> $1::vector) AS score
        FROM document_chunks
        ORDER BY embedding <=> $1::vector
        LIMIT $2
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, _format_vector(query_embedding), top_k)
    return [dict(r) for r in rows]


async def lexical_search(pool: asyncpg.Pool, query_text: str, top_k: int) -> list[dict]:
    sql = """
        SELECT id, document_name, page_number, chunk_index, content,
               ts_rank_cd(search_vector, plainto_tsquery('english', $1), 32) AS score
        FROM document_chunks
        WHERE search_vector @@ plainto_tsquery('english', $1)
        ORDER BY score DESC
        LIMIT $2
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, query_text, top_k)
    return [dict(r) for r in rows]


def _fuse_rrf(semantic_chunks: list[dict], lexical_chunks: list[dict]) -> list[dict]:
    """Combine two ranked lists using Reciprocal Rank Fusion."""
    k = settings.rrf_k
    fused: dict[int, dict] = {}

    for rank, chunk in enumerate(semantic_chunks, start=1):
        chunk_id = chunk["id"]
        if chunk_id not in fused:
            fused[chunk_id] = dict(chunk)
            fused[chunk_id]["rrf_score"] = 0.0
        fused[chunk_id]["rrf_score"] += 1.0 / (k + rank)

    for rank, chunk in enumerate(lexical_chunks, start=1):
        chunk_id = chunk["id"]
        if chunk_id not in fused:
            fused[chunk_id] = dict(chunk)
            fused[chunk_id]["rrf_score"] = 0.0
        fused[chunk_id]["rrf_score"] += 1.0 / (k + rank)

    return sorted(fused.values(), key=lambda x: x["rrf_score"], reverse=True)


async def search_chunks(
    pool: asyncpg.Pool,
    query_text: str,
    top_k: int = settings.rerank_top_k,
) -> list[dict]:
    """Hybrid search: semantic + lexical BM25-like fusion, then reranking.

    Returns the top_k chunks after reranking.
    """
    query_embedding = embed([query_text])[0]

    semantic_chunks = await semantic_search(
        pool, query_embedding, settings.semantic_top_k
    )
    lexical_chunks = await lexical_search(pool, query_text, settings.lexical_top_k)

    fused = _fuse_rrf(semantic_chunks, lexical_chunks)

    # Take enough candidates for the reranker (semantic + lexical pool size)
    candidates = fused[: max(settings.semantic_top_k, settings.lexical_top_k)]
    reranked = rerank(query_text, candidates, top_k)

    # Return a stable format expected downstream
    return [
        {
            "id": c["id"],
            "document_name": c["document_name"],
            "page_number": c["page_number"],
            "chunk_index": c["chunk_index"],
            "content": c["content"],
            "score": c["rerank_score"],
        }
        for c in reranked
    ]


async def has_chunks(pool: asyncpg.Pool) -> bool:
    sql = "SELECT EXISTS (SELECT 1 FROM document_chunks LIMIT 1)"
    async with pool.acquire() as conn:
        return await conn.fetchval(sql)
