"""SQLAlchemy ORM models that mirror the application database schema.

These classes drive Alembic autogeneration and are also used directly by
``app.repositories`` via SQLAlchemy async sessions. They intentionally avoid
business logic and only describe tables, columns, constraints, and indexes.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Document(Base):
    """A PDF document stored in object storage."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    minio_object: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        server_default="uploaded",
    )
    created_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=False),
        server_default=sa.func.now(),
    )

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class DocumentChunk(Base):
    """A text chunk extracted from a document, with embedding and full-text vector."""

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
    )
    document_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    page_number: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    chunk_index: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(384),
        nullable=True,
    )
    created_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=False),
        server_default=sa.func.now(),
    )
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', content)", persisted=True),
        nullable=True,
    )

    document: Mapped[Document] = relationship(back_populates="chunks")

    __table_args__ = (
        Index(
            "idx_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("idx_chunks_document_id", "document_id"),
        Index(
            "idx_chunks_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )


class Conversation(Base):
    """A user conversation thread."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    title: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=False),
        server_default=sa.func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=False),
        server_default=sa.func.now(),
    )

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.id",
    )


class Message(Base):
    """A single message inside a conversation."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,
    )
    role: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    debug_context: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=False),
        server_default=sa.func.now(),
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    __table_args__ = (
        Index("idx_messages_conversation_id", "conversation_id"),
    )
