"""
Redis-backed session store.
Session token → user dict with a rolling TTL.
"""

import json
import secrets
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SESSION_PREFIX = "orch:session:"


def _key(token: str) -> str:
    return f"{SESSION_PREFIX}{token}"


def create_session(redis_client, user_id: int, email: str, name: str, ttl: int) -> str:
    token = secrets.token_urlsafe(32)
    payload = json.dumps({"user_id": user_id, "email": email, "name": name})
    redis_client.setex(_key(token), ttl, payload)
    return token


def get_session(redis_client, token: str) -> Optional[dict]:
    raw = redis_client.get(_key(token))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def refresh_session(redis_client, token: str, ttl: int) -> bool:
    return bool(redis_client.expire(_key(token), ttl))


def delete_session(redis_client, token: str) -> None:
    redis_client.delete(_key(token))
