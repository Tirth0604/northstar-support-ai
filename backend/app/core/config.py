from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven Northstar configuration."""

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")
    app_name: str = "Northstar Support AI"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "sqlite:///./data/app.db"
    vector_store_path: Path = Path("./data/vector_store")
    upload_directory: Path = Path("./data/uploads")
    max_upload_size_mb: int = 20
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"
    jwt_secret_key: str = "northstar-local-demo-secret-change-me"
    jwt_access_token_expire_minutes: int = 60
    confirmation_expire_minutes: int = 10
    embedding_provider: str = "hash"
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: int = 384
    llm_provider: str = "mock"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    retrieval_top_k: int = 5
    similarity_threshold: float = 0.18
    minimum_evidence: int = 1
    chunk_size: int = 800
    chunk_overlap: int = 120
    max_question_length: int = 4000
    request_rate_limit: str = "60/minute"
    max_agent_steps: int = 6
    max_tool_failures: int = 2
    escalation_turn_threshold: int = 8

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]

    def ensure_directories(self) -> None:
        self.upload_directory.mkdir(parents=True, exist_ok=True)
        self.vector_store_path.mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite:///"):
            Path(self.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
