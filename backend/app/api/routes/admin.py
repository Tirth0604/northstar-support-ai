from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.db.session import get_db
from app.models import Conversation, Document, Escalation, Message, SupportTicket, ToolExecution, User
from app.tools.registry import TOOLS

router = APIRouter(prefix="/admin", tags=["administration"])
admin = require_roles("admin")


@router.get("/metrics/overview")
def overview(_: User = Depends(admin), db: Session = Depends(get_db)) -> dict:
    conversations = db.scalar(select(func.count(Conversation.id))) or 0
    escalated = db.scalar(select(func.count(Escalation.id))) or 0
    resolved = db.scalar(select(func.count(SupportTicket.id)).where(SupportTicket.status == "resolved")) or 0
    tickets = db.scalar(select(func.count(SupportTicket.id))) or 0
    avg_latency = db.scalar(select(func.avg(Message.latency_ms)).where(Message.latency_ms.is_not(None))) or 0
    return {
        "conversations": conversations,
        "tickets": tickets,
        "resolution_rate": round(resolved / tickets, 3) if tickets else 0,
        "human_handoff_rate": round(escalated / conversations, 3) if conversations else 0,
        "average_response_time_ms": round(float(avg_latency), 1),
        "knowledge_documents": db.scalar(select(func.count(Document.id))) or 0,
    }


@router.get("/metrics/escalations")
def escalations(_: User = Depends(admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(Escalation.reason, func.count(Escalation.id))
        .group_by(Escalation.reason)
        .order_by(func.count(Escalation.id).desc())
    ).all()
    return [{"reason": reason, "count": count} for reason, count in rows]


@router.get("/metrics/tool-usage")
def tool_usage(_: User = Depends(admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(
            ToolExecution.tool_name,
            ToolExecution.status,
            func.count(ToolExecution.id),
            func.avg(ToolExecution.latency_ms),
        ).group_by(ToolExecution.tool_name, ToolExecution.status)
    ).all()
    return [
        {"tool_name": name, "status": status, "count": count, "average_latency_ms": round(float(latency or 0), 1)}
        for name, status, count, latency in rows
    ]


@router.get("/metrics/agent-quality")
def quality(_: User = Depends(admin), db: Session = Depends(get_db)) -> dict:
    grounded = db.scalar(select(func.count(Message.id)).where(Message.grounding_status == "grounded")) or 0
    answered = db.scalar(select(func.count(Message.id)).where(Message.role == "assistant")) or 0
    failures = db.scalar(select(func.count(ToolExecution.id)).where(ToolExecution.status == "failed")) or 0
    calls = db.scalar(select(func.count(ToolExecution.id))) or 0
    return {
        "grounded_answer_rate": round(grounded / answered, 3) if answered else 0,
        "tool_success_rate": round((calls - failures) / calls, 3) if calls else 1.0,
        "note": "Demonstration metrics from seeded and local application activity; not production validation.",
    }


@router.get("/configuration")
def configuration(_: User = Depends(admin)) -> dict:
    return {
        "tools": [
            {
                "name": name,
                "enabled": True,
                "allowed_roles": sorted(item.policy.allowed_roles),
                "requires_identity": item.policy.requires_identity,
                "requires_confirmation": item.policy.requires_confirmation,
                "mutates_data": item.policy.mutates_data,
                "max_per_minute": item.policy.max_per_minute,
            }
            for name, item in TOOLS.items()
        ]
    }


@router.get("/errors")
def errors(_: User = Depends(admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(
        select(ToolExecution)
        .where(ToolExecution.status == "failed")
        .order_by(ToolExecution.created_at.desc())
        .limit(50)
    ).all()
    return [
        {"id": r.id, "tool_name": r.tool_name, "error_message": r.error_message, "created_at": r.created_at}
        for r in rows
    ]


@router.get("/support-agents")
def agents(_: User = Depends(admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(User).where(User.role == "support_agent").order_by(User.name)).all()
    return [{"id": u.id, "name": u.name, "email": u.email, "is_active": u.is_active} for u in rows]
