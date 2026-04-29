"""
Proactive Monitor Agent
=======================
Runs on a background timer. Scans your real data (Tasks DB, Calendar DB,
plus connector stubs for GitHub / Slack / Email) and feeds findings into
the existing CriticAgent + AuditorAgent pipeline.

Unlike every other agent in this system, this one is NEVER triggered by the
user. It wakes up on its own, thinks out loud via a reasoning queue, and
surfaces "Silent Bottlenecks" — things that are about to go wrong that
nobody asked it to look at.

Reasoning visibility
--------------------
Every internal thought is pushed to `self.reasoning_queue` as a typed event:
    {"type": "thought|finding|action|alert", "agent": "...", "message": "...", "ts": "..."}

The SSE endpoint drains this queue and streams it to the frontend in real time.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import AsyncGenerator, Dict, List, Any, Optional

logger = logging.getLogger(__name__)


# ── Connector stubs ───────────────────────────────────────────────────────────
# Each returns a list of findings. Swap the body for real API calls when you
# have OAuth tokens / webhooks wired up.

async def _fetch_github_findings() -> List[Dict]:
    """Stub: returns open PRs with failing CI. Replace with real GitHub API."""
    await asyncio.sleep(0.1)
    return [
        {"source": "github", "type": "failing_pr",
         "title": "PR #42 — API rate limiter", "detail": "2 failing checks: unit-tests, lint",
         "severity": "high", "url": "https://github.com/org/repo/pull/42"},
        {"source": "github", "type": "stale_pr",
         "title": "PR #38 — DB migration", "detail": "Open 6 days, no reviewer assigned",
         "severity": "medium", "url": "https://github.com/org/repo/pull/38"},
    ]

async def _fetch_slack_findings() -> List[Dict]:
    """Stub: returns unread @mentions that look like blockers."""
    await asyncio.sleep(0.1)
    return [
        {"source": "slack", "type": "unanswered_mention",
         "title": "@you in #backend", "detail": "Can you unblock the deploy pipeline?",
         "severity": "high", "channel": "#backend"},
    ]

async def _fetch_email_findings() -> List[Dict]:
    """Stub: returns emails flagged as requiring action."""
    await asyncio.sleep(0.1)
    return [
        {"source": "email", "type": "awaiting_reply",
         "title": "Re: Product launch sign-off", "detail": "Waiting 48h, no reply",
         "severity": "high", "from": "cto@company.com"},
    ]


# ── Main agent ────────────────────────────────────────────────────────────────

class ProactiveMonitorAgent:
    """
    The always-on background intelligence layer.

    Key methods
    -----------
    start()         — start the background scan loop
    stop()          — graceful shutdown
    run_scan()      — run one full scan cycle (also callable on-demand)
    reasoning_stream() — async generator yielding reasoning events for SSE
    """

    SCAN_INTERVAL_SECONDS = 300   # scan every 5 minutes in prod
    DEADLINE_WARN_HOURS   = 48    # warn if an event is within 48h

    def __init__(self, llm_service, critic_agent, auditor_agent,
                 knowledge_graph, pubsub_service, param_mitra_agent=None):
        self.llm            = llm_service
        self.critic         = critic_agent
        self.auditor        = auditor_agent
        self.kg             = knowledge_graph
        self.pubsub         = pubsub_service
        self.param_mitra    = param_mitra_agent

        self._running       = False
        self._task: Optional[asyncio.Task] = None

        # Reasoning queue — drained by the SSE stream endpoint
        self.reasoning_queue: asyncio.Queue = asyncio.Queue()

        # Notification store — persisted across scans
        self.notifications: List[Dict] = []
        self.last_scan_at: Optional[str] = None
        self.scan_count: int = 0

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._scan_loop())
            logger.info("🟢 ProactiveMonitorAgent started")

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("🔴 ProactiveMonitorAgent stopped")

    async def _scan_loop(self):
        # First scan after 10s so app has time to fully start
        await asyncio.sleep(10)
        while self._running:
            try:
                await self.run_scan()
            except Exception as e:
                logger.error(f"Monitor scan error: {e}")
            await asyncio.sleep(self.SCAN_INTERVAL_SECONDS)

    # ── SSE reasoning stream ──────────────────────────────────────────────────

    async def reasoning_stream(self) -> AsyncGenerator[str, None]:
        """
        Yields SSE-formatted strings. Drains the reasoning_queue.
        Also triggers a fresh scan so the frontend sees thoughts immediately.
        """
        asyncio.create_task(self.run_scan())

        # Stream for up to 120 seconds
        deadline = asyncio.get_event_loop().time() + 120
        while asyncio.get_event_loop().time() < deadline:
            try:
                event = await asyncio.wait_for(
                    self.reasoning_queue.get(), timeout=1.0
                )
                yield f"event: reasoning\ndata: {json.dumps(event)}\n\n"
                if event.get("type") == "scan_complete":
                    yield f"event: done\ndata: {json.dumps({'notifications': len(self.notifications)})}\n\n"
                    return
            except asyncio.TimeoutError:
                yield "event: ping\ndata: {}\n\n"   # keep connection alive

    # ── Core scan ─────────────────────────────────────────────────────────────

    async def run_scan(self):
        """
        One full proactive scan cycle. Emits reasoning events throughout.
        """
        self.scan_count += 1
        scan_id = f"scan-{self.scan_count}"
        self.last_scan_at = datetime.now().isoformat()
        new_notifications = []

        await self._think("orchestrator",
            f"🔍 Starting proactive scan #{self.scan_count} — "
            f"scanning tasks, calendar, GitHub, Slack, email…")

        # ── 1. Pull real data ─────────────────────────────────────────────────
        tasks, events = await self._load_real_data()
        github   = await _fetch_github_findings()
        slack    = await _fetch_slack_findings()
        email    = await _fetch_email_findings()

        await self._think("orchestrator",
            f"📦 Loaded {len(tasks)} tasks, {len(events)} calendar events, "
            f"{len(github)} GitHub signals, {len(slack)} Slack mentions, "
            f"{len(email)} email flags")

        # ── 2. Deadline proximity scan ────────────────────────────────────────
        await self._think("critic",
            "📅 Scanning calendar for events within 48 hours…")

        now = datetime.utcnow()
        urgent_events = [
            e for e in events
            if e.get("start_time") and
            0 <= (self._parse_dt(e["start_time"]) - now).total_seconds()
               <= self.DEADLINE_WARN_HOURS * 3600
        ]

        if urgent_events:
            await self._think("critic",
                f"⚠️  Found {len(urgent_events)} event(s) within 48h: "
                + ", ".join(f'"{e["title"]}"' for e in urgent_events))
        else:
            await self._think("critic", "✅ No imminent calendar events — clear horizon")

        # ── 3. Cross-reference: events vs tasks ───────────────────────────────
        await self._think("critic",
            "🔗 Cross-referencing calendar events against open task dependencies…")

        for event in urgent_events:
            blocking_tasks = await self._find_blocking_tasks(event, tasks)
            if blocking_tasks:
                insight = await self._generate_insight(event, blocking_tasks,
                                                        github, slack, email)
                notif = {
                    "id":       f"notif-{scan_id}-{len(new_notifications)}",
                    "type":     "bottleneck",
                    "severity": "high",
                    "title":    f"Silent bottleneck: {event['title']}",
                    "message":  insight["summary"],
                    "actions":  insight["actions"],
                    "event":    event["title"],
                    "blocking_tasks": [t["title"] for t in blocking_tasks],
                    "created_at": datetime.now().isoformat(),
                }
                new_notifications.append(notif)
                await self._alert("critic", notif["message"])

                # Let AuditorAgent validate the proposed actions
                await self._think("auditor",
                    f"🛡️ Vibe-checking proposed actions for '{event['title']}'…")
                audit = await self._audit_proposed_actions(insight["actions"], event)
                await self._think("auditor", f"✅ Audit result: {audit}")

        # ── 4. GitHub / Slack / Email bottlenecks ─────────────────────────────
        for signal in github + slack + email:
            if signal["severity"] == "high":
                await self._think("auditor",
                    f"📡 [{signal['source'].upper()}] High-severity signal: "
                    f"{signal['title']} — {signal['detail']}")
                notif = {
                    "id":       f"notif-{scan_id}-ext-{len(new_notifications)}",
                    "type":     "external_signal",
                    "severity": signal["severity"],
                    "title":    f"[{signal['source'].upper()}] {signal['title']}",
                    "message":  signal["detail"],
                    "actions":  [f"Review {signal['source']} item and unblock"],
                    "created_at": datetime.now().isoformat(),
                }
                new_notifications.append(notif)

        # ── 5. Overdue tasks scan ─────────────────────────────────────────────
        await self._think("critic", "🗂️ Scanning for overdue tasks…")
        overdue = [
            t for t in tasks
            if t.get("due_date") and t.get("status") not in ("completed", "cancelled")
            and self._parse_dt(t["due_date"]) < now
        ]
        if overdue:
            await self._think("critic",
                f"🚨 {len(overdue)} overdue task(s): "
                + ", ".join(f'"{t["title"]}"' for t in overdue[:3]))
            
            # Param Mitra Accountability Intervention
            if self.param_mitra:
                worst_task = overdue[0]
                await self._think("orchestrator", f"Calling Param Mitra for accountability on '{worst_task['title']}'...")
                msg = await self.param_mitra.check_accountability(worst_task['title'], 3, {"task_status": worst_task.get("status", "delayed")})
                notif = {
                    "id":       f"notif-{scan_id}-accountability",
                    "type":     "accountability_intervention",
                    "severity": "high",
                    "title":    f"Param Mitra Intervention: {worst_task['title']}",
                    "message":  msg,
                    "actions":  ["Break task into 15m chunks", "Ask Param Mitra for help"],
                    "created_at": datetime.now().isoformat(),
                }
                new_notifications.append(notif)
                await self._alert("guru", msg)

            notif = {
                "id":       f"notif-{scan_id}-overdue",
                "type":     "overdue_tasks",
                "severity": "medium",
                "title":    f"{len(overdue)} overdue task(s) need attention",
                "message":  "Tasks past their due date: " +
                            ", ".join(f'"{t["title"]}"' for t in overdue[:5]),
                "actions":  ["Review overdue tasks", "Update due dates or mark complete"],
                "created_at": datetime.now().isoformat(),
            }
            new_notifications.append(notif)
        else:
            await self._think("critic", "✅ No overdue tasks")

        # ── 6. Persist and broadcast ──────────────────────────────────────────
        self.notifications = new_notifications + [
            n for n in self.notifications if n not in new_notifications
        ]
        self.notifications = self.notifications[:50]   # keep last 50

        summary = (f"Scan complete — {len(new_notifications)} new notification(s). "
                   f"No bottlenecks found." if not new_notifications
                   else f"Scan complete — {len(new_notifications)} bottleneck(s) surfaced.")

        await self._think("orchestrator", f"🏁 {summary}")
        await self.reasoning_queue.put({
            "type": "scan_complete",
            "agent": "orchestrator",
            "message": summary,
            "notification_count": len(new_notifications),
            "ts": datetime.now().strftime("%H:%M:%S"),
        })

        # Broadcast via pubsub so other parts of the system can react
        try:
            await self.pubsub.publish("proactive-monitor-findings", {
                "scan_id":       scan_id,
                "notifications": new_notifications,
                "scanned_at":    self.last_scan_at,
            })
        except Exception:
            pass

        return new_notifications

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _load_real_data(self):
        """Load tasks and events from the real SQLite/PostgreSQL database."""
        try:
            from backend.database import get_all_tasks, get_all_events
            tasks  = [self._task_to_dict(t)  for t in get_all_tasks(limit=200)]
            events = [self._event_to_dict(e) for e in get_all_events(limit=200)]
            return tasks, events
        except Exception as e:
            logger.warning(f"DB load failed: {e}")
            return [], []

    def _task_to_dict(self, t) -> Dict:
        return {
            "task_id":   t.task_id,
            "title":     t.title,
            "status":    t.status,
            "priority":  t.priority,
            "due_date":  t.due_date.isoformat() if t.due_date else None,
            "description": t.description,
        }

    def _event_to_dict(self, e) -> Dict:
        return {
            "event_id":   e.event_id,
            "title":      e.title,
            "start_time": e.start_time.isoformat() if e.start_time else None,
            "end_time":   e.end_time.isoformat() if e.end_time else None,
            "description": e.description,
        }

    def _parse_dt(self, iso_str: str) -> datetime:
        try:
            return datetime.fromisoformat(iso_str.replace("Z", "+00:00").split("+")[0])
        except Exception:
            return datetime.utcnow() + timedelta(days=999)

    async def _find_blocking_tasks(self, event: Dict, tasks: List[Dict]) -> List[Dict]:
        """
        Find open tasks whose title/description semantically relates to this event.
        Uses keyword overlap as a fast heuristic; LLM call for ambiguous cases.
        """
        event_words = set(
            w.lower() for w in (event.get("title", "") + " " +
                                 event.get("description", "")).split()
            if len(w) > 3
        )
        blocking = []
        for t in tasks:
            if t.get("status") in ("completed", "cancelled"):
                continue
            task_words = set(
                w.lower() for w in (t.get("title", "") + " " +
                                     (t.get("description") or "")).split()
                if len(w) > 3
            )
            overlap = event_words & task_words
            if len(overlap) >= 2:
                blocking.append(t)
        return blocking[:5]   # cap at 5 to keep prompt concise

    async def _generate_insight(self, event: Dict, blocking_tasks: List[Dict],
                                 github: List[Dict], slack: List[Dict],
                                 email: List[Dict]) -> Dict:
        """Ask the LLM to synthesise a human-readable bottleneck summary + action list."""
        context = {
            "event":          event,
            "blocking_tasks": blocking_tasks,
            "github_signals": [g for g in github if g["severity"] == "high"],
            "slack_signals":  [s for s in slack  if s["severity"] == "high"],
            "email_signals":  [e for e in email  if e["severity"] == "high"],
        }

        prompt = f"""You are a proactive AI assistant monitoring a user's productivity system.

Context:
{json.dumps(context, indent=2)}

Identify the silent bottleneck and write:
1. A 2-sentence natural language summary (first-person, e.g. "Hey, I noticed...")
2. 2-3 concrete actions the system should take automatically

Respond ONLY with valid JSON (no markdown):
{{
  "summary": "Hey, I noticed...",
  "actions": ["Action 1", "Action 2", "Action 3"]
}}"""

        try:
            raw = await self.llm.call(prompt)
            raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Insight generation failed: {e}")
            task_titles = ", ".join(f'"{t["title"]}"' for t in blocking_tasks)
            return {
                "summary": (f"Hey, I noticed your '{event['title']}' is coming up soon, "
                            f"but {len(blocking_tasks)} related task(s) are still open: "
                            f"{task_titles}."),
                "actions": [
                    f"Review blocking tasks for '{event['title']}'",
                    "Clear calendar slot for a sync if needed",
                ],
            }

    async def _audit_proposed_actions(self, actions: List[str], event: Dict) -> str:
        """Run AuditorAgent's vibe-check on the proposed automatic actions."""
        try:
            report = await self.auditor.audit_action(
                executor_agent="ProactiveMonitorAgent",
                action={"id": f"monitor-{event['event_id']}", "actions": actions},
                reasoning=f"Auto-proposed for bottleneck around '{event['title']}'",
            )
            return f"{report.approval_status} (risk: {report.overall_risk.value})"
        except Exception as e:
            return f"audit skipped ({e})"

    # ── Reasoning helpers ─────────────────────────────────────────────────────

    async def _think(self, agent: str, message: str, thought_type: str = "thought", context_id: Optional[str] = None, risk_level: Optional[str] = None, event_bus=None):
        """Push a 'thinking' event to the reasoning queue AND the global thought bus."""
        event = {
            "type":    thought_type,
            "agent":   agent,
            "message": message,
            "context_id": context_id,
            "ts":      datetime.now().strftime("%H:%M:%S"),
        }
        if risk_level:
            event["risk_level"] = risk_level
        logger.info(f"[{agent}] {message}")
        try:
            self.reasoning_queue.put_nowait(event)
        except asyncio.QueueFull:
            pass

        # Replace global import with Event Bus publication
        if hasattr(self, 'event_bus') and self.event_bus:
            role_map = {"orchestrator": "Orchestrator", "critic": "Critic Agent", "auditor": "Auditor", "knowledge": "Knowledge Agent"}
            await self.event_bus.publish("thought", {
                "agent": agent, 
                "role": role_map.get(agent, agent.title()), 
                "message": message, 
                "type": thought_type, 
                "context_id": context_id, 
                "risk_level": risk_level
            })

    async def _alert(self, agent: str, message: str):
        """Push a high-priority 'alert' event to the reasoning queue."""
        event = {
            "type":    "alert",
            "agent":   agent,
            "message": message,
            "ts":      datetime.now().strftime("%H:%M:%S"),
        }
        try:
            self.reasoning_queue.put_nowait(event)
        except asyncio.QueueFull:
            pass

    async def _finding(self, agent: str, message: str):
        event = {
            "type":    "finding",
            "agent":   agent,
            "message": message,
            "ts":      datetime.now().strftime("%H:%M:%S"),
        }
        try:
            self.reasoning_queue.put_nowait(event)
        except asyncio.QueueFull:
            pass
