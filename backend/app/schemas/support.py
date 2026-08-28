from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    email: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class CitationPayload(BaseModel):
    document_id: str
    document_name: str
    section: str | None = None
    page_number: int | None = None
    excerpt: str
    relevance_score: float


class AgentResponse(BaseModel):
    response_type: Literal[
        "informational_answer",
        "clarifying_question",
        "tool_result",
        "confirmation_required",
        "action_completed",
        "ticket_created",
        "human_escalation",
        "human_message",
        "refusal",
        "system_error",
    ]
    message: str
    citations: list[CitationPayload] = []
    tool_events: list[dict[str, Any]] = []
    requires_confirmation: bool = False
    pending_action: dict[str, Any] | None = None
    escalation: dict[str, Any] | None = None
    ui_payload: dict[str, Any] = {}


class CustomerMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ConfirmationRequest(BaseModel):
    confirmation_token: str = Field(min_length=20, max_length=256)
    confirmed: bool


class ConversationCreateRequest(BaseModel):
    title: str = Field(default="New support conversation", min_length=1, max_length=120)


class TicketCreateRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=3, max_length=4000)
    category: str = Field(default="general", max_length=48)


class AgentReplyRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class TicketPatchRequest(BaseModel):
    status: str | None = None
    priority: str | None = None
    category: str | None = None
    assigned_agent_id: str | None = None


class NoteRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class SentimentResult(BaseModel):
    sentiment: Literal["positive", "neutral", "confused", "frustrated", "angry"]
    urgency: Literal["low", "normal", "high", "critical"]
    escalation_required: bool
    reason_codes: list[str]
    confidence: float = Field(ge=0, le=1)
