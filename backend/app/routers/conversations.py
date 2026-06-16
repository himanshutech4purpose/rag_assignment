"""Conversation and Q&A endpoints."""

import json
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.logging_config import get_logger
from app.dependencies import (
    ConversationServiceDep,
    DBConnection,
    LLMDep,
    RetrievalDep,
)
from app.exceptions import LLMServiceError, ValidationError
from app.models.schemas import (
    AskRequest,
    AskResponse,
    ConversationCreate,
    ConversationOut,
    ConversationsList,
    ConversationWithMessages,
)
from app.repositories import conversation_repo

logger = get_logger(__name__)
router = APIRouter(tags=["conversations"])


@router.post("/conversations", response_model=ConversationOut, status_code=201)
async def create_conversation(
    conn: DBConnection,
    conversation_service: ConversationServiceDep,
    body: ConversationCreate,
):
    conversation = await conversation_service.create(conn, body.title)
    return conversation


@router.get("/conversations", response_model=ConversationsList)
async def list_conversations(
    conn: DBConnection,
    conversation_service: ConversationServiceDep,
):
    conversations = await conversation_service.list_all(conn)
    return {"conversations": conversations}


@router.get("/conversations/{conversation_id}", response_model=ConversationWithMessages)
async def get_conversation(
    conn: DBConnection,
    conversation_service: ConversationServiceDep,
    conversation_id: UUID,
):
    conversation, messages = await conversation_service.get_with_messages(
        conn, conversation_id
    )
    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "messages": messages,
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conn: DBConnection,
    conversation_service: ConversationServiceDep,
    conversation_id: UUID,
):
    await conversation_service.delete(conn, conversation_id)
    return {"message": "Conversation deleted successfully"}


@router.post("/conversations/{conversation_id}/ask", response_model=AskResponse)
async def ask_question(
    conn: DBConnection,
    conversation_service: ConversationServiceDep,
    retrieval_service: RetrievalDep,
    llm_service: LLMDep,
    conversation_id: UUID,
    body: AskRequest,
):
    if not await retrieval_service.has_chunks(conn):
        raise ValidationError("Upload documents before asking questions")

    history = await conversation_service.add_user_message(
        conn, conversation_id, body.question, body.history_limit
    )
    chunks = await retrieval_service.search(conn, body.question)

    answer = await llm_service.answer(
        question=body.question,
        chunks=chunks,
        history=history,
        provider=body.provider,
        model=body.model,
        api_key=body.api_key,
        system_prompt=body.system_prompt,
        max_tokens=body.max_tokens,
    )

    sources = [c.to_dict() for c in chunks]
    await conversation_service.save_assistant_message(
        conn, conversation_id, answer, sources
    )

    return {"answer": answer, "sources": sources}


@router.post("/conversations/{conversation_id}/ask/stream")
async def ask_stream(
    conn: DBConnection,
    conversation_service: ConversationServiceDep,
    retrieval_service: RetrievalDep,
    llm_service: LLMDep,
    conversation_id: UUID,
    body: AskRequest,
):
    if not await retrieval_service.has_chunks(conn):
        raise ValidationError("Upload documents before asking questions")

    history = await conversation_service.add_user_message(
        conn, conversation_id, body.question, body.history_limit
    )
    chunks = await retrieval_service.search(conn, body.question)
    sources = [c.to_dict() for c in chunks]

    async def event_generator():
        answer_parts = []
        try:
            async for token in llm_service.stream_answer(
                question=body.question,
                chunks=chunks,
                history=history,
                provider=body.provider,
                model=body.model,
                api_key=body.api_key,
                system_prompt=body.system_prompt,
                max_tokens=body.max_tokens,
            ):
                answer_parts.append(token)
                yield f"data: {token}\n\n"

            answer = "".join(answer_parts)
            async with conn.transaction():
                await conversation_repo.add_message(
                    conn, conversation_id, "assistant", answer, sources
                )
                await conversation_repo.touch(conn, conversation_id)

            yield f"event: sources\ndata: {json.dumps(sources)}\n\n"
            yield "data: [DONE]\n\n"
        except LLMServiceError:
            yield "event: error\ndata: {\"error\": \"LLM service temporarily unavailable\"}\n\n"
        except Exception:
            logger.exception("Unexpected error during streaming (conversation_id=%s)", conversation_id)
            yield "event: error\ndata: {\"error\": \"An unexpected error occurred\"}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
