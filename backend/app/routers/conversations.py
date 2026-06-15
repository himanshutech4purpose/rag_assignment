import json
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from app.database import get_pool
from app.models.schemas import (
    AskRequest,
    AskResponse,
    ConversationCreate,
    ConversationOut,
    ConversationWithMessages,
    ConversationsList,
)
from app.services.embeddings import embed
from app.services.llm import answer_question, stream_answer
from app.services.vector_store import has_chunks, search_chunks

router = APIRouter()


@router.post("/conversations", response_model=ConversationOut, status_code=201)
async def create_conversation(body: ConversationCreate):
    pool = get_pool()
    title = body.title or "New conversation"
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO conversations (title, updated_at)
            VALUES ($1, NOW())
            RETURNING id, title, created_at, updated_at
            """,
            title,
        )
    return dict(row)


@router.get("/conversations", response_model=ConversationsList)
async def list_conversations():
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
        )
    return {"conversations": [dict(r) for r in rows]}


@router.get("/conversations/{conversation_id}", response_model=ConversationWithMessages)
async def get_conversation(conversation_id: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        conv = await conn.fetchrow(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = $1",
            conversation_id,
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages = await conn.fetch(
            "SELECT id, role, content, sources, created_at FROM messages WHERE conversation_id = $1 ORDER BY id ASC",
            conversation_id,
        )
    return {**dict(conv), "messages": [dict(m) for m in messages]}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM conversations WHERE id = $1", conversation_id
        )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": "Conversation deleted successfully"}


@router.post("/conversations/{conversation_id}/ask", response_model=AskResponse)
async def ask_question(conversation_id: str, body: AskRequest):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    pool = get_pool()
    async with pool.acquire() as conn:
        conv = await conn.fetchrow(
            "SELECT id FROM conversations WHERE id = $1", conversation_id
        )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if not await has_chunks(pool):
        raise HTTPException(
            status_code=400, detail="Upload documents before asking questions"
        )

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES ($1, 'user', $2)",
            conversation_id,
            body.question,
        )

        history = await conn.fetch(
            """
            SELECT role, content FROM messages
            WHERE conversation_id = $1
            ORDER BY id DESC
            LIMIT 10
            """,
            conversation_id,
        )
    history = list(reversed(history))

    query_embedding = embed([body.question])[0]
    chunks = await search_chunks(pool, query_embedding, settings.top_k)
    chunks = [dict(c) for c in chunks]

    answer = answer_question(body.question, chunks, history)

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO messages (conversation_id, role, content, sources) VALUES ($1, 'assistant', $2, $3)",
            conversation_id,
            answer,
            json.dumps(chunks),
        )
        await conn.execute(
            "UPDATE conversations SET updated_at = NOW() WHERE id = $1", conversation_id
        )

    return {"answer": answer, "sources": chunks}


@router.post("/conversations/{conversation_id}/ask/stream")
async def ask_stream(conversation_id: str, body: AskRequest):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    pool = get_pool()
    async with pool.acquire() as conn:
        conv = await conn.fetchrow(
            "SELECT id FROM conversations WHERE id = $1", conversation_id
        )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if not await has_chunks(pool):
        raise HTTPException(
            status_code=400, detail="Upload documents before asking questions"
        )

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES ($1, 'user', $2)",
            conversation_id,
            body.question,
        )

        history = await conn.fetch(
            """
            SELECT role, content FROM messages
            WHERE conversation_id = $1
            ORDER BY id DESC
            LIMIT 10
            """,
            conversation_id,
        )
    history = list(reversed(history))

    query_embedding = embed([body.question])[0]
    chunks = await search_chunks(pool, query_embedding, settings.top_k)
    chunks = [dict(c) for c in chunks]

    async def event_generator():
        answer_parts = []
        try:
            async for token in stream_answer(body.question, chunks, history):
                answer_parts.append(token)
                yield f"data: {token}\n\n"

            answer = "".join(answer_parts)
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO messages (conversation_id, role, content, sources) VALUES ($1, 'assistant', $2, $3)",
                    conversation_id,
                    answer,
                    json.dumps(chunks),
                )
                await conn.execute(
                    "UPDATE conversations SET updated_at = NOW() WHERE id = $1",
                    conversation_id,
                )

            sources = json.dumps(chunks)
            yield f"event: sources\ndata: {sources}\n\n"
            yield "data: [DONE]\n\n"
        except Exception:
            yield "event: error\ndata: {\"error\": \"LLM service temporarily unavailable\"}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
