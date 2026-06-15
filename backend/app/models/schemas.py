from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: UUID
    name: str
    size_bytes: int
    status: str
    created_at: datetime


class DocumentUploadResult(BaseModel):
    id: UUID
    name: str
    status: str
    chunks_inserted: int


class DocumentsList(BaseModel):
    documents: list[DocumentOut]


class UploadResponse(BaseModel):
    documents: list[DocumentUploadResult]


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


class AskResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]]


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
