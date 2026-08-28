from dataclasses import dataclass


@dataclass(slots=True)
class TextSection:
    text: str
    page_number: int | None = None


@dataclass(slots=True)
class Chunk:
    id: str
    document_id: str
    document_name: str
    text: str
    page_number: int | None
    index: int


@dataclass(slots=True)
class SearchResult:
    chunk: Chunk
    score: float
