"""Minimal signed demo tokens and password hashing without external auth services."""

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings


def hash_password(password: str) -> str:
    return hashlib.sha256(f"northstar:{password}".encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(user_id: str, role: str) -> str:
    settings = get_settings()
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    exp = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = _b64(
        json.dumps({"sub": user_id, "role": role, "exp": int(exp.timestamp())}, separators=(",", ":")).encode()
    )
    signature = _b64(
        hmac.new(settings.jwt_secret_key.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    )
    return f"{header}.{payload}.{signature}"


def decode_access_token(token: str) -> dict:
    try:
        header, payload, signature = token.split(".")
        expected = _b64(
            hmac.new(get_settings().jwt_secret_key.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            raise ValueError("bad signature")
        claims = json.loads(_unb64(payload))
        if int(claims["exp"]) < int(datetime.now(UTC).timestamp()):
            raise ValueError("expired")
        return claims
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid or expired access token") from exc
