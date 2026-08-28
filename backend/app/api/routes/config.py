from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["configuration"])


@router.get("/config/public")
async def public_config() -> dict:
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "max_upload_size_mb": settings.max_upload_size_mb,
        "allowed_file_types": ["pdf", "docx", "txt", "md"],
        "retrieval_top_k": settings.retrieval_top_k,
        "similarity_threshold": settings.similarity_threshold,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "llm_provider": settings.llm_provider,
        "model_name": settings.openai_model if settings.llm_provider == "openai" else "Grounded mock (offline)",
    }
