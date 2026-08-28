from datetime import UTC, datetime, timedelta

import pytest

from app.agents.workflow import classify_intent
from app.services.confirmation import build_pending_action, validate_pending_action
from app.services.sentiment import classify_sentiment


def test_classifier():
    assert classify_intent("hi").name == "greeting"
    assert classify_intent("Where is my order?").name == "shipping_status"
    assert classify_intent("what are my current orders").name == "order_list"
    assert classify_intent("show my order history").name == "order_list"


def test_risk():
    assert classify_sentiment("battery is swollen and smoking").escalation_required


def test_confirmation_binding():
    p = build_pending_action("cancel_order", {"order_id": "a"}, "Cancel", "Final")
    assert validate_pending_action(p, p["confirmation_token"])[0] == "cancel_order"
    q = dict(p)
    q["expires_at"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    with pytest.raises(ValueError):
        validate_pending_action(q, p["confirmation_token"])
