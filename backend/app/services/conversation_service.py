"""Conversation domain service: title generation, history, and persistence."""

import json
from typing import Any
from uuid import UUID

import asyncpg

from app.config import Settings
from app.exceptions import NotFoundError, ValidationError
from app.logging_config import get_logger
from app.models.domain import Conversation, Message
from app.repositories import conversation_repo

logger = get_logger(__name__)

DEFAULT_CONVERSATION_TITLE = "New conversation"
MAX_TITLE_LENGTH = 40


class ConversationService:
    """Encapsulates conversation business logic."""

    def __init__(self, settings: Settings):
        self._settings = settings

    @staticmethod
    def generate_title(question: str) -> str:
        """Generate a short title from the first few words of the user's question."""
        cleaned = question.strip().replace("\n", " ")
        words = cleaned.split()
        if not words:
            return DEFAULT_CONVERSATION_TITLE

        candidate = " ".join(words[:6])
        if len(candidate) > MAX_TITLE_LENGTH:
            candidate = candidate[:MAX_TITLE_LENGTH].rsplit(" ", 1)[0] + "..."
        elif len(words) > 6:
            candidate += "..."
        return candidate

    async def create(self, conn: asyncpg.Connection, title: str | None) -> Conversation:
        effective_title = title or DEFAULT_CONVERSATION_TITLE
        return await conversation_repo.create(conn, effective_title)

    async def list_all(self, conn: asyncpg.Connection) -> list[Conversation]:
        return await conversation_repo.list_all(conn)

    async def get_with_messages(
        self, conn: asyncpg.Connection, conversation_id: UUID
    ) -> tuple[Conversation, list[Message]]:
        conversation = await conversation_repo.get(conn, conversation_id)
        messages = await conversation_repo.get_messages(conn, conversation_id)
        return conversation, messages

    async def delete(self, conn: asyncpg.Connection, conversation_id: UUID) -> None:
        await conversation_repo.delete(conn, conversation_id)

    async def maybe_update_title(
        self, conn: asyncpg.Connection, conversation_id: UUID, question: str
    ) -> None:
        conversation = await conversation_repo.get(conn, conversation_id)
        if conversation.title == DEFAULT_CONVERSATION_TITLE:
            new_title = self.generate_title(question)
            await conversation_repo.update_title(conn, conversation_id, new_title)

    async def add_user_message(
        self,
        conn: asyncpg.Connection,
        conversation_id: UUID,
        question: str,
        history_limit: int | None = None,
    ) -> list[Message]:
        if not question.strip():
            raise ValidationError("Question cannot be empty")

        if not await conversation_repo.exists(conn, conversation_id):
            raise NotFoundError("Conversation", str(conversation_id))

        limit = history_limit or self._settings.history_limit
        await conversation_repo.add_message(conn, conversation_id, "user", question)
        await self.maybe_update_title(conn, conversation_id, question)
        history = await conversation_repo.recent_messages(conn, conversation_id, limit)
        return history

    async def save_assistant_message(
        self,
        conn: asyncpg.Connection,
        conversation_id: UUID,
        answer: str,
        sources: list[dict[str, Any]],
    ) -> None:
        await conversation_repo.add_message(
            conn, conversation_id, "assistant", answer, sources
        )
        await conversation_repo.touch(conn, conversation_id)
