import json
import math
import threading
from dataclasses import asdict
from pathlib import Path

from app.rag.types import Chunk, SearchResult


class LocalVectorStore:
    """Small persistent JSON vector store with atomic writes and metadata filtering."""

    def __init__(self, directory: Path):
        self.path = directory / "index.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _write(self, records: list[dict]) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.path)

    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Every chunk must have one embedding.")
        with self._lock:
            current = (
                [item for item in self._read() if item["chunk"]["document_id"] != chunks[0].document_id]
                if chunks
                else self._read()
            )
            current.extend(
                {"chunk": asdict(chunk), "embedding": embedding}
                for chunk, embedding in zip(chunks, embeddings, strict=True)
            )
            self._write(current)

    def delete_document(self, document_id: str) -> None:
        with self._lock:
            self._write([item for item in self._read() if item["chunk"]["document_id"] != document_id])

    def clear(self) -> None:
        with self._lock:
            self._write([])

    def search(
        self, query: list[float], top_k: int, threshold: float, document_ids: list[str] | None = None
    ) -> list[SearchResult]:
        results: list[SearchResult] = []
        allowed = set(document_ids or [])
        for item in self._read():
            data = item["chunk"]
            if allowed and data["document_id"] not in allowed:
                continue
            score = sum(a * b for a, b in zip(query, item["embedding"], strict=False))
            if math.isfinite(score) and score >= threshold:
                results.append(SearchResult(Chunk(**data), round(score, 4)))
        results.sort(key=lambda result: result.score, reverse=True)
        deduplicated: list[SearchResult] = []
        seen: set[str] = set()
        for result in results:
            fingerprint = " ".join(result.chunk.text.lower().split())[:180]
            if fingerprint not in seen:
                seen.add(fingerprint)
                deduplicated.append(result)
        return deduplicated[:top_k]
