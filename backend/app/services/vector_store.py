import asyncpg


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


async def search_chunks(pool: asyncpg.Pool, query_embedding: list[float], top_k: int):
    sql = """
        SELECT document_name, page_number, chunk_index, content,
               1 - (embedding <=> $1::vector) AS score
        FROM document_chunks
        ORDER BY embedding <=> $1::vector
        LIMIT $2
    """
    async with pool.acquire() as conn:
        return await conn.fetch(sql, _format_vector(query_embedding), top_k)


async def has_chunks(pool: asyncpg.Pool) -> bool:
    sql = "SELECT EXISTS (SELECT 1 FROM document_chunks LIMIT 1)"
    async with pool.acquire() as conn:
        return await conn.fetchval(sql)
