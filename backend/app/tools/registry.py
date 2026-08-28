"""Explicit, typed business tools. No tool accepts raw SQL or arbitrary model code."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Conversation,
    CustomerProfile,
    Escalation,
    Message,
    Order,
    ShippingEvent,
    SupportTicket,
    TicketMessage,
    ToolExecution,
    User,
)


class EmptyInput(BaseModel):
    pass


class OrderInput(BaseModel):
    order_id: str = Field(min_length=1, max_length=36)


class TicketInput(BaseModel):
    ticket_id: str = Field(min_length=1, max_length=36)


class CreateTicketInput(BaseModel):
    subject: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=3, max_length=4000)
    category: str = Field(default="general", max_length=48)
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")


class PriorityInput(TicketInput):
    priority: str = Field(pattern="^(low|normal|high|urgent)$")


class MessageInput(TicketInput):
    content: str = Field(min_length=1, max_length=4000)
    is_internal: bool = False


class EscalateInput(BaseModel):
    reason: str = Field(min_length=3, max_length=160)
    sentiment: str = "neutral"


@dataclass(frozen=True)
class ToolPolicy:
    allowed_roles: frozenset[str]
    requires_identity: bool
    requires_confirmation: bool
    mutates_data: bool
    max_per_minute: int


@dataclass(frozen=True)
class ToolDefinition:
    input_model: type[BaseModel]
    policy: ToolPolicy
    handler: Callable[..., dict[str, Any]]


@dataclass
class ToolContext:
    db: Session
    user: User
    customer: CustomerProfile | None
    conversation: Conversation


def _owned_order(ctx: ToolContext, order_id: str) -> Order:
    if not ctx.customer:
        raise PermissionError("Verified customer identity is required.")
    order = ctx.db.scalar(select(Order).where(Order.id == order_id, Order.customer_id == ctx.customer.id))
    if not order:
        raise LookupError("Order not found for the authenticated customer.")
    return order


def authenticated_customer(_: BaseModel, ctx: ToolContext) -> dict[str, Any]:
    if not ctx.customer:
        raise PermissionError("Verified customer identity is required.")
    return {"customer_id": ctx.customer.id, "name": ctx.user.name, "loyalty_tier": ctx.customer.loyalty_tier}


def list_orders(_: BaseModel, ctx: ToolContext) -> dict[str, Any]:
    if not ctx.customer:
        raise PermissionError("Verified customer identity is required.")
    rows = ctx.db.scalars(
        select(Order).where(Order.customer_id == ctx.customer.id).order_by(Order.created_at.desc())
    ).all()
    return {
        "orders": [
            {
                "id": o.id,
                "order_number": o.order_number,
                "status": o.status,
                "payment_status": o.payment_status,
                "total_amount": float(o.total_amount),
                "created_at": o.created_at.isoformat(),
            }
            for o in rows
        ]
    }


def order_details(data: OrderInput, ctx: ToolContext) -> dict[str, Any]:
    order = _owned_order(ctx, data.order_id)
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "payment_status": order.payment_status,
        "total_amount": float(order.total_amount),
        "shipping_address": order.shipping_address,
    }


def shipping_status(data: OrderInput, ctx: ToolContext) -> dict[str, Any]:
    order = _owned_order(ctx, data.order_id)
    events = ctx.db.scalars(
        select(ShippingEvent).where(ShippingEvent.order_id == order.id).order_by(ShippingEvent.occurred_at)
    ).all()
    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "timeline": [
            {"status": e.status, "location": e.location, "message": e.message, "occurred_at": e.occurred_at.isoformat()}
            for e in events
        ],
    }


def cancellation_eligibility(data: OrderInput, ctx: ToolContext) -> dict[str, Any]:
    order = _owned_order(ctx, data.order_id)
    eligible = order.status in {"processing", "confirmed"}
    return {
        "order_id": order.id,
        "eligible": eligible,
        "reason": "Order has not entered fulfilment." if eligible else "Order is already in fulfilment or completed.",
    }


def cancel_order(data: OrderInput, ctx: ToolContext) -> dict[str, Any]:
    order = _owned_order(ctx, data.order_id)
    if order.status not in {"processing", "confirmed"}:
        raise ValueError("Order is no longer eligible for cancellation.")
    order.status = "cancelled"
    return {"order_id": order.id, "order_number": order.order_number, "status": "cancelled"}


def return_eligibility(data: OrderInput, ctx: ToolContext) -> dict[str, Any]:
    order = _owned_order(ctx, data.order_id)
    age = datetime.now(UTC) - order.created_at.replace(tzinfo=order.created_at.tzinfo or UTC)
    eligible = order.status == "delivered" and age <= timedelta(days=30)
    return {
        "order_id": order.id,
        "eligible": eligible,
        "reason": "Within the 30-day return window."
        if eligible
        else "Order is not delivered or is outside the 30-day window.",
    }


def list_tickets(_: BaseModel, ctx: ToolContext) -> dict[str, Any]:
    if not ctx.customer:
        raise PermissionError("Verified customer identity is required.")
    rows = ctx.db.scalars(
        select(SupportTicket)
        .where(SupportTicket.customer_id == ctx.customer.id)
        .order_by(SupportTicket.created_at.desc())
    ).all()
    return {
        "tickets": [
            {
                "id": t.id,
                "subject": t.subject,
                "category": t.category,
                "priority": t.priority,
                "status": t.status,
                "created_at": t.created_at.isoformat(),
            }
            for t in rows
        ]
    }


def ticket_details(data: TicketInput, ctx: ToolContext) -> dict[str, Any]:
    if not ctx.customer:
        raise PermissionError("Verified customer identity is required.")
    ticket = ctx.db.scalar(
        select(SupportTicket).where(SupportTicket.id == data.ticket_id, SupportTicket.customer_id == ctx.customer.id)
    )
    if not ticket:
        raise LookupError("Ticket not found for the authenticated customer.")
    messages = ctx.db.scalars(
        select(TicketMessage).where(TicketMessage.ticket_id == ticket.id, TicketMessage.is_internal.is_(False))
    ).all()
    return {
        "id": ticket.id,
        "subject": ticket.subject,
        "status": ticket.status,
        "priority": ticket.priority,
        "messages": [{"sender_type": m.sender_type, "content": m.content} for m in messages],
    }


def create_ticket(data: CreateTicketInput, ctx: ToolContext) -> dict[str, Any]:
    if not ctx.customer:
        raise PermissionError("Verified customer identity is required.")
    ticket = SupportTicket(
        customer_id=ctx.customer.id,
        conversation_id=ctx.conversation.id,
        subject=data.subject,
        description=data.description,
        category=data.category,
        priority=data.priority,
    )
    ctx.db.add(ticket)
    ctx.db.flush()
    return {"ticket_id": ticket.id, "subject": ticket.subject, "status": ticket.status, "priority": ticket.priority}


def update_priority(data: PriorityInput, ctx: ToolContext) -> dict[str, Any]:
    ticket = ctx.db.get(SupportTicket, data.ticket_id)
    if not ticket:
        raise LookupError("Ticket not found.")
    if ctx.user.role == "customer" and (not ctx.customer or ticket.customer_id != ctx.customer.id):
        raise PermissionError("Ticket does not belong to this customer.")
    ticket.priority = data.priority
    return {"ticket_id": ticket.id, "priority": ticket.priority}


def add_ticket_message(data: MessageInput, ctx: ToolContext) -> dict[str, Any]:
    ticket = ctx.db.get(SupportTicket, data.ticket_id)
    if not ticket:
        raise LookupError("Ticket not found.")
    if ctx.user.role == "customer" and (not ctx.customer or ticket.customer_id != ctx.customer.id or data.is_internal):
        raise PermissionError("Message is not permitted.")
    message = TicketMessage(
        ticket_id=ticket.id,
        sender_type=ctx.user.role,
        sender_id=ctx.user.id,
        content=data.content,
        is_internal=data.is_internal,
    )
    ctx.db.add(message)
    ctx.db.flush()
    return {"ticket_id": ticket.id, "message_id": message.id, "is_internal": message.is_internal}


def escalate(data: EscalateInput, ctx: ToolContext) -> dict[str, Any]:
    recent = ctx.db.scalars(
        select(Message)
        .where(Message.conversation_id == ctx.conversation.id)
        .order_by(Message.created_at.desc())
        .limit(8)
    ).all()
    issue = next((m.content for m in recent if m.role == "customer"), "Customer requested support")
    summary = f"Verified customer {ctx.user.name}. Main issue: {issue[:300]}"
    ticket = None
    if ctx.customer:
        ticket = SupportTicket(
            customer_id=ctx.customer.id,
            conversation_id=ctx.conversation.id,
            subject=f"Escalated: {issue[:80]}",
            description=issue,
            category="escalation",
            priority="urgent" if data.sentiment in {"angry", "critical"} else "high",
            escalation_reason=data.reason,
        )
        ctx.db.add(ticket)
        ctx.db.flush()
    payload = {
        "customer": ctx.user.name,
        "main_issue": issue,
        "actions_taken": [],
        "tool_results": [],
        "order_or_ticket_ids": [ticket.id] if ticket else [],
        "sentiment": data.sentiment,
        "escalation_reason": data.reason,
        "suggested_next_action": "Review the conversation and contact the customer.",
        "unresolved_questions": [issue],
    }
    item = Escalation(
        conversation_id=ctx.conversation.id,
        ticket_id=ticket.id if ticket else None,
        reason=data.reason,
        summary=summary,
        handoff_payload=payload,
    )
    ctx.db.add(item)
    ctx.conversation.status = "escalated"
    ctx.conversation.ai_enabled = False
    ctx.conversation.summary = summary
    ctx.db.flush()
    return {
        "escalation_id": item.id,
        "ticket_id": ticket.id if ticket else None,
        "status": "queued",
        "handoff": payload,
    }


P = ToolPolicy
TOOLS: dict[str, ToolDefinition] = {
    "get_authenticated_customer": ToolDefinition(
        EmptyInput, P(frozenset({"customer", "support_agent", "admin"}), True, False, False, 30), authenticated_customer
    ),
    "list_customer_orders": ToolDefinition(
        EmptyInput, P(frozenset({"customer", "support_agent", "admin"}), True, False, False, 30), list_orders
    ),
    "get_order_details": ToolDefinition(
        OrderInput, P(frozenset({"customer", "support_agent", "admin"}), True, False, False, 30), order_details
    ),
    "get_shipping_status": ToolDefinition(
        OrderInput, P(frozenset({"customer", "support_agent", "admin"}), True, False, False, 30), shipping_status
    ),
    "check_cancellation_eligibility": ToolDefinition(
        OrderInput, P(frozenset({"customer", "support_agent"}), True, False, False, 20), cancellation_eligibility
    ),
    "cancel_order": ToolDefinition(
        OrderInput, P(frozenset({"customer", "support_agent"}), True, True, True, 5), cancel_order
    ),
    "check_return_eligibility": ToolDefinition(
        OrderInput, P(frozenset({"customer", "support_agent"}), True, False, False, 20), return_eligibility
    ),
    "list_customer_tickets": ToolDefinition(
        EmptyInput, P(frozenset({"customer", "support_agent", "admin"}), True, False, False, 30), list_tickets
    ),
    "get_ticket_details": ToolDefinition(
        TicketInput, P(frozenset({"customer", "support_agent", "admin"}), True, False, False, 30), ticket_details
    ),
    "create_support_ticket": ToolDefinition(
        CreateTicketInput, P(frozenset({"customer", "support_agent"}), True, False, True, 10), create_ticket
    ),
    "update_ticket_priority": ToolDefinition(
        PriorityInput, P(frozenset({"support_agent", "admin"}), False, False, True, 20), update_priority
    ),
    "add_ticket_message": ToolDefinition(
        MessageInput, P(frozenset({"customer", "support_agent", "admin"}), False, False, True, 30), add_ticket_message
    ),
    "escalate_to_human": ToolDefinition(
        EscalateInput, P(frozenset({"customer", "support_agent", "admin"}), False, False, True, 10), escalate
    ),
}


class ToolExecutor:
    def execute(
        self, name: str, raw_input: dict[str, Any], ctx: ToolContext, *, confirmed: bool = False
    ) -> dict[str, Any]:
        definition = TOOLS.get(name)
        if not definition:
            raise LookupError("Tool is not approved.")
        policy = definition.policy
        if ctx.user.role not in policy.allowed_roles:
            raise PermissionError("Role is not permitted to use this tool.")
        if policy.requires_identity and not ctx.customer:
            raise PermissionError("Verified identity is required.")
        if policy.requires_confirmation and not confirmed:
            raise PermissionError("Explicit action-specific confirmation is required.")
        cutoff = datetime.now(UTC) - timedelta(minutes=1)
        count = (
            ctx.db.scalar(
                select(func.count(ToolExecution.id)).where(
                    ToolExecution.conversation_id == ctx.conversation.id,
                    ToolExecution.tool_name == name,
                    ToolExecution.created_at >= cutoff,
                )
            )
            or 0
        )
        if count >= policy.max_per_minute:
            raise RuntimeError("Tool frequency limit reached.")
        started = time.perf_counter()
        event = ToolExecution(
            conversation_id=ctx.conversation.id, tool_name=name, input_payload=raw_input, status="running"
        )
        ctx.db.add(event)
        ctx.db.flush()
        try:
            validated = definition.input_model.model_validate(raw_input)
            result = definition.handler(validated, ctx)
            event.output_payload = result
            event.status = "success"
            return {"tool_name": name, "status": "success", "result": result}
        except (ValidationError, ValueError, LookupError, PermissionError, RuntimeError) as exc:
            event.status = "failed"
            event.error_message = str(exc)[:500]
            raise
        finally:
            event.latency_ms = round((time.perf_counter() - started) * 1000)
            ctx.db.flush()
