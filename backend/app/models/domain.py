"""Internal domain models. These are separate from API schemas to allow
flexibility in the service/repository layer without leaking implementation
 details to the HTTP contract.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class Chunk:
    document_id: UUID
    document_name: str
    page_number: int
    chunk_index: int
    content: str
    embedding: list[float] | None = None


@dataclass
class RetrievedChunk:
    id: int
    document_name: str
    page_number: int | None
    chunk_index: int
    content: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_name": self.document_name,
            "page_number": self.page_number,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "score": self.score,
        }


@dataclass(frozen=True)
class Message:
    id: int | None
    role: str
    content: str
    sources: list[dict[str, Any]] | None
    created_at: datetime | None = None


@dataclass(frozen=True)
class Conversation:
    id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Document:
    id: UUID
    name: str
    size_bytes: int
    status: str
    minio_object: str
    created_at: datetime


@dataclass(frozen=True)
class DocumentUploadResult:
    id: UUID
    name: str
    status: str
    chunks_inserted: int
    images_ignored: int = 0
