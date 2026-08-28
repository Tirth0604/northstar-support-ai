import hashlib
import math
import re
from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic signed feature hashing for zero-download local demonstrations."""

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * self.dimensions
            tokens = re.findall(r"[a-z0-9]+", text.lower())
            for token in tokens:
                raw = hashlib.blake2b(token.encode(), digest_size=8).digest()
                index = int.from_bytes(raw[:4], "big") % self.dimensions
                vector[index] += 1.0 if raw[4] % 2 else -1.0
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors


class SentenceTransformerProvider(EmbeddingProvider):
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()


def build_embedding_provider(name: str, model_name: str, dimensions: int) -> EmbeddingProvider:
    if name == "sentence_transformers":
        return SentenceTransformerProvider(model_name)
    if name != "hash":
        raise ValueError(f"Unsupported embedding provider: {name}")
    return HashEmbeddingProvider(dimensions)
