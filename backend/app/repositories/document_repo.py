"""Document repository: data access for the `documents` table."""

from uuid import UUID

import asyncpg

from app.exceptions import NotFoundError
from app.models.domain import Document


async def create(
    conn: asyncpg.Connection,
    document_id: UUID,
    name: str,
    size_bytes: int,
    minio_object: str,
    status: str,
) -> Document:
    row = await conn.fetchrow(
        """
        INSERT INTO documents (id, name, size_bytes, minio_object, status)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, name, size_bytes, status, minio_object, created_at
        """,
        document_id,
        name,
        size_bytes,
        minio_object,
        status,
    )
    return _to_domain(row)


async def update_status(
    conn: asyncpg.Connection, document_id: UUID, status: str
) -> None:
    await conn.execute(
        "UPDATE documents SET status = $1 WHERE id = $2",
        status,
        document_id,
    )


async def list_all(conn: asyncpg.Connection) -> list[Document]:
    rows = await conn.fetch(
        "SELECT id, name, size_bytes, status, minio_object, created_at "
        "FROM documents ORDER BY created_at DESC"
    )
    return [_to_domain(r) for r in rows]


async def get(conn: asyncpg.Connection, document_id: UUID) -> Document:
    row = await conn.fetchrow(
        "SELECT id, name, size_bytes, status, minio_object, created_at "
        "FROM documents WHERE id = $1",
        document_id,
    )
    if not row:
        raise NotFoundError("Document", str(document_id))
    return _to_domain(row)


async def get_object_name(conn: asyncpg.Connection, document_id: UUID) -> str:
    row = await conn.fetchrow(
        "SELECT minio_object FROM documents WHERE id = $1", document_id
    )
    if not row:
        raise NotFoundError("Document", str(document_id))
    return row["minio_object"]


async def delete(conn: asyncpg.Connection, document_id: UUID) -> None:
    result = await conn.execute("DELETE FROM documents WHERE id = $1", document_id)
    if result == "DELETE 0":
        raise NotFoundError("Document", str(document_id))


def _to_domain(row: asyncpg.Record) -> Document:
    return Document(
        id=row["id"],
        name=row["name"],
        size_bytes=row["size_bytes"],
        status=row["status"],
        minio_object=row["minio_object"],
        created_at=row["created_at"],
    )
