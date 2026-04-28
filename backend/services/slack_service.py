"""
Slack Integration Service
Fetches real data via Slack Web API using a Bot/User OAuth token.
Token scopes needed: channels:history, channels:read, users:read, search:read
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import httpx

logger = logging.getLogger(__name__)
SLACK_API = "https://slack.com/api"


class SlackService:
    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def get_summary(self, token: str, channels: list = None) -> dict:
        """Returns last 7 days of messages from joined channels, filtered for mentions."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # Who am I?
                auth = (await client.get(f"{SLACK_API}/auth.test",
                                         headers=self._headers(token))).json()
                if not auth.get("ok"):
                    raise ValueError(f"Slack auth failed: {auth.get('error')}")

                user_id  = auth.get("user_id", "")
                username = auth.get("user", "unknown")

                # List joined channels
                ch_resp = (await client.get(
                    f"{SLACK_API}/conversations.list",
                    headers=self._headers(token),
                    params={"types": "public_channel,private_channel",
                            "exclude_archived": True, "limit": 20},
                )).json()
                all_channels = [c for c in ch_resp.get("channels", []) if c.get("is_member")]

                # Target only provided channels or take first 5 joined
                target = channels or [c["id"] for c in all_channels[:5]]

                oldest = str((datetime.now(timezone.utc) - timedelta(days=7)).timestamp())
                messages, mentions, action_items = [], [], []

                for ch_id in target:
                    hist = (await client.get(
                        f"{SLACK_API}/conversations.history",
                        headers=self._headers(token),
                        params={"channel": ch_id, "oldest": oldest, "limit": 50},
                    )).json()
                    ch_name = next((c["name"] for c in all_channels if c["id"] == ch_id), ch_id)

                    for msg in hist.get("messages", []):
                        text = msg.get("text", "")
                        ts   = datetime.fromtimestamp(float(msg.get("ts", 0))).strftime("%b %d %H:%M")

                        if f"<@{user_id}>" in text:
                            mentions.append({
                                "text":    text[:120],
                                "channel": f"#{ch_name}",
                                "ts":      ts,
                                "url":     f"https://slack.com/app_redirect?channel={ch_id}",
                            })
                        if any(kw in text.lower() for kw in ["action:", "todo:", "follow up", "you need to", "please"]):
                            action_items.append({
                                "text":    text[:120],
                                "channel": f"#{ch_name}",
                                "ts":      ts,
                            })
                        messages.append({
                            "text":    text[:100],
                            "channel": f"#{ch_name}",
                            "ts":      ts,
                            "type":    "mention" if f"<@{user_id}>" in text else "message",
                        })

                return {
                    "username":    username,
                    "user_id":     user_id,
                    "channels":    [{"id": c["id"], "name": c["name"],
                                     "unread": c.get("unread_count", 0)}
                                    for c in all_channels[:10]],
                    "mentions":    mentions[:10],
                    "action_items": action_items[:8],
                    "recent":      messages[:15],
                    "week_count":  len(messages),
                }
        except Exception as e:
            logger.error(f"Slack API error: {e}")
            raise

    async def get_channel_summary(self, channel_name="#general"):
        return {"summaries": [], "channel": channel_name}


def create_slack_service():
    return SlackService()
