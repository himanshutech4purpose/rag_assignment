from sentence_transformers import CrossEncoder

from app.config import settings

_reranker: CrossEncoder | None = None


def get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(settings.reranker_model)
    return _reranker


def rerank(query: str, chunks: list[dict], top_k: int) -> list[dict]:
    """Re-rank chunks with a cross-encoder and return the top_k results."""
    if not chunks:
        return []

    pairs = [(query, chunk["content"]) for chunk in chunks]
    scores = get_reranker().predict(pairs, convert_to_numpy=True)

    scored_chunks = [
        {**chunk, "rerank_score": float(score)}
        for chunk, score in zip(chunks, scores)
    ]
    scored_chunks.sort(key=lambda x: x["rerank_score"], reverse=True)
    return scored_chunks[:top_k]
