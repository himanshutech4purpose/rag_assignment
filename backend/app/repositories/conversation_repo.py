"""Conversation repository: data access for conversations and messages."""

import json
from typing import Any
from uuid import UUID

import asyncpg

from app.exceptions import NotFoundError
from app.models.domain import Conversation, Message


async def create(conn: asyncpg.Connection, title: str | None) -> Conversation:
    row = await conn.fetchrow(
        """
        INSERT INTO conversations (title, updated_at)
        VALUES ($1, NOW())
        RETURNING id, title, created_at, updated_at
        """,
        title,
    )
    return _to_conversation(row)


async def list_all(conn: asyncpg.Connection) -> list[Conversation]:
    rows = await conn.fetch(
        "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
    )
    return [_to_conversation(r) for r in rows]


async def get(conn: asyncpg.Connection, conversation_id: UUID) -> Conversation:
    row = await conn.fetchrow(
        "SELECT id, title, created_at, updated_at FROM conversations WHERE id = $1",
        conversation_id,
    )
    if not row:
        raise NotFoundError("Conversation", str(conversation_id))
    return _to_conversation(row)


async def exists(conn: asyncpg.Connection, conversation_id: UUID) -> bool:
    row = await conn.fetchrow(
        "SELECT 1 FROM conversations WHERE id = $1", conversation_id
    )
    return row is not None


async def delete(conn: asyncpg.Connection, conversation_id: UUID) -> None:
    result = await conn.execute(
        "DELETE FROM conversations WHERE id = $1", conversation_id
    )
    if result == "DELETE 0":
        raise NotFoundError("Conversation", str(conversation_id))


async def update_title(
    conn: asyncpg.Connection, conversation_id: UUID, title: str
) -> None:
    await conn.execute(
        "UPDATE conversations SET title = $1, updated_at = NOW() WHERE id = $2",
        title,
        conversation_id,
    )


async def touch(conn: asyncpg.Connection, conversation_id: UUID) -> None:
    await conn.execute(
        "UPDATE conversations SET updated_at = NOW() WHERE id = $1", conversation_id
    )


async def add_message(
    conn: asyncpg.Connection,
    conversation_id: UUID,
    role: str,
    content: str,
    sources: list[dict[str, Any]] | None = None,
) -> Message:
    sources_json = json.dumps(sources) if sources is not None else None
    row = await conn.fetchrow(
        """
        INSERT INTO messages (conversation_id, role, content, sources)
        VALUES ($1, $2, $3, $4)
        RETURNING id, role, content, sources, created_at
        """,
        conversation_id,
        role,
        content,
        sources_json,
    )
    return _to_message(row)


async def get_messages(
    conn: asyncpg.Connection, conversation_id: UUID
) -> list[Message]:
    rows = await conn.fetch(
        """
        SELECT id, role, content, sources, created_at
        FROM messages
        WHERE conversation_id = $1
        ORDER BY id ASC
        """,
        conversation_id,
    )
    return [_to_message(r) for r in rows]


async def recent_messages(
    conn: asyncpg.Connection, conversation_id: UUID, limit: int
) -> list[Message]:
    rows = await conn.fetch(
        """
        SELECT role, content FROM messages
        WHERE conversation_id = $1
        ORDER BY id DESC
        LIMIT $2
        """,
        conversation_id,
        limit,
    )
    return [_to_message(r) for r in reversed(rows)]


def _to_conversation(row: asyncpg.Record) -> Conversation:
    return Conversation(
        id=row["id"],
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_message(row: asyncpg.Record) -> Message:
    sources = row.get("sources")
    if isinstance(sources, str):
        sources = json.loads(sources)
    return Message(
        id=row.get("id"),
        role=row["role"],
        content=row["content"],
        sources=sources,
        created_at=row.get("created_at"),
    )
