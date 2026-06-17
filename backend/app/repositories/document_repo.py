"""Document repository: data access for the ``documents`` table."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.domain import Document as DocumentDTO
from app.models.tables import Document as DocumentORM


async def create(
    session: AsyncSession,
    document_id: UUID,
    name: str,
    size_bytes: int,
    minio_object: str,
    status: str,
) -> DocumentDTO:
    document = DocumentORM(
        id=document_id,
        name=name,
        size_bytes=size_bytes,
        minio_object=minio_object,
        status=status,
    )
    session.add(document)
    await session.flush()
    await session.refresh(document)
    return _to_domain(document)


async def update_status(
    session: AsyncSession, document_id: UUID, status: str
) -> None:
    document = await session.get(DocumentORM, document_id)
    if document is None:
        raise NotFoundError("Document", str(document_id))
    document.status = status


async def list_all(session: AsyncSession) -> list[DocumentDTO]:
    result = await session.execute(
        select(DocumentORM).order_by(DocumentORM.created_at.desc())
    )
    return [_to_domain(doc) for doc in result.scalars().all()]


async def get(session: AsyncSession, document_id: UUID) -> DocumentDTO:
    document = await session.get(DocumentORM, document_id)
    if document is None:
        raise NotFoundError("Document", str(document_id))
    return _to_domain(document)


async def get_object_name(session: AsyncSession, document_id: UUID) -> str:
    result = await session.execute(
        select(DocumentORM.minio_object).where(DocumentORM.id == document_id)
    )
    object_name = result.scalar_one_or_none()
    if object_name is None:
        raise NotFoundError("Document", str(document_id))
    return object_name


async def delete(session: AsyncSession, document_id: UUID) -> None:
    document = await session.get(DocumentORM, document_id)
    if document is None:
        raise NotFoundError("Document", str(document_id))
    await session.delete(document)


def _to_domain(document: DocumentORM) -> DocumentDTO:
    return DocumentDTO(
        id=document.id,
        name=document.name,
        size_bytes=document.size_bytes,
        status=document.status,
        minio_object=document.minio_object,
        created_at=document.created_at,
    )
