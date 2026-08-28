from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import require_roles
from app.db.session import get_db
from app.models import (
    Conversation,
    Escalation,
    Message,
    SupportTicket,
    TicketMessage,
    ToolExecution,
    User,
)
from app.schemas.support import AgentReplyRequest, NoteRequest, TicketPatchRequest

router = APIRouter(prefix="/agent", tags=["support agent"])
agent_role = require_roles("support_agent", "admin")


def serialize(conversation: Conversation, db: Session) -> dict:
    escalation = db.scalar(
        select(Escalation).where(Escalation.conversation_id == conversation.id).order_by(Escalation.created_at.desc())
    )
    tools = db.scalars(
        select(ToolExecution).where(ToolExecution.conversation_id == conversation.id).order_by(ToolExecution.created_at)
    ).all()
    return {
        "id": conversation.id,
        "title": conversation.title,
        "status": conversation.status,
        "ai_enabled": conversation.ai_enabled,
        "assigned_agent_id": conversation.assigned_agent_id,
        "summary": conversation.summary,
        "handoff": escalation.handoff_payload if escalation else None,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at,
                "structured_payload": m.structured_payload,
            }
            for m in conversation.messages
        ],
        "tool_timeline": [
            {
                "tool_name": t.tool_name,
                "status": t.status,
                "input_payload": t.input_payload,
                "output_payload": t.output_payload,
                "latency_ms": t.latency_ms,
                "created_at": t.created_at,
            }
            for t in tools
        ],
    }


@router.get("/queue")
def queue(
    _: User = Depends(agent_role),
    db: Session = Depends(get_db),
    priority: str | None = None,
    category: str | None = None,
) -> list[dict]:
    query = (
        select(Escalation, Conversation, SupportTicket)
        .join(Conversation, Conversation.id == Escalation.conversation_id)
        .outerjoin(SupportTicket, SupportTicket.id == Escalation.ticket_id)
        .where(Escalation.status == "queued")
        .order_by(Escalation.created_at)
    )
    rows = db.execute(query).all()
    return [
        {
            "escalation_id": e.id,
            "conversation_id": c.id,
            "reason": e.reason,
            "summary": e.summary,
            "handoff": e.handoff_payload,
            "priority": t.priority if t else "normal",
            "category": t.category if t else "general",
            "waiting_since": e.created_at,
        }
        for e, c, t in rows
        if (not priority or (t and t.priority == priority)) and (not category or (t and t.category == category))
    ]


@router.get("/conversations/{conversation_id}")
def conversation(conversation_id: str, _: User = Depends(agent_role), db: Session = Depends(get_db)) -> dict:
    item = db.scalar(
        select(Conversation).options(selectinload(Conversation.messages)).where(Conversation.id == conversation_id)
    )
    if not item:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return serialize(item, db)


@router.post("/conversations/{conversation_id}/takeover")
def takeover(conversation_id: str, user: User = Depends(agent_role), db: Session = Depends(get_db)) -> dict:
    item = db.get(Conversation, conversation_id)
    if not item:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    item.ai_enabled = False
    item.status = "human_assigned"
    item.assigned_agent_id = user.id
    escalation = db.scalar(
        select(Escalation).where(Escalation.conversation_id == item.id, Escalation.status == "queued")
    )
    if escalation:
        escalation.status = "accepted"
        escalation.accepted_at = datetime.now(UTC)
    db.commit()
    return {"status": item.status, "ai_enabled": item.ai_enabled, "assigned_agent_id": user.id}


@router.post("/conversations/{conversation_id}/reply")
def reply(
    conversation_id: str, payload: AgentReplyRequest, user: User = Depends(agent_role), db: Session = Depends(get_db)
) -> dict:
    item = db.get(Conversation, conversation_id)
    if not item or item.assigned_agent_id != user.id or item.ai_enabled:
        raise HTTPException(status_code=409, detail="Take over the conversation before replying.")
    message = Message(
        conversation_id=item.id,
        role="human_agent",
        sender_id=user.id,
        content=payload.content,
        structured_payload={"response_type": "human_message"},
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return {"id": message.id, "role": message.role, "content": message.content, "created_at": message.created_at}


@router.post("/conversations/{conversation_id}/release")
def release(conversation_id: str, user: User = Depends(agent_role), db: Session = Depends(get_db)) -> dict:
    item = db.get(Conversation, conversation_id)
    if not item or (item.assigned_agent_id not in {None, user.id} and user.role != "admin"):
        raise HTTPException(status_code=409, detail="Conversation is assigned to another agent.")
    item.ai_enabled = True
    item.status = "ai_active"
    item.assigned_agent_id = None
    db.commit()
    return {"status": item.status, "ai_enabled": True}


@router.patch("/tickets/{ticket_id}")
def patch_ticket(
    ticket_id: str, payload: TicketPatchRequest, _: User = Depends(agent_role), db: Session = Depends(get_db)
) -> dict:
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    for field in ("status", "priority", "category", "assigned_agent_id"):
        value = getattr(payload, field)
        if value is not None:
            setattr(ticket, field, value)
    if ticket.status in {"resolved", "closed"}:
        ticket.resolved_at = datetime.now(UTC)
    db.commit()
    return {
        "id": ticket.id,
        "status": ticket.status,
        "priority": ticket.priority,
        "category": ticket.category,
        "assigned_agent_id": ticket.assigned_agent_id,
    }


@router.post("/tickets/{ticket_id}/notes", status_code=201)
def note(ticket_id: str, payload: NoteRequest, user: User = Depends(agent_role), db: Session = Depends(get_db)) -> dict:
    if not db.get(SupportTicket, ticket_id):
        raise HTTPException(status_code=404, detail="Ticket not found.")
    item = TicketMessage(
        ticket_id=ticket_id, sender_type="support_agent", sender_id=user.id, content=payload.content, is_internal=True
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "is_internal": True}
