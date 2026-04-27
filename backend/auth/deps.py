"""
FastAPI dependency: extract and validate the session token from
the X-Session-Token request header.
"""

from fastapi import Header, HTTPException, status
from backend.api import state
from backend.auth.session import get_session, refresh_session


async def get_current_user(x_session_token: str = Header(default="")):
    if not x_session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    cfg = state.config
    session = get_session(state.redis_client, x_session_token)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid")
    # Roll the TTL on each request
    refresh_session(state.redis_client, x_session_token, cfg.SESSION_TTL_SECONDS)
    return session


async def get_current_user_optional(x_session_token: str = Header(default="")):
    """Returns session dict if authenticated, None otherwise (for public-compatible routes)."""
    if not x_session_token or state.redis_client is None:
        return None
    return get_session(state.redis_client, x_session_token)
