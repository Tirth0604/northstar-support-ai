"""Bounded, deterministic agent workflow used by mock mode and as a safety shell for LLM providers."""

import re
import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Citation, Conversation, CustomerProfile, Message, Order, User
from app.rag.prompts import REFUSAL, build_grounded_prompt
from app.schemas.support import AgentResponse, CitationPayload
from app.services.confirmation import build_pending_action, validate_pending_action
from app.services.container import services
from app.services.sentiment import classify_sentiment
from app.tools.registry import ToolContext, ToolExecutor

INJECTION_MARKERS = (
    "ignore previous",
    "ignore system",
    "reveal your prompt",
    "show system prompt",
    "developer message",
    "execute code",
    "change your permissions",
)
POLICY_TERMS = (
    "policy",
    "refund",
    "return",
    "warranty",
    "opened product",
    "billing",
    "troubleshoot",
    "shipping policy",
    "cancel policy",
)


@dataclass
class Intent:
    name: str
    action_based: bool
    confidence: float


def classify_intent(text: str) -> Intent:
    value = text.lower()
    if re.fullmatch(r"\s*(hi|hello|hey|good morning|good afternoon|good evening)[!.,\s]*", value):
        return Intent("greeting", False, 0.99)
    if any(term in value for term in ("human", "real person", "representative", "manager")):
        return Intent("human_escalation", True, 0.98)
    if "cancel" in value and "order" in value:
        return Intent("cancel_order", True, 0.93)
    if ("where is" in value and "order" in value) or any(
        term in value
        for term in ("where is my order", "shipping status", "delivery progress", "tracking", "track order")
    ):
        return Intent("shipping_status", False, 0.94)
    if any(
        term in value
        for term in (
            "current orders",
            "my orders",
            "all orders",
            "order history",
            "recent orders",
            "show orders",
            "list orders",
            "past orders",
            "my purchases",
        )
    ):
        return Intent("order_list", False, 0.94)
    if "order" in value and any(term in value for term in ("status", "details")):
        return Intent("order_lookup", False, 0.9)
    if "return" in value and any(term in value for term in ("eligible", "can i", "start")):
        return Intent("return_eligibility", False, 0.87)
    if any(term in value for term in ("ticket", "case")) and any(
        term in value for term in ("create", "open", "report", "submit")
    ):
        return Intent("create_ticket", True, 0.88)
    if any(term in value for term in POLICY_TERMS):
        return Intent("knowledge_question", False, 0.82)
    return Intent("knowledge_question", False, 0.55)


class SupportWorkflow:
    """Executes at most one business tool per customer turn, plus optional retrieval."""

    def __init__(self) -> None:
        self.executor = ToolExecutor()

    def _context(self, db: Session, user: User, conversation: Conversation) -> ToolContext:
        customer = (
            db.scalar(select(CustomerProfile).where(CustomerProfile.user_id == user.id))
            if user.role == "customer"
            else None
        )
        return ToolContext(db=db, user=user, customer=customer, conversation=conversation)

    def _resolve_order(self, text: str, ctx: ToolContext) -> Order | None:
        if not ctx.customer:
            return None
        match = re.search(r"NS-\d{6}", text.upper())
        query = select(Order).where(Order.customer_id == ctx.customer.id)
        query = query.where(Order.order_number == match.group(0)) if match else query.order_by(Order.created_at.desc())
        return ctx.db.scalar(query)

    def _persist_response(
        self, conversation: Conversation, db: Session, response: AgentResponse, latency_ms: int
    ) -> Message:
        message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=response.message,
            structured_payload=response.model_dump(mode="json"),
            latency_ms=latency_ms,
            grounding_status="grounded" if response.citations else None,
        )
        db.add(message)
        db.flush()
        return message

    async def _knowledge(self, text: str, conversation: Conversation, db: Session) -> AgentResponse:
        _, chat = services()
        query = chat.embeddings.embed([text])[0]
        results = chat.vectors.search(query, chat.settings.retrieval_top_k, chat.settings.similarity_threshold, None)
        if len(results) < chat.settings.minimum_evidence:
            return AgentResponse(response_type="refusal", message=REFUSAL)
        prompt = build_grounded_prompt(
            text, [(i, r.chunk.document_name, r.chunk.text, r.chunk.page_number) for i, r in enumerate(results, 1)]
        )
        answer = await chat.llm.generate(text, prompt, results)
        citations = [
            CitationPayload(
                document_id=r.chunk.document_id,
                document_name=r.chunk.document_name,
                section="Indexed policy section",
                page_number=r.chunk.page_number,
                excerpt=r.chunk.text[:420],
                relevance_score=r.score,
            )
            for r in results
        ]
        return AgentResponse(response_type="informational_answer", message=answer, citations=citations)

    async def process(self, text: str, conversation: Conversation, user: User, db: Session) -> AgentResponse:
        started = time.perf_counter()
        if not conversation.ai_enabled:
            return AgentResponse(
                response_type="human_message",
                message="A human support agent is handling this conversation. Your message has been added to the queue.",
            )
        db.add(Message(conversation_id=conversation.id, role="customer", sender_id=user.id, content=text))
        ctx = self._context(db, user, conversation)
        signal = classify_sentiment(text)
        lower = text.lower()
        if any(marker in lower for marker in INJECTION_MARKERS):
            response = AgentResponse(
                response_type="refusal",
                message="I canÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢t follow instructions that request internal prompts, secrets, permission changes, or unauthorised access. I can still help with your Northstar support issue.",
            )
        elif signal.escalation_required:
            event = self.executor.execute(
                "escalate_to_human",
                {
                    "reason": signal.reason_codes[0] if signal.reason_codes else "high_dissatisfaction",
                    "sentiment": signal.sentiment,
                },
                ctx,
            )
            response = AgentResponse(
                response_type="human_escalation",
                message="IÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ve escalated this conversation to a human support agent. The AI is now paused, and the handoff includes the context already shared.",
                tool_events=[event],
                escalation=event["result"],
                ui_payload={"handoff": event["result"]["handoff"]},
            )
        else:
            intent = classify_intent(text)
            order = self._resolve_order(text, ctx)
            if intent.name == "greeting":
                response = AgentResponse(
                    response_type="informational_answer",
                    message=(
                        "Hi! I can help with your orders, shipping, returns, policies, support tickets, "
                        "or connect you with a human agent. What would you like help with?"
                    ),
                )
            elif intent.name == "human_escalation":
                event = self.executor.execute(
                    "escalate_to_human", {"reason": "explicit_human_request", "sentiment": signal.sentiment}, ctx
                )
                response = AgentResponse(
                    response_type="human_escalation",
                    message="IÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ve escalated your conversation to a human support agent. AI replies are paused until an agent releases the conversation.",
                    tool_events=[event],
                    escalation=event["result"],
                )
            elif intent.name == "cancel_order":
                if not order:
                    response = AgentResponse(
                        response_type="clarifying_question",
                        message="Which of your orders would you like to cancel? Please provide the Northstar order number.",
                    )
                else:
                    eligibility = self.executor.execute("check_cancellation_eligibility", {"order_id": order.id}, ctx)
                    if not eligibility["result"]["eligible"]:
                        response = AgentResponse(
                            response_type="tool_result",
                            message=f"Order {order.order_number} canÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢t be cancelled because it has already entered fulfilment. I can escalate this if you need a policy exception.",
                            tool_events=[eligibility],
                            ui_payload={"order_card": eligibility["result"]},
                        )
                    else:
                        pending = build_pending_action(
                            "cancel_order",
                            {"order_id": order.id},
                            f"Cancel order {order.order_number}",
                            "Cancellation is final and stops fulfilment. Any captured payment will follow the refund policy.",
                        )
                        conversation.pending_action = pending
                        response = AgentResponse(
                            response_type="confirmation_required",
                            message=f"Order {order.order_number} is eligible for cancellation. This is final and may initiate a refund. Please confirm to continue.",
                            tool_events=[eligibility],
                            requires_confirmation=True,
                            pending_action=pending,
                            ui_payload={
                                "order_card": {
                                    "id": order.id,
                                    "order_number": order.order_number,
                                    "status": order.status,
                                }
                            },
                        )
            elif intent.name == "order_list":
                event = self.executor.execute("list_customer_orders", {}, ctx)
                orders = event["result"]["orders"]
                if orders:
                    summary = "; ".join(
                        f"{item['order_number']} - {item['status'].replace('_', ' ')}, ${item['total_amount']:.2f}"
                        for item in orders
                    )
                    message = f"You currently have {len(orders)} orders: {summary}."
                else:
                    message = "I couldn't find any orders in your verified account."
                response = AgentResponse(
                    response_type="tool_result",
                    message=message,
                    tool_events=[event],
                    ui_payload={"orders": orders},
                )
            elif intent.name in {"shipping_status", "order_lookup", "return_eligibility"}:
                if not order:
                    response = AgentResponse(
                        response_type="clarifying_question",
                        message="I couldnÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢t find an order in your verified account. Please choose an order from the Orders page.",
                    )
                else:
                    tool = (
                        "get_shipping_status"
                        if intent.name == "shipping_status"
                        else "check_return_eligibility"
                        if intent.name == "return_eligibility"
                        else "get_order_details"
                    )
                    event = self.executor.execute(tool, {"order_id": order.id}, ctx)
                    data = event["result"]
                    if tool == "get_shipping_status":
                        latest = data["timeline"][-1] if data["timeline"] else None
                        message = f"Order {order.order_number} is {data['status'].replace('_', ' ')}." + (
                            f" Latest update: {latest['message']}"
                            if latest
                            else " No carrier events are available yet."
                        )
                        ui = {"order_card": data, "shipping_timeline": data["timeline"]}
                    elif tool == "check_return_eligibility":
                        message = f"Order {order.order_number} is {'eligible' if data['eligible'] else 'not currently eligible'} for return. {data['reason']}"
                        ui = {"order_card": data}
                    else:
                        message = f"Order {data['order_number']} is {data['status'].replace('_', ' ')} and payment is {data['payment_status'].replace('_', ' ')}."
                        ui = {"order_card": data}
                    response = AgentResponse(
                        response_type="tool_result", message=message, tool_events=[event], ui_payload=ui
                    )
            elif intent.name == "create_ticket":
                event = self.executor.execute(
                    "create_support_ticket",
                    {"subject": text[:120], "description": text, "category": "general", "priority": "normal"},
                    ctx,
                )
                response = AgentResponse(
                    response_type="ticket_created",
                    message=f"I created support ticket {event['result']['ticket_id'][:8]} for this issue.",
                    tool_events=[event],
                    ui_payload={"ticket_card": event["result"]},
                )
            else:
                response = await self._knowledge(text, conversation, db)
        elapsed = round((time.perf_counter() - started) * 1000)
        persisted = self._persist_response(conversation, db, response, elapsed)
        for item in response.citations:
            db.add(
                Citation(
                    message_id=persisted.id,
                    document_id=item.document_id,
                    document_name=item.document_name,
                    chunk_id=f"agent-{item.document_id[:8]}-{persisted.id[:8]}",
                    page_number=item.page_number,
                    excerpt=item.excerpt,
                    relevance_score=item.relevance_score,
                )
            )
        db.commit()
        return response

    def confirm(
        self, token: str, confirmed: bool, conversation: Conversation, user: User, db: Session
    ) -> AgentResponse:
        ctx = self._context(db, user, conversation)
        if not confirmed:
            conversation.pending_action = None
            response = AgentResponse(
                response_type="action_completed", message="The pending action was cancelled. No changes were made."
            )
        else:
            action, arguments = validate_pending_action(conversation.pending_action, token)
            event = self.executor.execute(action, arguments, ctx, confirmed=True)
            conversation.pending_action = None
            response = AgentResponse(
                response_type="action_completed",
                message=f"The action completed successfully. Order {event['result'].get('order_number', '')} is now {event['result'].get('status', 'updated')}.",
                tool_events=[event],
                ui_payload={"order_card": event["result"]},
            )
        self._persist_response(conversation, db, response, 0)
        db.commit()
        return response
