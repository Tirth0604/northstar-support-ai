from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    original_filename: str
    file_type: str
    file_size: int
    upload_status: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None


class CitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str | None = None
    document_id: str
    document_name: str
    chunk_id: str
    page_number: int | None
    excerpt: str
    relevance_score: float


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    role: str
    content: str
    created_at: datetime
    latency_ms: int | None = None
    grounding_status: str | None = None
    citations: list[CitationOut] = []


class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=120)


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut] = []


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    document_ids: list[str] | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    similarity_threshold: float | None = Field(default=None, ge=-1, le=1)


class ChatResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    retrieved_sources: list[CitationOut]
    grounding_status: str
    confidence: float
    conversation_id: str
    message_id: str
    response_time_ms: int
