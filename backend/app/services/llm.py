from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from app.config import settings

prompt = PromptTemplate.from_template(
    """You are a helpful assistant. Use ONLY the following context to answer the question.
Cite the source document name and chunk index for each fact you use.

Context:
{context}

Previous conversation:
{history}

Question: {question}

Answer:"""
)


def get_llm(provider: str = "groq", model: str | None = None, api_key: str | None = None):
    provider = provider.lower()
    if provider == "groq":
        return ChatGroq(
            api_key=api_key or settings.groq_api_key,
            model_name=model or settings.llm_model,
            temperature=0.1,
        )
    if provider == "openai":
        key = api_key or settings.openai_api_key
        if not key:
            raise ValueError("OpenAI API key is required when provider is 'openai'")
        return ChatOpenAI(
            api_key=key,
            model_name=model or settings.openai_model,
            temperature=0.1,
        )
    raise ValueError(f"Unsupported LLM provider: {provider}")


def format_context(chunks: list[dict]) -> str:
    return "\n\n".join(
        f"[{c['document_name']} - page {c.get('page_number') or 'unknown'}, chunk {c['chunk_index']}]\n{c['content']}"
        for c in chunks
    )


def format_history(messages: list[dict]) -> str:
    return "\n\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in messages
    )


def answer_question(
    question: str,
    chunks: list[dict],
    history: list[dict],
    provider: str = "groq",
    model: str | None = None,
    api_key: str | None = None,
) -> str:
    context = format_context(chunks)
    history_text = format_history(history)
    chain = prompt | get_llm(provider, model, api_key)
    return chain.invoke(
        {"context": context, "history": history_text, "question": question}
    ).content


async def stream_answer(
    question: str,
    chunks: list[dict],
    history: list[dict],
    provider: str = "groq",
    model: str | None = None,
    api_key: str | None = None,
):
    context = format_context(chunks)
    history_text = format_history(history)
    chain = prompt | get_llm(provider, model, api_key)
    async for chunk in chain.astream(
        {"context": context, "history": history_text, "question": question}
    ):
        yield chunk.content
