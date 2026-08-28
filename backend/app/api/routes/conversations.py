from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agents.workflow import SupportWorkflow
from app.auth.dependencies import current_customer, current_user
from app.db.session import get_db
from app.models import Conversation, CustomerProfile, Message, User
from app.schemas.support import AgentResponse, ConfirmationRequest, ConversationCreateRequest, CustomerMessageRequest
from app.tools.registry import ToolContext, ToolExecutor

router = APIRouter(prefix="/conversations", tags=["customer conversations"])
workflow = SupportWorkflow()


def owned(conversation_id: str, customer: CustomerProfile, db: Session) -> Conversation:
    item = db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id, Conversation.customer_id == customer.id)
    )
    if not item:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return item


def serialize(item: Conversation) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "status": item.status,
        "ai_enabled": item.ai_enabled,
        "assigned_agent_id": item.assigned_agent_id,
        "summary": item.summary,
        "pending_action": item.pending_action,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "structured_payload": m.structured_payload,
                "created_at": m.created_at,
                "latency_ms": m.latency_ms,
                "grounding_status": m.grounding_status,
                "citations": [
                    {
                        "document_id": c.document_id,
                        "document_name": c.document_name,
                        "page_number": c.page_number,
                        "excerpt": c.excerpt,
                        "relevance_score": c.relevance_score,
                    }
                    for c in m.citations
                ],
            }
            for m in item.messages
        ],
    }


@router.post("", status_code=201)
def create(
    payload: ConversationCreateRequest,
    customer: CustomerProfile = Depends(current_customer),
    db: Session = Depends(get_db),
) -> dict:
    item = Conversation(customer_id=customer.id, title=payload.title)
    db.add(item)
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.get("")
def list_conversations(
    customer: CustomerProfile = Depends(current_customer), db: Session = Depends(get_db)
) -> list[dict]:
    rows = db.scalars(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.customer_id == customer.id)
        .order_by(Conversation.updated_at.desc())
    ).all()
    return [serialize(item) for item in rows]


@router.get("/{conversation_id}")
def get(
    conversation_id: str, customer: CustomerProfile = Depends(current_customer), db: Session = Depends(get_db)
) -> dict:
    return serialize(owned(conversation_id, customer, db))


@router.post("/{conversation_id}/messages", response_model=AgentResponse)
async def message(
    conversation_id: str,
    payload: CustomerMessageRequest,
    customer: CustomerProfile = Depends(current_customer),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> AgentResponse:
    return await workflow.process(payload.content, owned(conversation_id, customer, db), user, db)


@router.post("/{conversation_id}/confirm-action", response_model=AgentResponse)
def confirm(
    conversation_id: str,
    payload: ConfirmationRequest,
    customer: CustomerProfile = Depends(current_customer),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> AgentResponse:
    try:
        return workflow.confirm(
            payload.confirmation_token, payload.confirmed, owned(conversation_id, customer, db), user, db
        )
    except (ValueError, PermissionError, LookupError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{conversation_id}/request-human", response_model=AgentResponse)
def request_human(
    conversation_id: str,
    customer: CustomerProfile = Depends(current_customer),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> AgentResponse:
    item = owned(conversation_id, customer, db)
    event = ToolExecutor().execute(
        "escalate_to_human",
        {"reason": "explicit_human_request", "sentiment": "neutral"},
        ToolContext(db=db, user=user, customer=customer, conversation=item),
    )
    response = AgentResponse(
        response_type="human_escalation",
        message="Your conversation has been escalated. A human support agent can now take over.",
        tool_events=[event],
        escalation=event["result"],
    )
    db.add(
        Message(
            conversation_id=item.id,
            role="assistant",
            content=response.message,
            structured_payload=response.model_dump(mode="json"),
        )
    )
    db.commit()
    return response


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    conversation_id: str, customer: CustomerProfile = Depends(current_customer), db: Session = Depends(get_db)
) -> Response:
    item = owned(conversation_id, customer, db)
    db.delete(item)
    db.commit()
    return Response(status_code=204)
