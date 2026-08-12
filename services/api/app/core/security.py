"""Password hashing and JWT issuing/verification.

We use ``bcrypt`` directly rather than ``passlib`` — passlib's bcrypt backend has a long-standing
incompatibility with bcrypt >= 4.1 that produces confusing runtime warnings, and we need only two
functions from it.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import settings

TokenType = Literal["access", "refresh"]

# bcrypt truncates at 72 bytes; hashing a longer password silently ignores the tail, which would
# make two different long passwords interchangeable. We reject instead of truncating.
MAX_PASSWORD_BYTES = 72


class InvalidTokenError(Exception):
    """Raised when a token is malformed, expired, or of the wrong type."""


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError("Password must be at most 72 bytes when UTF-8 encoded")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:MAX_PASSWORD_BYTES],
                              password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _create_token(subject: str, token_type: TokenType, expires: dt.timedelta,
                  extra: dict[str, Any] | None = None) -> str:
    now = dt.datetime.now(dt.UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, role: str) -> str:
    return _create_token(
        subject,
        "access",
        dt.timedelta(minutes=settings.access_token_expire_minutes),
        {"role": role},
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(
        subject, "refresh", dt.timedelta(days=settings.refresh_token_expire_days)
    )


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    if payload.get("type") != expected_type:
        # Without this check a refresh token would be accepted as an access token, defeating the
        # point of having short-lived access tokens at all.
        raise InvalidTokenError(f"Expected a {expected_type} token")
    return payload
