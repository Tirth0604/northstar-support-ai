import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import get_settings


def arguments_hash(action: str, arguments: dict[str, Any]) -> str:
    canonical = json.dumps({"action": action, "arguments": arguments}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_pending_action(action: str, arguments: dict[str, Any], summary: str, consequences: str) -> dict[str, Any]:
    expires = datetime.now(UTC) + timedelta(minutes=get_settings().confirmation_expire_minutes)
    nonce = secrets.token_urlsafe(18)
    digest = arguments_hash(action, arguments)
    signature = hmac.new(
        get_settings().jwt_secret_key.encode(), f"{nonce}:{digest}".encode(), hashlib.sha256
    ).hexdigest()
    return {
        "action": action,
        "arguments": arguments,
        "arguments_hash": digest,
        "confirmation_token": f"{nonce}.{signature}",
        "summary": summary,
        "consequences": consequences,
        "expires_at": expires.isoformat(),
    }


def validate_pending_action(pending: dict[str, Any] | None, token: str) -> tuple[str, dict[str, Any]]:
    if not pending:
        raise ValueError("No action is awaiting confirmation.")
    try:
        expires = datetime.fromisoformat(pending["expires_at"])
        if expires < datetime.now(UTC):
            raise ValueError("Confirmation expired. Please request the action again.")
        nonce, supplied = token.split(".", 1)
        expected = hmac.new(
            get_settings().jwt_secret_key.encode(), f"{nonce}:{pending['arguments_hash']}".encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(supplied, expected):
            raise ValueError("Confirmation does not match the pending action.")
        if arguments_hash(pending["action"], pending["arguments"]) != pending["arguments_hash"]:
            raise ValueError("Pending action was modified.")
        return pending["action"], pending["arguments"]
    except (KeyError, TypeError) as exc:
        raise ValueError("Invalid confirmation state.") from exc
