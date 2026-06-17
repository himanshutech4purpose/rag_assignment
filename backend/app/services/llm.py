"""LLM service supporting Groq and OpenAI providers via LangChain."""

import asyncio
from collections.abc import AsyncIterator

from langchain.prompts import PromptTemplate
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from app.config import Settings
from app.exceptions import LLMServiceError
from app.logging_config import get_logger
from app.domain import LLMResponse, Message, RetrievedChunk

logger = get_logger(__name__)

DEFAULT_SYSTEM_PROMPT = """You are a helpful assistant. Answer the question using the provided context and previous conversation.
If the question asks about earlier parts of the conversation, use the previous conversation.
Cite the source document name, page number, and chunk index for each fact you use from the context.

Context:
{context}

Previous conversation:
{history}

Question: {question}

Answer:"""


def build_prompt(system_prompt: str | None = None) -> PromptTemplate:
    template = system_prompt or DEFAULT_SYSTEM_PROMPT
    return PromptTemplate.from_template(template)


def format_context(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(
        f"[{c.document_name} - page {c.page_number or 'unknown'}, chunk {c.chunk_index}]\n{c.content}"
        for c in chunks
    )


def format_history(messages: list[Message]) -> str:
    return "\n\n".join(
        f"{'User' if m.role == 'user' else 'Assistant'}: {m.content}" for m in messages
    )


def build_debug_context(
    system_prompt: str | None,
    context: str,
    history_text: str,
    question: str,
    raw_response: str,
) -> dict:
    """Capture the exact inputs and raw output sent to the LLM for debugging."""
    prompt = build_prompt(system_prompt)
    raw_input = prompt.format(
        context=context, history=history_text, question=question
    )
    return {
        "system_prompt": system_prompt or DEFAULT_SYSTEM_PROMPT,
        "context": context,
        "history": history_text,
        "question": question,
        "raw_input": raw_input,
        "raw_response": raw_response,
    }


class LLMService:
    """Provides async access to the configured LLM providers."""

    def __init__(self, settings: Settings):
        self._settings = settings

    def _get_llm(
        self,
        provider: str = "groq",
        model: str | None = None,
        api_key: str | None = None,
        max_tokens: int | None = None,
    ) -> BaseChatModel:
        provider = provider.lower()
        extra_kwargs = {}
        if max_tokens is not None:
            extra_kwargs["max_tokens"] = max_tokens

        if provider == "groq":
            return ChatGroq(
                api_key=api_key or self._settings.groq_api_key,
                model_name=model or self._settings.llm_model,
                temperature=0.1,
                **extra_kwargs,
            )
        if provider == "openai":
            key = api_key or self._settings.openai_api_key
            if not key:
                raise LLMServiceError("OpenAI API key is required when provider is 'openai'")
            return ChatOpenAI(
                api_key=key,
                model_name=model or self._settings.openai_model,
                temperature=0.1,
                **extra_kwargs,
            )
        raise LLMServiceError(f"Unsupported LLM provider: {provider}")

    async def answer(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        history: list[Message],
        provider: str = "groq",
        model: str | None = None,
        api_key: str | None = None,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        context = format_context(chunks)
        history_text = format_history(history)
        prompt = build_prompt(system_prompt)
        llm = self._get_llm(provider, model, api_key, max_tokens)
        chain = prompt | llm
        try:
            # Some LangChain invoke calls perform network I/O synchronously.
            response = await asyncio.to_thread(
                chain.invoke,
                {"context": context, "history": history_text, "question": question},
            )
            content = str(response.content)
            debug_context = build_debug_context(
                system_prompt, context, history_text, question, content
            )
            return LLMResponse(content=content, debug_context=debug_context)
        except Exception as exc:
            logger.exception("LLM invoke failed")
            raise LLMServiceError(f"LLM invoke failed: {exc}") from exc

    async def stream_answer(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        history: list[Message],
        provider: str = "groq",
        model: str | None = None,
        api_key: str | None = None,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        context = format_context(chunks)
        history_text = format_history(history)
        prompt = build_prompt(system_prompt)
        llm = self._get_llm(provider, model, api_key, max_tokens)
        chain = prompt | llm
        try:
            async for chunk in chain.astream(
                {"context": context, "history": history_text, "question": question}
            ):
                yield str(chunk.content)
        except Exception as exc:
            logger.exception("LLM streaming failed")
            raise LLMServiceError(f"LLM streaming failed: {exc}") from exc
