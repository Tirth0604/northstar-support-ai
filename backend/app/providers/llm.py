import re
from abc import ABC, abstractmethod

import httpx

from app.rag.prompts import REFUSAL
from app.rag.types import SearchResult

STOP_WORDS = {
    "what",
    "which",
    "where",
    "when",
    "who",
    "does",
    "the",
    "and",
    "for",
    "about",
    "is",
    "are",
    "a",
    "an",
    "of",
    "to",
}


def lexical_terms(text: str) -> set[str]:
    """Normalize a small set of English inflections for deterministic demo matching."""
    terms = set()
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        if token in STOP_WORDS:
            continue
        if token.endswith("er") and len(token) > 4:
            token = token[:-2]
        elif token.endswith("s") and len(token) > 3:
            token = token[:-1]
        terms.add(token)
    return terms


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, question: str, prompt: str, sources: list[SearchResult]) -> str:
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    """Deterministic extractive provider for tests and offline demonstrations."""

    async def generate(self, question: str, prompt: str, sources: list[SearchResult]) -> str:
        del prompt
        if not sources:
            return REFUSAL
        query_terms = lexical_terms(question)
        selected: list[str] = []
        for index, result in enumerate(sources[:3], 1):
            sentences = [
                sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", result.chunk.text) if sentence.strip()
            ]
            ranked = sorted(sentences, key=lambda sentence: len(query_terms & lexical_terms(sentence)), reverse=True)
            required_overlap = 1 if len(query_terms) <= 1 else 2
            supporting = [
                sentence for sentence in ranked[:2] if len(query_terms & lexical_terms(sentence)) >= required_overlap
            ]
            if supporting:
                selected.append(f"{' '.join(supporting)} [{index}]")
        return " ".join(selected) if selected else REFUSAL


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def generate(self, question: str, prompt: str, sources: list[SearchResult]) -> str:
        del question, sources
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": prompt, "temperature": 0},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("output_text") or "".join(
                part.get("text", "") for output in data.get("output", []) for part in output.get("content", [])
            )


def build_llm_provider(name: str, api_key: str | None, model: str) -> LLMProvider:
    if name == "openai":
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return OpenAIProvider(api_key, model)
    if name != "mock":
        raise ValueError(f"Unsupported LLM provider: {name}")
    return MockLLMProvider()
