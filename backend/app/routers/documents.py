import uuid
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.database import get_pool
from app.models.schemas import DocumentsList, UploadResponse
from app.services.chunker import split_text
from app.services.embeddings import embed
from app.services.pdf_parser import extract_text
from app.services.storage import delete_file, upload_file
from app.services.vector_store import insert_chunks

router = APIRouter()
MAX_FILE_SIZE = 10 * 1024 * 1024


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/upload", response_model=UploadResponse)
async def upload_documents(files: list[UploadFile] = File(...)):
    if len(files) > 3:
        raise HTTPException(status_code=400, detail="Maximum 3 PDF files allowed")

    pool = get_pool()
    results = []

    for file in files:
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File exceeds 10MB limit")

        document_id = uuid.uuid4()
        object_name = f"{document_id}_{file.filename}"

        upload_file(object_name, contents, len(contents))

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO documents (id, name, size_bytes, minio_object, status)
                VALUES ($1, $2, $3, $4, 'processing')
                """,
                document_id,
                file.filename,
                len(contents),
                object_name,
            )

        pages = extract_text(contents)
        chunks = []
        chunk_index = 0
        for page in pages:
            page_text = page["text"] or ""
            if not page_text.strip():
                continue
            split_chunks = split_text(
                page_text, settings.chunk_size, settings.chunk_overlap
            )
            for text_chunk in split_chunks:
                if not text_chunk.strip():
                    continue
                chunks.append(
                    {
                        "document_id": document_id,
                        "document_name": file.filename,
                        "page_number": page["page_number"],
                        "chunk_index": chunk_index,
                        "content": text_chunk,
                    }
                )
                chunk_index += 1

        if chunks:
            embeddings = embed([c["content"] for c in chunks])
            for c, e in zip(chunks, embeddings):
                c["embedding"] = e
            await insert_chunks(pool, chunks)

        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE documents SET status = 'indexed' WHERE id = $1",
                document_id,
            )

        results.append(
            {
                "id": document_id,
                "name": file.filename,
                "status": "indexed",
                "chunks_inserted": len(chunks),
            }
        )

    return {"documents": results}


@router.get("/documents", response_model=DocumentsList)
async def list_documents():
    pool = get_pool()
    rows = await pool.fetch(
        "SELECT id, name, size_bytes, status, created_at FROM documents ORDER BY created_at DESC"
    )
    return {"documents": [dict(r) for r in rows]}


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT minio_object FROM documents WHERE id = $1", document_id
        )

    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    delete_file(row["minio_object"])

    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM documents WHERE id = $1", document_id)

    return {"message": "Document deleted successfully"}
