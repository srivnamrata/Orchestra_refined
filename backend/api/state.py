"""
Shared singleton state for all routers.
Populated by the lifespan handler in app.py; imported by routers at call time.
"""

import asyncio
from datetime import datetime

# ── Global Thought Bus ───────────────────────────────────────────────────────
thought_bus: asyncio.Queue = asyncio.Queue(maxsize=500)
_thought_subscribers: list = []


def emit_thought(agent: str, role: str, message: str, thought_type: str = "thought"):
    event = {
        "agent":   agent,
        "role":    role,
        "message": message,
        "type":    thought_type,
        "ts":      datetime.now().strftime("%H:%M:%S"),
    }
    for q in list(_thought_subscribers):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


# ── Service & Agent Singletons (set during lifespan) ─────────────────────────
llm_service       = None
pubsub_service    = None
knowledge_graph   = None
critic_agent      = None
security_auditor  = None
orchestrator      = None
github_service    = None
slack_service     = None
email_service     = None
proactive_monitor = None
veda_librarian    = None
param_mitra       = None
debate_engine     = None
config            = None
redis_client      = None
