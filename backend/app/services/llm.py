from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq

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

llm = ChatGroq(
    api_key=settings.groq_api_key,
    model_name=settings.llm_model,
    temperature=0.1,
)


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


def answer_question(question: str, chunks: list[dict], history: list[dict]) -> str:
    context = format_context(chunks)
    history_text = format_history(history)
    chain = prompt | llm
    return chain.invoke(
        {"context": context, "history": history_text, "question": question}
    ).content


async def stream_answer(question: str, chunks: list[dict], history: list[dict]):
    context = format_context(chunks)
    history_text = format_history(history)
    chain = prompt | llm
    async for chunk in chain.astream(
        {"context": context, "history": history_text, "question": question}
    ):
        yield chunk.content
