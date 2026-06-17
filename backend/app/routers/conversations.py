"""Conversation and Q&A endpoints."""

import json
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.dependencies import (
    ConversationServiceDep,
    DBSession,
    LLMDep,
    RetrievalDep,
)
from app.exceptions import LLMServiceError, NotFoundError, ValidationError
from app.logging_config import get_logger
from app.domain import Message as MessageDTO
from app.schemas import (
    AskRequest,
    AskResponse,
    ConversationCreate,
    ConversationOut,
    ConversationsList,
    ConversationWithMessages,
)
from app.repositories import conversation_repo
from app.services.llm import build_debug_context, format_context, format_history

logger = get_logger(__name__)
router = APIRouter(tags=["conversations"])


def _message_to_out(message: MessageDTO) -> dict:
    """Map a domain Message to the ConversationWithMessages output shape."""
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "sources": message.sources,
        "has_debug_context": bool(message.debug_context),
        "created_at": message.created_at,
    }


@router.post("/conversations", response_model=ConversationOut, status_code=201)
async def create_conversation(
    session: DBSession,
    conversation_service: ConversationServiceDep,
    body: ConversationCreate,
):
    conversation = await conversation_service.create(session, body.title)
    return conversation


@router.get("/conversations", response_model=ConversationsList)
async def list_conversations(
    session: DBSession,
    conversation_service: ConversationServiceDep,
):
    conversations = await conversation_service.list_all(session)
    return {"conversations": conversations}


@router.get("/conversations/{conversation_id}", response_model=ConversationWithMessages)
async def get_conversation(
    session: DBSession,
    conversation_service: ConversationServiceDep,
    conversation_id: UUID,
):
    conversation, messages = await conversation_service.get_with_messages(
        session, conversation_id
    )
    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "messages": [_message_to_out(m) for m in messages],
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    session: DBSession,
    conversation_service: ConversationServiceDep,
    conversation_id: UUID,
):
    await conversation_service.delete(session, conversation_id)
    return {"message": "Conversation deleted successfully"}


@router.get("/conversations/{conversation_id}/messages/{message_id}/debug")
async def get_message_debug(
    session: DBSession,
    conversation_id: UUID,
    message_id: int,
):
    """Return the LLM prompt, context, history, and raw response for a message."""
    message = await conversation_repo.get_message(session, conversation_id, message_id)
    if message is None:
        raise NotFoundError("Message", str(message_id))
    if not message.debug_context:
        raise ValidationError("No debug context available for this message")
    return message.debug_context


@router.post("/conversations/{conversation_id}/ask", response_model=AskResponse)
async def ask_question(
    session: DBSession,
    conversation_service: ConversationServiceDep,
    retrieval_service: RetrievalDep,
    llm_service: LLMDep,
    conversation_id: UUID,
    body: AskRequest,
):
    if not await retrieval_service.has_chunks(session):
        raise ValidationError("Upload documents before asking questions")

    history = await conversation_service.add_user_message(
        session, conversation_id, body.question, body.history_limit
    )
    chunks = await retrieval_service.search(session, body.question)

    llm_response = await llm_service.answer(
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
        session,
        conversation_id,
        llm_response.content,
        sources,
        llm_response.debug_context,
    )

    return {"answer": llm_response.content, "sources": sources}


@router.post("/conversations/{conversation_id}/ask/stream")
async def ask_stream(
    conversation_service: ConversationServiceDep,
    retrieval_service: RetrievalDep,
    llm_service: LLMDep,
    conversation_id: UUID,
    body: AskRequest,
):
    # Streaming runs after the endpoint returns, so we cannot use the request
    # session dependency. Open a dedicated session inside the generator.
    async def event_generator():
        answer_parts = []
        async with AsyncSessionLocal() as session:
            async with session.begin():
                if not await retrieval_service.has_chunks(session):
                    yield "event: error\ndata: {\"error\": \"Upload documents before asking questions\"}\n\n"
                    return

                history = await conversation_service.add_user_message(
                    session, conversation_id, body.question, body.history_limit
                )
                chunks = await retrieval_service.search(session, body.question)
                sources = [c.to_dict() for c in chunks]

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
                debug_context = build_debug_context(
                    body.system_prompt,
                    format_context(chunks),
                    format_history(history),
                    body.question,
                    answer,
                )
                async with AsyncSessionLocal() as save_session:
                    async with save_session.begin():
                        await conversation_repo.add_message(
                            save_session,
                            conversation_id,
                            "assistant",
                            answer,
                            sources,
                            debug_context,
                        )
                        await conversation_repo.touch(save_session, conversation_id)

                yield f"event: sources\ndata: {json.dumps(sources)}\n\n"
                yield "data: [DONE]\n\n"
            except LLMServiceError as exc:
                logger.exception("LLM error during streaming (conversation_id=%s)", conversation_id)
                detail = str(exc) or "LLM service temporarily unavailable"
                yield f"event: error\ndata: {json.dumps({'error': detail})}\n\n"
            except Exception:
                logger.exception("Unexpected error during streaming (conversation_id=%s)", conversation_id)
                yield "event: error\ndata: {\"error\": \"An unexpected error occurred\"}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
