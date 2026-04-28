"""
Integrations router — connect/disconnect + live data fetch for GitHub, Slack, Gmail.
Each endpoint requires a valid session (user scoped).
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from backend.api import state
from backend.auth.deps import get_current_user
from backend.database import upsert_integration, get_integration, delete_integration

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Integrations"])


# ── Pydantic models ──────────────────────────────────────────────────────────

class GitHubConnectRequest(BaseModel):
    token: str                       # Personal Access Token

class SlackConnectRequest(BaseModel):
    token: str                       # Bot or User OAuth token
    channels: Optional[list] = None  # optional channel IDs to monitor

class GmailConnectRequest(BaseModel):
    refresh_token: str
    client_id:     str
    client_secret: str


# ── GitHub ────────────────────────────────────────────────────────────────────

@router.post("/api/integrations/github/connect")
async def github_connect(req: GitHubConnectRequest, user=Depends(get_current_user)):
    upsert_integration(user["user_id"], "github", req.token)
    return {"status": "connected", "service": "github"}


@router.delete("/api/integrations/github/connect")
async def github_disconnect(user=Depends(get_current_user)):
    delete_integration(user["user_id"], "github")
    return {"status": "disconnected", "service": "github"}


@router.get("/api/integrations/github")
async def github_data(user=Depends(get_current_user)):
    row = get_integration(user["user_id"], "github")
    if not row or not row["token"]:
        raise HTTPException(status_code=404, detail="GitHub not connected")
    try:
        return await state.github_service.get_summary(row["token"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GitHub API error: {e}")


@router.get("/api/integrations/github/status")
async def github_status(user=Depends(get_current_user)):
    row = get_integration(user["user_id"], "github")
    return {"connected": bool(row and row["token"]),
            "connected_at": row["connected_at"].isoformat() if row else None}


# ── Slack ─────────────────────────────────────────────────────────────────────

@router.post("/api/integrations/slack/connect")
async def slack_connect(req: SlackConnectRequest, user=Depends(get_current_user)):
    extra = {"channels": req.channels} if req.channels else {}
    upsert_integration(user["user_id"], "slack", req.token, extra)
    return {"status": "connected", "service": "slack"}


@router.delete("/api/integrations/slack/connect")
async def slack_disconnect(user=Depends(get_current_user)):
    delete_integration(user["user_id"], "slack")
    return {"status": "disconnected", "service": "slack"}


@router.get("/api/integrations/slack")
async def slack_data(user=Depends(get_current_user)):
    row = get_integration(user["user_id"], "slack")
    if not row or not row["token"]:
        raise HTTPException(status_code=404, detail="Slack not connected")
    try:
        channels = row["extra"].get("channels") if row["extra"] else None
        return await state.slack_service.get_summary(row["token"], channels)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Slack API error: {e}")


@router.get("/api/integrations/slack/status")
async def slack_status(user=Depends(get_current_user)):
    row = get_integration(user["user_id"], "slack")
    return {"connected": bool(row and row["token"]),
            "connected_at": row["connected_at"].isoformat() if row else None}


# ── Gmail ─────────────────────────────────────────────────────────────────────

@router.post("/api/integrations/gmail/connect")
async def gmail_connect(req: GmailConnectRequest, user=Depends(get_current_user)):
    upsert_integration(user["user_id"], "gmail", req.refresh_token, {
        "client_id":     req.client_id,
        "client_secret": req.client_secret,
    })
    return {"status": "connected", "service": "gmail"}


@router.delete("/api/integrations/gmail/connect")
async def gmail_disconnect(user=Depends(get_current_user)):
    delete_integration(user["user_id"], "gmail")
    return {"status": "disconnected", "service": "gmail"}


@router.get("/api/integrations/gmail")
async def gmail_data(user=Depends(get_current_user)):
    row = get_integration(user["user_id"], "gmail")
    if not row or not row["token"]:
        raise HTTPException(status_code=404, detail="Gmail not connected")
    extra = row["extra"] or {}
    try:
        return await state.email_service.get_summary(
            refresh_token=row["token"],
            client_id=extra.get("client_id", ""),
            client_secret=extra.get("client_secret", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gmail API error: {e}")


@router.get("/api/integrations/gmail/status")
async def gmail_status(user=Depends(get_current_user)):
    row = get_integration(user["user_id"], "gmail")
    return {"connected": bool(row and row["token"]),
            "connected_at": row["connected_at"].isoformat() if row else None}


# ── Status for all integrations at once (used by settings page) ──────────────

@router.get("/api/integrations/status")
async def all_status(user=Depends(get_current_user)):
    uid = user["user_id"]
    result = {}
    for svc in ["github", "slack", "gmail"]:
        row = get_integration(uid, svc)
        result[svc] = {
            "connected":    bool(row and row["token"]),
            "connected_at": row["connected_at"].isoformat() if row else None,
        }
    return result


# ── Feedback (unchanged) ──────────────────────────────────────────────────────

@router.post("/api/feedback")
async def submit_feedback(request: Request):
    data = await request.json()
    logger.info(f"FEEDBACK: Agent={data.get('agent')} Type={data.get('type')}")
    return {"status": "success"}
