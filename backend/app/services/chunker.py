"""Simple character-based text chunking."""

from app.exceptions import ValidationError


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split text into overlapping chunks.

    Args:
        text: The input text to chunk.
        chunk_size: Maximum number of characters per chunk.
        chunk_overlap: Number of overlapping characters between chunks.

    Returns:
        A list of text chunks.
    """
    if chunk_size <= 0:
        raise ValidationError("chunk_size must be greater than 0")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValidationError("chunk_overlap must be between 0 and chunk_size - 1")

    chunks = []
    start = 0
    text_length = len(text)
    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
    return chunks
