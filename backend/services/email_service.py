"""
Gmail Integration Service
Fetches real data via Gmail API using a stored OAuth refresh token.
Scopes needed: gmail.readonly
"""

import logging
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional
import httpx

logger = logging.getLogger(__name__)
GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API       = "https://gmail.googleapis.com/gmail/v1"


class EmailService:
    async def _refresh_access_token(self, client: httpx.AsyncClient,
                                    refresh_token: str, client_id: str,
                                    client_secret: str) -> str:
        resp = await client.post(GMAIL_TOKEN_URL, data={
            "grant_type":    "refresh_token",
            "refresh_token": refresh_token,
            "client_id":     client_id,
            "client_secret": client_secret,
        })
        data = resp.json()
        if "access_token" not in data:
            raise ValueError(f"Token refresh failed: {data.get('error_description', data)}")
        return data["access_token"]

    async def get_summary(self, refresh_token: str, client_id: str,
                          client_secret: str) -> dict:
        """Fetch unread + starred + important emails from last 7 days."""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                access_token = await self._refresh_access_token(
                    client, refresh_token, client_id, client_secret)
                headers = {"Authorization": f"Bearer {access_token}"}

                # Profile
                profile = (await client.get(f"{GMAIL_API}/users/me/profile",
                                             headers=headers)).json()
                email_addr = profile.get("emailAddress", "")
                unread     = profile.get("messagesUnread", 0)

                after_ts = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp())

                async def search(q: str, max_results: int = 10):
                    resp = (await client.get(
                        f"{GMAIL_API}/users/me/messages",
                        headers=headers,
                        params={"q": q, "maxResults": max_results},
                    )).json()
                    msgs = []
                    for m in resp.get("messages", []):
                        detail = (await client.get(
                            f"{GMAIL_API}/users/me/messages/{m['id']}",
                            headers=headers,
                            params={"format": "metadata",
                                    "metadataHeaders": "Subject,From,Date"},
                        )).json()
                        hdrs = {h["name"]: h["value"]
                                for h in detail.get("payload", {}).get("headers", [])}
                        msgs.append({
                            "id":      m["id"],
                            "subject": hdrs.get("Subject", "(no subject)")[:80],
                            "from":    hdrs.get("From", "")[:60],
                            "date":    hdrs.get("Date", "")[:16],
                            "snippet": detail.get("snippet", "")[:120],
                            "url":     f"https://mail.google.com/mail/u/0/#inbox/{m['id']}",
                            "labels":  detail.get("labelIds", []),
                        })
                    return msgs

                urgent   = await search(f"is:unread is:important after:{after_ts}", 8)
                starred  = await search("is:starred is:unread", 5)
                all_unread = await search("is:unread", 10)

                # Tag priority
                for m in urgent:
                    m["priority"] = "high"
                for m in starred:
                    m["priority"] = "high"
                for m in all_unread:
                    m["priority"] = "medium"

                seen = set()
                combined = []
                for m in urgent + starred + all_unread:
                    if m["id"] not in seen:
                        seen.add(m["id"])
                        combined.append(m)

                return {
                    "email":          email_addr,
                    "unread_count":   unread,
                    "urgent":         combined[:10],
                    "week_total":     len(combined),
                }
        except Exception as e:
            logger.error(f"Gmail API error: {e}")
            raise

    async def get_unread_summaries(self):
        return {"urgent": [], "unread_count": 0}


def create_email_service():
    return EmailService()
