"""
Session store: Redis when available, in-memory dict fallback for local dev.
Token → user dict with a rolling TTL.
"""

import json
import secrets
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SESSION_PREFIX = "orch:session:"

# ── In-memory fallback (used when Redis is unavailable) ───────────────────────
# { token: {"payload": {...}, "expires_at": float} }
_mem: dict = {}


def _mem_purge():
    now = time.time()
    expired = [k for k, v in _mem.items() if v["expires_at"] < now]
    for k in expired:
        del _mem[k]


def _key(token: str) -> str:
    return f"{SESSION_PREFIX}{token}"


# ── Public API (redis_client may be None) ─────────────────────────────────────

def create_session(redis_client, user_id: int, email: str, name: str, ttl: int) -> str:
    token   = secrets.token_urlsafe(32)
    payload = {"user_id": user_id, "email": email, "name": name}

    if redis_client is not None:
        redis_client.setex(_key(token), ttl, json.dumps(payload))
    else:
        _mem_purge()
        _mem[token] = {"payload": payload, "expires_at": time.time() + ttl}
        logger.debug("Session stored in memory (Redis unavailable)")

    return token


def get_session(redis_client, token: str) -> Optional[dict]:
    if redis_client is not None:
        raw = redis_client.get(_key(token))
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None
    else:
        entry = _mem.get(token)
        if not entry or entry["expires_at"] < time.time():
            _mem.pop(token, None)
            return None
        return entry["payload"]


def refresh_session(redis_client, token: str, ttl: int) -> bool:
    if redis_client is not None:
        return bool(redis_client.expire(_key(token), ttl))
    else:
        entry = _mem.get(token)
        if entry:
            entry["expires_at"] = time.time() + ttl
            return True
        return False


def delete_session(redis_client, token: str) -> None:
    if redis_client is not None:
        redis_client.delete(_key(token))
    else:
        _mem.pop(token, None)
