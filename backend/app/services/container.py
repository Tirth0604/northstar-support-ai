from functools import lru_cache

from app.core.config import get_settings
from app.providers.llm import build_llm_provider
from app.rag.embeddings import build_embedding_provider
from app.rag.vector_store import LocalVectorStore
from app.services.chat import ChatService
from app.services.documents import DocumentService


@lru_cache
def services() -> tuple[DocumentService, ChatService]:
    settings = get_settings()
    embeddings = build_embedding_provider(
        settings.embedding_provider, settings.embedding_model_name, settings.embedding_dimensions
    )
    vectors = LocalVectorStore(settings.vector_store_path)
    llm = build_llm_provider(settings.llm_provider, settings.openai_api_key, settings.openai_model)
    return DocumentService(settings, embeddings, vectors), ChatService(settings, embeddings, vectors, llm)
