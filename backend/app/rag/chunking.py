import hashlib

from app.rag.types import Chunk, TextSection


def chunk_sections(
    sections: list[TextSection], document_id: str, document_name: str, chunk_size: int, overlap: int
) -> list[Chunk]:
    """Create stable, page-aware chunks, preferring paragraph and sentence boundaries."""
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Chunk size must be positive and overlap smaller than chunk size.")
    chunks: list[Chunk] = []
    for section in sections:
        start = 0
        while start < len(section.text):
            end = min(start + chunk_size, len(section.text))
            if end < len(section.text):
                candidates = [
                    section.text.rfind("\n", start + chunk_size // 2, end),
                    section.text.rfind(". ", start + chunk_size // 2, end),
                ]
                boundary = max(candidates)
                if boundary > start:
                    end = boundary + 1
            text = section.text[start:end].strip()
            if text:
                index = len(chunks)
                digest = hashlib.sha1(f"{document_id}:{index}:{text}".encode()).hexdigest()[:16]
                chunks.append(Chunk(digest, document_id, document_name, text, section.page_number, index))
            if end >= len(section.text):
                break
            start = max(end - overlap, start + 1)
    return chunks
