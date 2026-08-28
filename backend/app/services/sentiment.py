import re
from typing import Literal

from app.schemas.support import SentimentResult

RULES = {
    "legal_threat": ("lawyer", "sue", "legal action", "attorney"),
    "fraud_concern": ("fraud", "stolen card", "unauthorized"),
    "charge_dispute": ("charged twice", "duplicate charge", "chargeback"),
    "safety_concern": ("fire", "smoke", "electric shock", "unsafe", "battery swollen", "swollen"),
    "explicit_human": ("human", "real person", "representative", "manager"),
}


def classify_sentiment(text: str) -> SentimentResult:
    """Return a transparent rule-based signal, not a psychological assessment."""
    clean = re.sub(r"\s+", " ", text.lower())
    reasons = [
        code
        for code, phrases in RULES.items()
        if any(re.search(rf"\b{re.escape(phrase)}\b", clean) for phrase in phrases)
    ]
    angry = any(word in clean for word in ("furious", "unacceptable", "ridiculous", "angry", "worst"))
    frustrated = angry or any(word in clean for word in ("frustrated", "again", "still waiting", "not resolved"))
    confused = any(word in clean for word in ("confused", "don't understand", "how do i"))
    sentiment: Literal["positive", "neutral", "confused", "frustrated", "angry"] = (
        "angry" if angry else "frustrated" if frustrated else "confused" if confused else "neutral"
    )
    critical = any(code in reasons for code in ("legal_threat", "fraud_concern", "safety_concern"))
    high = critical or "charge_dispute" in reasons or angry
    urgency: Literal["low", "normal", "high", "critical"] = "critical" if critical else "high" if high else "normal"
    escalate = bool(reasons) or angry
    return SentimentResult(
        sentiment=sentiment,
        urgency=urgency,
        escalation_required=escalate,
        reason_codes=reasons,
        confidence=0.9 if reasons else 0.7,
    )
