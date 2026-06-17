"""Conversation repository: data access for conversations and messages."""

import json
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.domain import Conversation as ConversationDTO
from app.domain import Message as MessageDTO
from app.models.tables import Conversation as ConversationORM
from app.models.tables import Message as MessageORM


async def create(session: AsyncSession, title: str | None) -> ConversationDTO:
    conversation = ConversationORM(title=title)
    session.add(conversation)
    await session.flush()
    await session.refresh(conversation)
    return _to_conversation(conversation)


async def list_all(session: AsyncSession) -> list[ConversationDTO]:
    result = await session.execute(
        select(ConversationORM).order_by(ConversationORM.updated_at.desc())
    )
    return [_to_conversation(c) for c in result.scalars().all()]


async def get(session: AsyncSession, conversation_id: UUID) -> ConversationDTO:
    conversation = await session.get(ConversationORM, conversation_id)
    if conversation is None:
        raise NotFoundError("Conversation", str(conversation_id))
    return _to_conversation(conversation)


async def exists(session: AsyncSession, conversation_id: UUID) -> bool:
    result = await session.execute(
        select(ConversationORM.id).where(ConversationORM.id == conversation_id)
    )
    return result.scalar_one_or_none() is not None


async def delete(session: AsyncSession, conversation_id: UUID) -> None:
    conversation = await session.get(ConversationORM, conversation_id)
    if conversation is None:
        raise NotFoundError("Conversation", str(conversation_id))
    await session.delete(conversation)


async def update_title(
    session: AsyncSession, conversation_id: UUID, title: str
) -> None:
    conversation = await session.get(ConversationORM, conversation_id)
    if conversation is None:
        raise NotFoundError("Conversation", str(conversation_id))
    conversation.title = title


async def touch(session: AsyncSession, conversation_id: UUID) -> None:
    conversation = await session.get(ConversationORM, conversation_id)
    if conversation is None:
        raise NotFoundError("Conversation", str(conversation_id))
    conversation.updated_at = func.now()


async def add_message(
    session: AsyncSession,
    conversation_id: UUID,
    role: str,
    content: str,
    sources: list[dict[str, Any]] | None = None,
    debug_context: dict[str, Any] | None = None,
) -> MessageDTO:
    message = MessageORM(
        conversation_id=conversation_id,
        role=role,
        content=content,
        sources=sources,
        debug_context=debug_context,
    )
    session.add(message)
    await session.flush()
    await session.refresh(message)
    return _to_message(message)


async def get_messages(
    session: AsyncSession, conversation_id: UUID
) -> list[MessageDTO]:
    result = await session.execute(
        select(MessageORM)
        .where(MessageORM.conversation_id == conversation_id)
        .order_by(MessageORM.id.asc())
    )
    return [_to_message(m) for m in result.scalars().all()]


async def recent_messages(
    session: AsyncSession, conversation_id: UUID, limit: int
) -> list[MessageDTO]:
    result = await session.execute(
        select(MessageORM)
        .where(MessageORM.conversation_id == conversation_id)
        .order_by(MessageORM.id.desc())
        .limit(limit)
    )
    messages = [_to_message(m) for m in result.scalars().all()]
    return list(reversed(messages))


async def get_message(
    session: AsyncSession, conversation_id: UUID, message_id: int
) -> MessageDTO | None:
    """Return a single message belonging to a conversation, or None."""
    result = await session.execute(
        select(MessageORM)
        .where(MessageORM.id == message_id)
        .where(MessageORM.conversation_id == conversation_id)
    )
    message = result.scalar_one_or_none()
    if message is None:
        return None
    return _to_message(message)


def _to_conversation(conversation: ConversationORM) -> ConversationDTO:
    return ConversationDTO(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _to_message(message: MessageORM) -> MessageDTO:
    sources = message.sources
    if isinstance(sources, str):
        sources = json.loads(sources)
    debug_context = message.debug_context
    if isinstance(debug_context, str):
        debug_context = json.loads(debug_context)
    return MessageDTO(
        id=message.id,
        role=message.role,
        content=message.content,
        sources=sources,
        debug_context=debug_context,
        created_at=message.created_at,
    )
