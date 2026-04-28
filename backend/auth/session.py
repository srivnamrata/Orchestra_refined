"""
JWT-based session store.

Tokens are signed JWTs — verifiable on any container without shared state.
Redis is used as an optional revocation cache (logout blacklist).
In-memory fallback used when Redis is unavailable.

Benefits over pure server-side sessions:
- Survives Cloud Run deployments and scale-out (no shared memory needed)
- No Redis required for basic functionality
- Still supports logout (via Redis/memory denylist)
"""

import os
import json
import time
import secrets
import logging
from typing import Optional

import jwt

logger = logging.getLogger(__name__)

# Secret key for signing JWTs — set JWT_SECRET in env for production
_JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
_ALGORITHM  = "HS256"

# In-memory denylist for logout (fallback when Redis unavailable)
_denylisted: set = set()


# ── Token creation ────────────────────────────────────────────────────────────

def create_session(redis_client, user_id: int, email: str, name: str, ttl: int) -> str:
    """Create a signed JWT. redis_client is accepted but not required."""
    now     = int(time.time())
    payload = {
        "sub":   str(user_id),
        "email": email,
        "name":  name,
        "iat":   now,
        "exp":   now + ttl,
        "jti":   secrets.token_urlsafe(8),   # unique token id for revocation
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_ALGORITHM)


# ── Token validation ──────────────────────────────────────────────────────────

def get_session(redis_client, token: str) -> Optional[dict]:
    """Decode and validate a JWT. Returns user dict or None."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

    jti = payload.get("jti", "")

    # Check revocation via Redis
    if redis_client is not None:
        try:
            if redis_client.get(f"orch:revoked:{jti}"):
                return None
        except Exception:
            pass

    # Check in-memory denylist
    if jti in _denylisted:
        return None

    return {
        "user_id": int(payload["sub"]),
        "email":   payload["email"],
        "name":    payload["name"],
    }


def refresh_session(redis_client, token: str, ttl: int) -> bool:
    """JWTs are self-expiring — no rolling needed. No-op."""
    return True


def delete_session(redis_client, token: str) -> None:
    """Revoke token by adding its jti to denylist."""
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_ALGORITHM],
                             options={"verify_exp": False})
        jti = payload.get("jti", "")
        exp = payload.get("exp", int(time.time()) + 3600)
        ttl = max(1, exp - int(time.time()))

        if redis_client is not None:
            try:
                redis_client.setex(f"orch:revoked:{jti}", ttl, "1")
                return
            except Exception:
                pass
        _denylisted.add(jti)
    except Exception:
        pass
