from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import current_customer
from app.db.session import get_db
from app.models import CustomerProfile, Order, ShippingEvent, SupportTicket, TicketMessage

router = APIRouter(prefix="/customer", tags=["customer"])


@router.get("/orders")
def orders(customer: CustomerProfile = Depends(current_customer), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Order).where(Order.customer_id == customer.id).order_by(Order.created_at.desc())).all()
    return [
        {
            "id": o.id,
            "order_number": o.order_number,
            "status": o.status,
            "payment_status": o.payment_status,
            "total_amount": float(o.total_amount),
            "created_at": o.created_at,
        }
        for o in rows
    ]


@router.get("/orders/{order_id}")
def order(order_id: str, customer: CustomerProfile = Depends(current_customer), db: Session = Depends(get_db)) -> dict:
    item = db.scalar(select(Order).where(Order.id == order_id, Order.customer_id == customer.id))
    if not item:
        raise HTTPException(status_code=404, detail="Order not found.")
    return {
        "id": item.id,
        "order_number": item.order_number,
        "status": item.status,
        "payment_status": item.payment_status,
        "total_amount": float(item.total_amount),
        "shipping_address": item.shipping_address,
    }


@router.get("/orders/{order_id}/shipping")
def shipping(
    order_id: str, customer: CustomerProfile = Depends(current_customer), db: Session = Depends(get_db)
) -> list[dict]:
    item = db.scalar(select(Order).where(Order.id == order_id, Order.customer_id == customer.id))
    if not item:
        raise HTTPException(status_code=404, detail="Order not found.")
    rows = db.scalars(
        select(ShippingEvent).where(ShippingEvent.order_id == item.id).order_by(ShippingEvent.occurred_at)
    ).all()
    return [
        {"status": e.status, "location": e.location, "message": e.message, "occurred_at": e.occurred_at} for e in rows
    ]


@router.get("/tickets")
def tickets(customer: CustomerProfile = Depends(current_customer), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(
        select(SupportTicket).where(SupportTicket.customer_id == customer.id).order_by(SupportTicket.created_at.desc())
    ).all()
    return [
        {
            "id": t.id,
            "subject": t.subject,
            "category": t.category,
            "priority": t.priority,
            "status": t.status,
            "created_at": t.created_at,
        }
        for t in rows
    ]


@router.get("/tickets/{ticket_id}")
def ticket(
    ticket_id: str, customer: CustomerProfile = Depends(current_customer), db: Session = Depends(get_db)
) -> dict:
    item = db.scalar(
        select(SupportTicket).where(SupportTicket.id == ticket_id, SupportTicket.customer_id == customer.id)
    )
    if not item:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    messages = db.scalars(
        select(TicketMessage).where(TicketMessage.ticket_id == item.id, TicketMessage.is_internal.is_(False))
    ).all()
    return {
        "id": item.id,
        "subject": item.subject,
        "description": item.description,
        "status": item.status,
        "priority": item.priority,
        "messages": [
            {"sender_type": m.sender_type, "content": m.content, "created_at": m.created_at} for m in messages
        ],
    }
