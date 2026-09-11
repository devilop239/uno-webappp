"""Signed anonymous sessions for web game rooms."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

# Prefer the Replit-managed session secret when the web app is hosted there.
# Keep UNO_SESSION_SECRET as the explicit project-level override for existing
# deployments.
_SECRET = (
    os.getenv("UNO_SESSION_SECRET")
    or os.getenv("SESSION_SECRET")
    or secrets.token_urlsafe(32)
)
_SESSION_TTL_SECONDS = int(os.getenv("UNO_SESSION_TTL_SECONDS", "86400"))


def issue_session(room_id: int, user_id: int, match_uuid: str | None = None) -> str:
    payload = {
        "room_id": int(room_id),
        "user_id": int(user_id),
        "match_uuid": match_uuid,
        "expires_at": int(time.time()) + _SESSION_TTL_SECONDS,
    }
    encoded = _encode(payload)
    signature = _sign(encoded)
    return f"{encoded}.{signature}"


def verify_session(token: str | None, room_id: int, user_id: int | None = None) -> dict[str, Any]:
    if not token or "." not in token:
        raise ValueError("A valid room session is required")
    encoded, signature = token.split(".", 1)
    expected = _sign(encoded)
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Invalid room session")
    try:
        payload = json.loads(_decode(encoded))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid room session") from exc
    if int(payload.get("room_id", -1)) != int(room_id):
        raise ValueError("Room session does not match this room")
    if int(payload.get("expires_at", 0)) <= int(time.time()):
        raise ValueError("Room session has expired")
    if user_id is not None and int(payload.get("user_id", -1)) != int(user_id):
        raise ValueError("Room session does not match this user")
    return payload


def _encode(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode(encoded: str) -> str:
    padded = encoded + "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")


def _sign(encoded: str) -> str:
    return hmac.new(_SECRET.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).hexdigest()
