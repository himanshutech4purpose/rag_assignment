"""Pydantic request and response schemas for the API layer."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: UUID
    name: str
    size_bytes: int
    status: str
    created_at: datetime


class DocumentUploadResultOut(BaseModel):
    id: UUID
    name: str
    status: str
    chunks_inserted: int
    images_ignored: int = 0


class DocumentsList(BaseModel):
    documents: list[DocumentOut]


class ChunkOut(BaseModel):
    id: int
    document_name: str
    page_number: int | None
    chunk_index: int
    content: str


class UploadResponse(BaseModel):
    documents: list[DocumentUploadResultOut]


class ConversationCreate(BaseModel):
    title: str | None = None


class ConversationOut(BaseModel):
    id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class ConversationsList(BaseModel):
    conversations: list[ConversationOut]


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    sources: list[dict[str, Any]] | None
    created_at: datetime


class ConversationWithMessages(ConversationOut):
    messages: list[MessageOut]


class AskRequest(BaseModel):
    question: str
    provider: Literal["groq", "openai"] = "groq"
    model: str | None = None
    api_key: str | None = None
    system_prompt: str | None = None
    max_tokens: int | None = Field(None, ge=1, le=8192)
    history_limit: int | None = Field(None, ge=1, le=50)


class AskResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]]


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


class HealthOut(BaseModel):
    status: str
