"""Deterministic synthetic demonstration dataset. Never use these records as real customer data."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.service import hash_password
from app.models import (
    Conversation,
    CustomerProfile,
    Document,
    DocumentStatus,
    Message,
    Order,
    OrderItem,
    Product,
    ShippingEvent,
    SupportTicket,
    TicketMessage,
    User,
)
from app.rag.types import Chunk
from app.services.container import services

NAMESPACE = uuid.UUID("f91cc4c8-4ff2-48ad-8db6-51c67410c4da")


def sid(value: str) -> str:
    return str(uuid.uuid5(NAMESPACE, value))


POLICIES = {
    "Refund Policy": "Refunds are issued to the original payment method after an approved return is inspected. Banks may take 5 to 10 business days to post the refund. Duplicate charges are escalated to Billing immediately.",
    "Return Policy": "Most electronics may be returned within 30 calendar days after delivery. Opened products are accepted when complete and undamaged; damaged or wrong items should be reported within 48 hours.",
    "Shipping Policy": "In-stock orders usually leave the warehouse within two business days. Tracking appears after carrier collection. Delivery estimates are not guarantees during severe weather.",
    "Warranty Policy": "Northstar accessories include a 12-month limited warranty and selected devices include 24 months. The warranty covers manufacturing defects, not accidental damage or misuse.",
    "Order Cancellation Policy": "Orders may be cancelled only while processing or confirmed. Once fulfilment begins, support can request a carrier intercept but cannot guarantee cancellation.",
    "Billing FAQ": "Northstar never displays full payment card numbers. Pending authorisations may resemble duplicate charges. Posted duplicate charges require immediate human billing review.",
    "Product Troubleshooting": "For unresponsive electronics, disconnect power for 30 seconds, inspect the cable, reconnect to a known working outlet, and install current firmware. Stop using devices that are hot, swollen, smoking, or sparking.",
    "Human Escalation Policy": "Escalate explicit human requests, fraud or duplicate charge concerns, legal threats, safety issues, policy exceptions, repeated tool failures, high dissatisfaction, and unresolved conversations.",
}


def seed_demo_data(db: Session) -> dict[str, int]:
    if (db.scalar(select(func.count(User.id))) or 0) > 0:
        return counts(db)
    now = datetime.now(UTC)
    customers = []
    for i in range(1, 16):
        user = User(
            id=sid(f"customer-user-{i}"),
            name=f"Demo Customer {i:02d}",
            email=f"customer{i:02d}@northstar.demo",
            role="customer",
            password_hash=hash_password("Demo123!"),
        )
        profile = CustomerProfile(
            id=sid(f"customer-{i}"),
            user_id=user.id,
            phone=f"+1-555-01{i:02d}",
            loyalty_tier=("standard", "silver", "gold")[i % 3],
        )
        db.add(user)
        db.flush()
        db.add(profile)
        customers.append(profile)
    agents = []
    for i in range(1, 6):
        user = User(
            id=sid(f"agent-{i}"),
            name=f"Support Agent {i}",
            email=f"agent{i}@northstar.demo",
            role="support_agent",
            password_hash=hash_password("Agent123!"),
        )
        db.add(user)
        agents.append(user)
    db.add(
        User(
            id=sid("admin"),
            name="Northstar Administrator",
            email="admin@northstar.demo",
            role="admin",
            password_hash=hash_password("Admin123!"),
        )
    )
    products = []
    categories = ("Audio", "Mobile Accessories", "Smart Home", "Computing", "Power")
    for i in range(1, 26):
        product = Product(
            id=sid(f"product-{i}"),
            sku=f"NS-{categories[i % 5][:2].upper()}-{1000 + i}",
            name=f"Northstar {categories[i % 5]} Device {i}",
            category=categories[i % 5],
            description="Synthetic demonstration product for portfolio use.",
            price=Decimal(str(19.99 + i * 7)),
            warranty_months=24 if i % 4 == 0 else 12,
        )
        db.add(product)
        products.append(product)
    db.flush()
    statuses = ("processing", "confirmed", "in_transit", "delivered", "delivered", "cancelled")
    orders = []
    for i in range(1, 46):
        customer = customers[(i - 1) % len(customers)]
        status = statuses[i % len(statuses)]
        created = now - timedelta(days=i % 35, hours=i)
        order = Order(
            id=sid(f"order-{i}"),
            customer_id=customer.id,
            order_number=f"NS-{100000 + i}",
            status=status,
            payment_status="refunded" if status == "cancelled" else "paid",
            total_amount=Decimal(str(59.99 + i * 11)),
            shipping_address=f"{100 + i} Demo Avenue, Example City, CA 900{i % 10}0",
            created_at=created,
            updated_at=created,
        )
        db.add(order)
        orders.append(order)
    db.flush()
    for i, order in enumerate(orders, 1):
        for j in range(3):
            product = products[(i * 3 + j) % len(products)]
            db.add(
                OrderItem(
                    id=sid(f"item-{i}-{j}"),
                    order_id=order.id,
                    product_id=product.id,
                    quantity=1 if j else 2,
                    unit_price=product.price,
                )
            )
        event_names = ["confirmed", "packed", "carrier_collected"]
        if order.status in {"in_transit", "delivered"}:
            event_names.append("in_transit")
        if order.status == "delivered":
            event_names.append("delivered")
        for j, event in enumerate(event_names):
            db.add(
                ShippingEvent(
                    id=sid(f"event-{i}-{j}"),
                    order_id=order.id,
                    status=event,
                    location=("Northstar Warehouse", "Regional Hub", "Local Depot")[j % 3],
                    message=f"Synthetic carrier update: {event.replace('_', ' ')}.",
                    occurred_at=order.created_at + timedelta(hours=12 * j),
                )
            )
    for i in range(1, 31):
        customer = customers[(i - 1) % len(customers)]
        ticket = SupportTicket(
            id=sid(f"ticket-{i}"),
            customer_id=customer.id,
            subject=("Damaged item", "Refund delay", "Delivery question", "Product setup")[i % 4],
            description="Synthetic historical support issue.",
            category=("returns", "billing", "shipping", "technical")[i % 4],
            priority=("low", "normal", "high")[i % 3],
            status=("open", "waiting_customer", "resolved")[i % 3],
            assigned_agent_id=agents[i % len(agents)].id,
            created_at=now - timedelta(days=i),
        )
        db.add(ticket)
        for j in range(3):
            db.add(
                TicketMessage(
                    id=sid(f"ticket-message-{i}-{j}"),
                    ticket_id=ticket.id,
                    sender_type="customer" if j % 2 == 0 else "support_agent",
                    sender_id=customer.user_id if j % 2 == 0 else agents[i % len(agents)].id,
                    content=f"Synthetic ticket message {j + 1} for demonstration.",
                    is_internal=False,
                    created_at=now - timedelta(days=i, hours=-j),
                )
            )
    for i in range(1, 7):
        customer = customers[i - 1]
        conversation = Conversation(
            id=sid(f"conversation-{i}"),
            customer_id=customer.id,
            title=f"Demo support conversation {i}",
            status="ai_active",
        )
        db.add(conversation)
        db.flush()
        db.add(
            Message(
                conversation_id=conversation.id,
                role="customer",
                sender_id=customer.user_id,
                content="Where is my latest order?",
            )
        )
        db.add(
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content="I can check that using your verified account.",
            )
        )
    db.commit()
    seed_knowledge(db)
    return counts(db)


def seed_knowledge(db: Session) -> None:
    _, chat = services()
    for index, (title, text) in enumerate(POLICIES.items(), 1):
        document_id = sid(f"policy-{title}")
        if db.get(Document, document_id):
            continue
        filename = title.lower().replace(" ", "_") + ".md"
        document = Document(
            id=document_id,
            original_filename=filename,
            stored_filename=f"seed-{filename}",
            file_type="md",
            file_size=len(text.encode()),
            file_hash=uuid.uuid5(NAMESPACE, text).hex,
            upload_status=DocumentStatus.READY,
            chunk_count=1,
        )
        db.add(document)
        db.flush()
        chunk = Chunk(
            id=f"{document_id}:0",
            document_id=document_id,
            document_name=title,
            text=text,
            page_number=None,
            index=index,
        )
        chat.vectors.add([chunk], chat.embeddings.embed([text]))
    db.commit()


def counts(db: Session) -> dict[str, int]:
    return {
        "users": db.scalar(select(func.count(User.id))) or 0,
        "customers": db.scalar(select(func.count(CustomerProfile.id))) or 0,
        "products": db.scalar(select(func.count(Product.id))) or 0,
        "orders": db.scalar(select(func.count(Order.id))) or 0,
        "order_items": db.scalar(select(func.count(OrderItem.id))) or 0,
        "shipping_events": db.scalar(select(func.count(ShippingEvent.id))) or 0,
        "tickets": db.scalar(select(func.count(SupportTicket.id))) or 0,
        "ticket_messages": db.scalar(select(func.count(TicketMessage.id))) or 0,
        "knowledge_documents": db.scalar(select(func.count(Document.id))) or 0,
    }
