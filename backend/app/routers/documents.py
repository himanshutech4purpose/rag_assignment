"""Document upload and management endpoints."""

import uuid
from fastapi import APIRouter, File, Query, UploadFile

from app.config import get_settings
from app.dependencies import DBSession, IngestionDep
from app.exceptions import ValidationError
from app.schemas import ChunkOut, DocumentsList, UploadResponse
from app.repositories import chunk_repo, document_repo

router = APIRouter(tags=["documents"])


@router.post("/upload", response_model=UploadResponse)
async def upload_documents(
    session: DBSession,
    ingestion_service: IngestionDep,
    files: list[UploadFile] = File(...),
    chunk_size: int | None = Query(None, ge=100, le=4000),
    chunk_overlap: int | None = Query(None, ge=0, le=1000),
):
    settings = get_settings()
    if len(files) > settings.max_upload_files:
        raise ValidationError(
            f"Maximum {settings.max_upload_files} PDF files allowed"
        )

    results = []
    for file in files:
        if not file.filename:
            raise ValidationError("All uploaded files must have a filename")

        if file.content_type != "application/pdf":
            raise ValidationError("Only PDF files are supported")

        contents = await file.read()

        if len(contents) > settings.max_upload_file_size:
            raise ValidationError(
                f"File exceeds {settings.max_upload_file_size // (1024 * 1024)}MB limit"
            )

        # Each file is ingested in its own savepoint so a failure in one file
        # does not roll back previously successful uploads.
        async with session.begin():
            result = await ingestion_service.ingest(
                session,
                filename=file.filename,
                content=contents,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        results.append(result)

    return {"documents": results}


@router.get("/documents", response_model=DocumentsList)
async def list_documents(session: DBSession):
    documents = await document_repo.list_all(session)
    return {"documents": documents}


@router.get("/documents/{document_id}/chunks", response_model=list[ChunkOut])
async def list_document_chunks(
    session: DBSession,
    document_id: str,
):
    try:
        doc_id = uuid.UUID(document_id)
    except ValueError as exc:
        raise ValidationError("Invalid document_id format") from exc

    chunks = await chunk_repo.get_by_document(session, doc_id)
    return [
        {
            "id": c.id,
            "document_name": c.document_name,
            "page_number": c.page_number,
            "chunk_index": c.chunk_index,
            "content": c.content,
        }
        for c in chunks
    ]


@router.delete("/documents/{document_id}")
async def delete_document(
    session: DBSession,
    ingestion_service: IngestionDep,
    document_id: str,
):
    try:
        doc_id = uuid.UUID(document_id)
    except ValueError as exc:
        raise ValidationError("Invalid document_id format") from exc

    await ingestion_service.delete_document(session, doc_id)
    return {"message": "Document deleted successfully"}
