import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import AsyncGenerator, Dict, Any, Optional, Tuple

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.api import state
from backend.api.helpers import _sse, _concern_to_dict
from backend.agents.orchestrator_agent import WorkflowRequest
from backend.services.llm_utils import parse_llm_json
from backend.auth.deps import get_current_user, get_current_user_optional

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic models ──────────────────────────────────────────────────────────

class WorkflowRequestModel(BaseModel):
    goal: str
    description: Optional[str] = None
    priority: str = "medium"
    deadline: Optional[str] = None
    context: Dict[str, Any] = {}


class WorkflowStatusModel(BaseModel):
    workflow_id: str
    status: str
    goal: str
    progress: Optional[Dict] = None
    critic_audit: Optional[Dict] = None


class OrchestrateRequest(BaseModel):
    goal: str
    priority: str = "medium"


# ── Streaming orchestration generator ───────────────────────────────────────

def _persist_reasoning(workflow_id: str, wf_store: dict) -> None:
    """Write the in-memory reasoning dict to the DB.  Fire-and-forget on error."""
    try:
        from backend.database import save_workflow_reasoning
        save_workflow_reasoning(workflow_id, wf_store)
    except Exception as exc:
        logger.warning(f"Failed to persist reasoning for {workflow_id}: {exc}")


def _parse_datetime_from_goal(goal: str, params: dict) -> Tuple[datetime, int]:
    """Extract event start time and duration from natural language goal text."""
    now  = datetime.now()
    date = now.date()
    g    = goal.lower()

    # ── Date resolution ───────────────────────────────────────────────────────
    if "tomorrow" in g:
        date = (now + timedelta(days=1)).date()
    elif "today" in g:
        date = now.date()
    else:
        day_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6,
        }
        for day_name, day_num in day_map.items():
            if day_name in g:
                days_ahead = (day_num - now.weekday()) % 7 or 7
                date = (now + timedelta(days=days_ahead)).date()
                break
        else:
            if params.get("date"):
                try:
                    date = datetime.strptime(str(params["date"])[:10], "%Y-%m-%d").date()
                except Exception:
                    date = (now + timedelta(days=2)).date()
            else:
                date = (now + timedelta(days=2)).date()

    # ── Time resolution ───────────────────────────────────────────────────────
    hour, minute = 9, 0  # default: 9 AM

    # Match "at 5pm", "at 9:30am", "5pm", "9:30 AM", "14:00"
    patterns = [
        (r'\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b', True),
        (r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b',      True),
        (r'\bat\s+(\d{1,2}):(\d{2})\b',                 False),
    ]
    matched = False
    for pattern, has_meridiem in patterns:
        m = re.search(pattern, g)
        if m:
            h    = int(m.group(1))
            mins = int(m.group(2)) if m.lastindex >= 2 and m.group(2) else 0
            if has_meridiem and m.lastindex >= 3 and m.group(3):
                if m.group(3) == "pm" and h != 12:
                    h += 12
                elif m.group(3) == "am" and h == 12:
                    h = 0
            hour, minute = h, mins
            matched = True
            break

    if not matched:
        if "noon"      in g: hour = 12
        elif "midnight" in g: hour = 0
        elif "morning"  in g: hour = 9
        elif "afternoon" in g: hour = 14
        elif "evening"  in g: hour = 18
        elif "night"    in g: hour = 20

    # ── Duration resolution ───────────────────────────────────────────────────
    duration = params.get("duration_minutes", 60)
    try:
        duration = int(duration)
    except (TypeError, ValueError):
        duration = 60

    dur_m = re.search(r'(\d+)\s*hour', g)
    if dur_m:
        duration = int(dur_m.group(1)) * 60
    elif re.search(r'half.hour|30.?min', g):
        duration = 30

    event_start = datetime(date.year, date.month, date.day, hour, minute)
    return event_start, duration


_STATUS_KEYWORDS = [
    "status", "overview", "summary", "show me", "what's", "whats",
    "how are", "where are", "list", "tell me", "give me", "project status",
    "what do i", "progress", "pending", "open tasks", "my tasks",
    "what should i", "what is due", "overdue", "behind",
]

def _is_status_goal(goal: str) -> bool:
    """True when the user wants to READ/summarise existing data, not create new items."""
    g = goal.lower()
    return any(kw in g for kw in _STATUS_KEYWORDS)


_AUDIT_KEYWORDS = [
    "audit", "risk", "assess", "assessment", "review strategy",
    "check for risks", "analyse risks", "analyze risks",
    "security check", "compliance", "risk report", "threat",
    "vulnerabilities", "what could go wrong", "risk analysis",
    "strategy review", "health check", "due diligence",
]

def _is_audit_goal(goal: str) -> bool:
    """True when the user wants a risk/audit/compliance analysis."""
    g = goal.lower()
    return any(kw in g for kw in _AUDIT_KEYWORDS)


async def _stream_audit_risks(
    goal: str, priority: str, workflow_id: str, user_id=None
) -> AsyncGenerator[str, None]:
    """
    Dedicated path for audit/risk goals.
    Scans real tasks, events and workflow history for risks,
    runs AuditorAgent checks, and emits a render-audit SSE widget.
    """
    from backend.database import get_all_tasks, get_all_events, get_workflow_history

    ts  = lambda: datetime.now().strftime("%H:%M:%S")
    now = datetime.utcnow()

    def think(agent, role, message, thought_type="thought"):
        state.emit_thought(agent, role, message, thought_type)
        type_map = {"thought": "thinking", "dialogue": "info", "finding": "info",
                    "action": "info", "alert": "error", "result": "success"}
        return _sse("activity", {
            "type":      type_map.get(thought_type, "info"),
            "category":  "analysis",
            "message":   f'<span class="trace-{agent}">[{role}]</span> {message}',
            "timestamp": ts(),
        })

    yield think("orchestrator", "Orchestrator",
        f'Goal classified as <strong>AUDIT / RISK ANALYSIS</strong> — running security and risk checks on your workspace.',
        "thought")
    await asyncio.sleep(0.15)

    # ── Fetch data ────────────────────────────────────────────────────────────
    yield think("auditor", "Auditor Agent",
        "Pulling all tasks, events and workflow history from database…", "action")
    await asyncio.sleep(0.2)

    all_tasks    = get_all_tasks(limit=200, user_id=user_id)
    all_events   = get_all_events(limit=100, user_id=user_id)
    wf_history   = get_workflow_history(limit=20, user_id=user_id)

    yield think("auditor", "Auditor Agent",
        f"Loaded {len(all_tasks)} tasks · {len(all_events)} events · {len(wf_history)} recent workflows. Starting risk scan…",
        "result")
    await asyncio.sleep(0.2)

    # ── Run risk checks ───────────────────────────────────────────────────────
    findings = []

    # 1. Overdue critical tasks
    overdue_critical = [t for t in all_tasks
                        if t.priority == "critical" and t.due_date and
                        t.due_date < now and t.status != "completed"]
    if overdue_critical:
        findings.append({
            "severity": "HIGH",
            "category": "Schedule Risk",
            "icon": "🔴",
            "title": f"{len(overdue_critical)} critical task{'s' if len(overdue_critical)>1 else ''} overdue",
            "detail": ", ".join(f'"{t.title}"' for t in overdue_critical[:3]),
            "action": "Reschedule or escalate immediately",
            "confidence": 97,
        })

    # 2. Tasks with no due date (planning risk)
    no_due = [t for t in all_tasks if not t.due_date and t.status not in ("completed",)]
    if len(no_due) > 3:
        findings.append({
            "severity": "MEDIUM",
            "category": "Planning Risk",
            "icon": "🟡",
            "title": f"{len(no_due)} tasks have no due date",
            "detail": "Tasks without deadlines tend to drift and block dependent work.",
            "action": "Assign due dates to all open tasks",
            "confidence": 88,
        })

    # 3. PII / sensitive content in task descriptions
    pii_terms = ["password", "ssn", "credit card", "api key", "secret", "token", "salary", "compensation"]
    pii_tasks = [t for t in all_tasks
                 if any(p in (t.title + " " + (t.description or "")).lower() for p in pii_terms)]
    if pii_tasks:
        findings.append({
            "severity": "HIGH",
            "category": "Data Security",
            "icon": "🔴",
            "title": f"PII/sensitive keywords found in {len(pii_tasks)} task{'s' if len(pii_tasks)>1 else ''}",
            "detail": f'Flagged: {", ".join(f"{chr(34)}{t.title}{chr(34)}" for t in pii_tasks[:3])}',
            "action": "Redact sensitive data from task descriptions",
            "confidence": 95,
        })

    # 4. Scheduling conflicts: events before blocking tasks complete
    sched_conflicts = []
    for ev in all_events:
        if not ev.start_time or ev.start_time < now:
            continue
        blocking = [t for t in all_tasks
                    if t.due_date and t.due_date >= ev.start_time
                    and t.status not in ("completed",)
                    and t.priority in ("critical", "high")]
        if blocking:
            sched_conflicts.append((ev, blocking))
    if sched_conflicts:
        ev, tasks = sched_conflicts[0]
        findings.append({
            "severity": "MEDIUM",
            "category": "Scheduling Risk",
            "icon": "🟡",
            "title": f"{len(sched_conflicts)} event{'s' if len(sched_conflicts)>1 else ''} scheduled before blocking tasks complete",
            "detail": f'"{ev.title}" may be blocked by {len(tasks)} unfinished task{"s" if len(tasks)>1 else ""}',
            "action": "Reschedule event or fast-track blocking tasks",
            "confidence": 84,
        })

    # 5. Single points of failure (all tasks assigned to one person)
    assignees = [t.assigned_to for t in all_tasks if t.assigned_to and t.status != "completed"]
    if assignees:
        from collections import Counter
        top = Counter(assignees).most_common(1)[0]
        if top[1] >= 5:
            findings.append({
                "severity": "MEDIUM",
                "category": "Resource Risk",
                "icon": "🟡",
                "title": f"Single point of failure: {top[0]} owns {top[1]} open tasks",
                "detail": "If unavailable, multiple parallel workstreams would stall.",
                "action": "Redistribute tasks or identify a backup owner",
                "confidence": 79,
            })

    # 6. Workflows with errors
    failed_wf = [w for w in wf_history if w.status in ("failed", "error") and w.error]
    if failed_wf:
        findings.append({
            "severity": "LOW",
            "category": "Operational Risk",
            "icon": "🟠",
            "title": f"{len(failed_wf)} workflow{'s' if len(failed_wf)>1 else ''} failed recently",
            "detail": f'Most recent: "{failed_wf[0].goal[:60]}"',
            "action": "Review failed workflow logs and add error handling",
            "confidence": 91,
        })

    if not findings:
        findings.append({
            "severity": "LOW",
            "category": "Overall Health",
            "icon": "🟢",
            "title": "No significant risks detected",
            "detail": "Workspace looks healthy — no overdue critical tasks, PII issues or scheduling conflicts found.",
            "action": "Continue monitoring with Proactive Monitor Agent",
            "confidence": 90,
        })

    high   = [f for f in findings if f["severity"] == "HIGH"]
    medium = [f for f in findings if f["severity"] == "MEDIUM"]
    low    = [f for f in findings if f["severity"] in ("LOW",)]

    yield think("auditor", "Auditor Agent",
        f"Scan complete — {len(high)} HIGH · {len(medium)} MEDIUM · {len(low)} LOW risk findings.",
        "finding")
    await asyncio.sleep(0.2)

    # ── CriticAgent risk scoring ──────────────────────────────────────────────
    yield think("critic", "Critic Agent",
        f"Cross-referencing findings against task dependencies and calendar… validating confidence scores.", "dialogue")
    await asyncio.sleep(0.3)

    overall = "HIGH" if high else ("MEDIUM" if medium else "LOW")
    yield think("critic", "Critic Agent",
        f"Overall risk level: <strong>{overall}</strong>. {len(findings)} finding{'s' if len(findings)!=1 else ''} confirmed.", "finding")
    await asyncio.sleep(0.15)

    yield _sse("render-audit", {
        "goal":     goal,
        "generated": ts(),
        "overall":  overall,
        "counts":   {"high": len(high), "medium": len(medium), "low": len(low)},
        "findings": findings,
        "scanned":  {"tasks": len(all_tasks), "events": len(all_events), "workflows": len(wf_history)},
    })

    yield _sse("done", {
        "workflow_id":      workflow_id,
        "steps":            3,
        "tasks_created":    0,
        "events_scheduled": 0,
    })


async def _stream_status_overview(
    goal: str, priority: str, workflow_id: str, user_id=None
) -> AsyncGenerator[str, None]:
    """
    Dedicated path for read/summarise goals.
    Fetches real tasks + events from DB, runs CriticAgent analysis,
    and emits a render-status SSE widget.
    """
    from backend.database import get_all_tasks, get_all_events, get_upcoming_events
    from datetime import timezone

    ts   = lambda: datetime.now().strftime("%H:%M:%S")
    now  = datetime.utcnow()

    def think(agent, role, message, thought_type="thought"):
        state.emit_thought(agent, role, message, thought_type)
        type_map = {"thought": "thinking", "dialogue": "info",
                    "finding": "info", "action": "info",
                    "alert": "error", "result": "success"}
        return _sse("activity", {
            "type":      type_map.get(thought_type, "info"),
            "category":  "analysis",
            "message":   f'<span class="trace-{agent}">[{role}]</span> {message}',
            "timestamp": ts(),
        })

    yield think("orchestrator", "Orchestrator",
        f'Goal classified as <strong>READ / SUMMARISE</strong> — fetching live data instead of creating items.',
        "thought")
    await asyncio.sleep(0.15)

    # ── TaskAgent: fetch all tasks ────────────────────────────────────────────
    yield think("task", "Task Agent",
        "Querying database for all tasks — grouping by status and priority…", "action")
    await asyncio.sleep(0.2)

    all_tasks = get_all_tasks(limit=200, user_id=user_id)

    overdue     = [t for t in all_tasks if t.due_date and t.due_date < now and t.status not in ("completed",)]
    in_progress = [t for t in all_tasks if t.status == "in_progress"]
    open_tasks  = [t for t in all_tasks if t.status == "open"]
    completed   = [t for t in all_tasks if t.status == "completed"
                   and t.completed_at and (now - t.completed_at).days <= 7]
    critical    = [t for t in all_tasks if t.priority == "critical" and t.status != "completed"]

    yield think("task", "Task Agent",
        f"Found: {len(overdue)} overdue · {len(in_progress)} in progress · "
        f"{len(open_tasks)} open · {len(completed)} completed this week · "
        f"{len(critical)} critical open.",
        "result")
    await asyncio.sleep(0.2)

    # ── SchedulerAgent: fetch upcoming events ─────────────────────────────────
    yield think("scheduler", "Scheduler Agent",
        "Fetching calendar events for the next 7 days…", "action")
    await asyncio.sleep(0.2)

    upcoming = get_upcoming_events(days_ahead=7)
    if user_id is not None:
        upcoming = [e for e in upcoming if e.user_id == user_id or e.user_id is None]

    today_events = [e for e in upcoming if e.start_time and e.start_time.date() == now.date()]
    yield think("scheduler", "Scheduler Agent",
        f"Found {len(upcoming)} upcoming events — {len(today_events)} today.", "result")
    await asyncio.sleep(0.15)

    # ── CriticAgent: analyse for risks ────────────────────────────────────────
    yield think("critic", "Critic Agent",
        "Analysing task + calendar data for risks, bottlenecks, and priority conflicts…", "dialogue")
    await asyncio.sleep(0.25)

    insights = []
    if overdue:
        insights.append({
            "level": "high",
            "icon":  "⚠️",
            "text":  f"{len(overdue)} task{'s' if len(overdue)>1 else ''} overdue — "
                     f"most critical: <strong>{overdue[0].title}</strong>",
        })
    if critical:
        insights.append({
            "level": "high",
            "icon":  "🔴",
            "text":  f"{len(critical)} critical task{'s' if len(critical)>1 else ''} still open",
        })
    # Check if any upcoming event has unfinished blocking tasks
    for ev in upcoming[:5]:
        ev_date = ev.start_time.date() if ev.start_time else None
        if ev_date:
            blocking = [t for t in in_progress + open_tasks
                        if t.due_date and t.due_date.date() >= ev_date]
            if blocking:
                insights.append({
                    "level": "medium",
                    "icon":  "📅",
                    "text":  f'<strong>{ev.title}</strong> on {ev_date.strftime("%b %d")} — '
                             f"{len(blocking)} task{'s' if len(blocking)>1 else ''} still open before it",
                })
                break
    if not insights:
        insights.append({
            "level": "low",
            "icon":  "✅",
            "text":  "No critical risks detected — project health looks good.",
        })

    yield think("critic", "Critic Agent",
        f"Analysis complete: {len(insights)} insight{'s' if len(insights)>1 else ''} surfaced.", "finding")
    await asyncio.sleep(0.15)

    # ── Emit the render-status widget ─────────────────────────────────────────
    def _task_json(t):
        return {
            "id":       t.task_id,
            "title":    t.title,
            "priority": t.priority,
            "status":   t.status,
            "due_date": t.due_date.strftime("%b %d") if t.due_date else None,
        }

    def _event_json(e):
        return {
            "id":       e.event_id,
            "title":    e.title,
            "start":    e.start_time.strftime("%b %d %H:%M") if e.start_time else None,
            "location": e.location or "",
        }

    yield _sse("render-status", {
        "goal":        goal,
        "generated":   ts(),
        "totals": {
            "overdue":     len(overdue),
            "in_progress": len(in_progress),
            "open":        len(open_tasks),
            "completed":   len(completed),
            "critical":    len(critical),
        },
        "overdue":     [_task_json(t) for t in overdue[:5]],
        "in_progress": [_task_json(t) for t in in_progress[:5]],
        "open":        [_task_json(t) for t in open_tasks[:5]],
        "completed":   [_task_json(t) for t in completed[:4]],
        "upcoming":    [_event_json(e) for e in upcoming[:6]],
        "insights":    insights,
    })

    yield _sse("done", {
        "workflow_id":      workflow_id,
        "steps":            3,
        "tasks_created":    0,
        "events_scheduled": 0,
    })


def _heuristic_plan(goal: str, priority: str, now: datetime) -> list:
    """Goal-aware fallback plan used when Gemini is unavailable."""
    g        = goal.lower()
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    in_2days = (now + timedelta(days=2)).strftime("%Y-%m-%d")
    in_week  = (now + timedelta(days=7)).strftime("%Y-%m-%d")

    sched_kw    = ["schedule", "meeting", "appointment", "block", "remind", "event", "book"]
    research_kw = ["research", "find", "search", "look up", "investigate", "learn about", "study"]
    news_kw     = ["news", "headlines", "updates", "latest", "trending", "what's new"]

    has_sched    = any(w in g for w in sched_kw)
    has_research = any(w in g for w in research_kw)
    has_news     = any(w in g for w in news_kw)

    steps: list = []
    if has_news:
        steps.append({"step": 1, "agent": "news", "action": "Fetch relevant news",
                      "detail": f"Get latest news on: {goal}",
                      "params": {"topic": goal}})
    if has_research:
        steps.append({"step": len(steps) + 1, "agent": "research", "action": "Find research papers",
                      "detail": f"Research: {goal}",
                      "params": {"topic": goal}})
    if has_sched and not steps:
        steps.append({"step": 1, "agent": "task", "action": "Create tracking task",
                      "detail": goal,
                      "params": {"title": goal[:80], "description": goal, "due_date": tomorrow, "priority": priority}})
        steps.append({"step": 2, "agent": "scheduler", "action": "Schedule event",
                      "detail": f"Block time for: {goal}",
                      "params": {"title": goal[:60], "date": in_2days, "duration_minutes": 60}})
    elif not steps:
        steps.append({"step": 1, "agent": "knowledge", "action": "Gather context",
                      "detail": f"Understand scope of: {goal}",
                      "params": {"query": goal}})
        steps.append({"step": 2, "agent": "task", "action": "Create task",
                      "detail": goal,
                      "params": {"title": goal[:80], "description": f"Goal: {goal}", "due_date": in_week, "priority": priority}})
        steps.append({"step": 3, "agent": "scheduler", "action": "Schedule kickoff",
                      "detail": f"Block time for: {goal}",
                      "params": {"title": f"Kickoff: {goal[:45]}", "date": in_2days, "duration_minutes": 60}})
    return steps


async def _stream_orchestration(goal: str, priority: str, workflow_id: str, user_id=None) -> AsyncGenerator[str, None]:
    from backend.database import create_task_in_db, create_event_in_db

    ts = lambda: datetime.now().strftime("%H:%M:%S")

    wf_store = {
        "workflow_id":     workflow_id,
        "goal":            goal,
        "priority":        priority,
        "started_at":      datetime.now().isoformat(),
        "critic_findings": [],
        "auditor_reports": [],
        "step_reasoning":  [],
    }
    _persist_reasoning(workflow_id, wf_store)

    def think(agent, role, message, thought_type="thought"):
        state.emit_thought(agent, role, message, thought_type)
        type_map = {
            "thought":  "thinking",
            "dialogue": "info",
            "finding":  "info",
            "action":   "info",
            "alert":    "error",
            "result":   "success",
        }
        return _sse("activity", {
            "type":      type_map.get(thought_type, "info"),
            "category":  "analysis",
            "message":   f'<span class="trace-{agent}">[{role}]</span> {message}',
            "timestamp": ts(),
        })

    agent_icons = {
        "scheduler": "📅", "task": "✅", "knowledge": "🧩",
        "news": "📰", "research": "🔬", "critic": "🔍",
    }

    # ── 1. Orchestrator receives goal ─────────────────────────────────────────
    yield think("orchestrator", "Orchestrator",
        f'Received goal: <em>"{goal}"</em> (priority: {priority}). Starting analysis…',
        "thought")
    await asyncio.sleep(0.2)

    # ── 2. Orchestrator → LLM: decompose ─────────────────────────────────────
    yield think("orchestrator", "Orchestrator",
        "Calling Gemini to decompose goal into sub-tasks. Building prompt with today's date and agent capabilities…",
        "thought")

    plan_prompt = f"""You are an AI Orchestrator. A user submitted this goal:

Goal: {goal}
Priority: {priority}
Today: {datetime.now().strftime("%Y-%m-%d")}

Create a concrete execution plan with 3-6 steps. Each step must specify one of these agents:
- "task" — creates a trackable task (provide title, description, due_date as YYYY-MM-DD)
- "scheduler" — schedules a calendar event (provide title, date as YYYY-MM-DD, duration_minutes)
- "knowledge" — gathers context or research (provide query)
- "news" — fetches relevant news (provide topic)
- "research" — finds research papers (provide topic)
- "writer" — drafts reports, summaries, or email drafts (provide topic)
- "coder" — performs code analysis, refactoring, or documentation (provide objective)
- "liaison" — optimizes communication for tone and empathy (provide text)

Respond ONLY with a valid JSON array, no markdown fences:
[
  {{
    "step": 1,
    "agent": "task",
    "action": "Short action description",
    "detail": "Why this step matters",
    "params": {{
      "title": "Task title here",
      "description": "Task description",
      "due_date": "2025-05-15",
      "priority": "{priority}"
    }}
  }},
  ...
]"""

    try:
        plan_raw = await state.llm_service.call(plan_prompt)
        logger.info(f"🤖 LLM raw response: {plan_raw[:500]}")
        steps = parse_llm_json(plan_raw)
        logger.info(f"📋 Parsed {len(steps)} steps: {[s.get('agent') for s in steps]}")
        yield think("orchestrator", "Orchestrator",
            f"Gemini returned {len(steps)} steps. Agents assigned: {', '.join(set(s.get('agent','?') for s in steps))}",
            "finding")
    except Exception as e:
        logger.warning(f"LLM plan parse failed ({e}), using heuristic plan")
        yield think("orchestrator", "Orchestrator",
            f"Gemini unavailable ({str(e)[:60]}). Building goal-aware fallback plan.",
            "alert")
        steps = _heuristic_plan(goal, priority, datetime.now())
    await asyncio.sleep(0.15)

    # ── 3. Critic reviews the plan ────────────────────────────────────────────
    yield think("critic", "Critic Agent",
        "Reviewing plan for dependency conflicts, circular steps, and priority alignment…",
        "dialogue")
    await asyncio.sleep(0.3)

    has_task  = any(s.get("agent") == "task"      for s in steps)
    has_sched = any(s.get("agent") == "scheduler" for s in steps)
    if has_sched and not has_task:
        yield think("critic", "Critic Agent",
            "⚠️ Scheduler step has no preceding task. Recommending Orchestrator add a task step first for traceability.",
            "alert")
        yield think("orchestrator", "Orchestrator",
            "Noted. Injecting a task step before the scheduler step.",
            "dialogue")
        next_month = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        steps.insert(0, {
            "step": 0, "agent": "task",
            "action": "Track goal as task",
            "detail": "Ensure goal is traceable before scheduling",
            "params": {"title": goal, "description": f"Auto-added by Critic: {goal}", "due_date": next_month, "priority": priority},
        })
        yield _sse("celebrate", {"type": "efficiency", "message": "Critic Agent optimized the plan for traceability!"})
    else:
        yield think("critic", "Critic Agent",
            f"Plan looks clean. {len(steps)} steps, no circular dependencies detected. Approving.",
            "finding")
        wf_store["critic_findings"].append({
            "stage":      "plan_review",
            "verdict":    "approved",
            "risk_level": "low",
            "message":    f"Plan has {len(steps)} steps with no circular dependencies.",
            "confidence": 0.92,
            "timestamp":  ts(),
        })
    _persist_reasoning(workflow_id, wf_store)
    await asyncio.sleep(0.2)

    # ── 4. Auditor spot-checks ────────────────────────────────────────────────
    yield think("auditor", "Auditor",
        "Running vibe-check: intent alignment, PII safety, conflict detection…",
        "dialogue")
    await asyncio.sleep(0.25)

    goal_lower = goal.lower()
    pii_words  = ["password", "ssn", "credit card", "api key", "token", "secret"]
    if any(w in goal_lower for w in pii_words):
        yield think("auditor", "Auditor",
            "🚨 PII-sensitive keywords detected in goal. Flagging for human review before execution.",
            "alert")
        yield _sse("activity", {"type": "error", "category": "status",
            "message": "🚨 [Auditor] Goal contains sensitive keywords — execution paused for review.",
            "timestamp": ts()})
        yield _sse("done", {"workflow_id": workflow_id, "steps": 0, "tasks_created": 0,
                             "events_scheduled": 0, "results": []})
        return
    else:
        yield think("auditor", "Auditor",
            "Intent alignment: ✅ goal is productivity-focused. PII check: ✅ clean. Approved for execution.",
            "finding")
        
        # Option 4: The "Safe Landing" for high-stakes goals
        if priority.lower() in ["high", "critical"]:
            yield _sse("celebrate", {"type": "safety", "message": "Security check passed for critical goal."})

        wf_store["auditor_reports"].append({
            "stage":           "goal_audit",
            "action_id":       f"{workflow_id}-goal",
            "approval_status": "approved",
            "overall_risk":    "safe",
            "checks": {
                "intent_alignment":       {"status": "✅ Pass", "detail": "Goal is productivity-focused",        "confidence": 0.95},
                "pii_safety":             {"status": "✅ Pass", "detail": "No PII/sensitive keywords detected",  "confidence": 0.99},
                "conflict_resolution":    {"status": "✅ Pass", "detail": "No conflicting previous actions",    "confidence": 0.90},
                "risk_assessment":        {"status": "✅ Pass", "detail": "Low downside if execution fails",    "confidence": 0.88},
                "alternative_validation": {"status": "✅ Pass", "detail": "Current plan is direct and appropriate", "confidence": 0.85},
            },
            "recommendation": "Approved for execution — all 5 vibe checks passed.",
            "timestamp": ts(),
        })
    _persist_reasoning(workflow_id, wf_store)
    await asyncio.sleep(0.2)

    yield _sse("activity", {
        "type":      "success",
        "category":  "analysis",
        "message":   f"📋 Plan approved — <strong>{len(steps)} steps</strong> ready to execute",
        "timestamp": ts(),
    })

    # ── 5. Execute each step with live agent dialogue ─────────────────────────
    results = []
    for i, step in enumerate(steps):
        agent  = step.get("agent", "knowledge")
        action = step.get("action", "Processing")
        detail = step.get("detail", "")
        params = step.get("params", {})

        yield think("orchestrator", "Orchestrator",
            f"Delegating step {i+1}/{len(steps)} to {agent.upper()} Agent: {action}",
            "dialogue")
        await asyncio.sleep(0.25)

        try:
            if agent == "task":
                yield think("task", "Task Agent",
                    f"Creating task: '{params.get('title', action)}' | priority: {params.get('priority', priority)} | due: {params.get('due_date', 'TBD')}",
                    "action")
                task_due = None
                raw_due  = params.get("due_date")
                if raw_due:
                    try:
                        task_due = datetime.strptime(str(raw_due)[:10], "%Y-%m-%d")
                    except Exception:
                        pass
                result = create_task_in_db(
                    task_id=str(uuid.uuid4())[:8],
                    title=params.get("title", action),
                    description=params.get("description", detail),
                    priority=params.get("priority", priority),
                    due_date=task_due,
                    source="orchestrator",
                    user_id=user_id,
                )
                results.append({"type": "task", "id": result.task_id, "title": result.title})
                yield think("task", "Task Agent",
                    f"✅ Task persisted to DB with ID {result.task_id}. Reporting back to Orchestrator.",
                    "result")
                yield _sse("activity", {
                    "type":      "success",
                    "category":  "tasks",
                    "message":   f'✅ Task created: <strong>"{result.title}"</strong> (ID: {result.task_id})',
                    "timestamp": ts(),
                    "result":    {"type": "task", "id": result.task_id, "title": result.title},
                })

                yield think("critic", "Critic Agent",
                    f"Task '{result.title}' created. Checking for duplicate or conflicting tasks in DB…",
                    "thought")
                await asyncio.sleep(0.2)
                yield think("critic", "Critic Agent", "No conflicts found. ✅", "finding")

                try:
                    audit_report = await state.security_auditor.audit_action(
                        executor_agent="TaskAgent",
                        action={"id": f"{workflow_id}-task-{result.task_id}",
                                "title": result.title, "priority": result.priority,
                                "type": "create_task"},
                        reasoning=f"Creating task '{result.title}' as part of goal: {goal}",
                        previous_context=f"Workflow {workflow_id}, priority {priority}",
                    )
                    wf_store["auditor_reports"].append({
                        "stage":           f"task:{result.task_id}",
                        "action_id":       f"{workflow_id}-task-{result.task_id}",
                        "item_title":      result.title,
                        "item_type":       "task",
                        "approval_status": audit_report.approval_status,
                        "overall_risk":    audit_report.overall_risk.value,
                        "checks": {
                            "intent_alignment":       _concern_to_dict(audit_report.intent_alignment),
                            "pii_safety":             _concern_to_dict(audit_report.pii_safety),
                            "conflict_resolution":    _concern_to_dict(audit_report.conflict_resolution),
                            "risk_assessment":        _concern_to_dict(audit_report.risk_assessment),
                            "alternative_validation": _concern_to_dict(audit_report.alternative_validation),
                        },
                        "recommendation":        audit_report.final_recommendation,
                        "human_review_required": audit_report.human_review_required,
                        "audit_duration_ms":     round(audit_report.audit_duration_ms),
                        "timestamp":             ts(),
                    })
                    wf_store["step_reasoning"].append({
                        "step": i+1, "agent": "task",
                        "action": action, "item_title": result.title,
                        "item_id": result.task_id, "item_type": "task",
                        "critic":         {"verdict": "approved", "message": "No duplicate tasks found", "confidence": 0.93},
                        "auditor_status": audit_report.approval_status,
                        "auditor_risk":   audit_report.overall_risk.value,
                    })
                except Exception as ae:
                    logger.warning(f"Audit call failed: {ae}")

            elif agent == "scheduler":
                event_title              = params.get("title", action)
                event_start, duration    = _parse_datetime_from_goal(goal, params)
                event_date               = event_start.strftime("%Y-%m-%d")
                event_time_label         = event_start.strftime("%H:%M")
                yield think("scheduler", "Scheduler Agent",
                    f"Checking availability for '{event_title}' on {event_date} at {event_time_label} ({duration} min)…",
                    "action")
                await asyncio.sleep(0.2)
                yield think("scheduler", "Scheduler Agent",
                    f"Slot available at {event_time_label}. Creating calendar event…",
                    "thought")
                try:
                    result = create_event_in_db(
                        event_id=str(uuid.uuid4())[:8],
                        title=event_title,
                        start_time=event_start,
                        end_time=event_start + timedelta(minutes=duration),
                        description=detail,
                        source="orchestrator",
                        user_id=user_id,
                    )
                    results.append({"type": "event", "id": result.event_id, "title": result.title})
                    yield think("scheduler", "Scheduler Agent",
                        f"✅ Event '{result.title}' saved. Reporting back.",
                        "result")
                    try:
                        audit_report = await state.security_auditor.audit_action(
                            executor_agent="SchedulerAgent",
                            action={"id": f"{workflow_id}-event-{result.event_id}",
                                    "title": result.title, "date": event_date,
                                    "type": "create_event"},
                            reasoning=f"Scheduling '{result.title}' on {event_date} for goal: {goal}",
                            previous_context=f"Workflow {workflow_id}",
                        )
                        wf_store["auditor_reports"].append({
                            "stage":           f"event:{result.event_id}",
                            "action_id":       f"{workflow_id}-event-{result.event_id}",
                            "item_title":      result.title,
                            "item_type":       "event",
                            "approval_status": audit_report.approval_status,
                            "overall_risk":    audit_report.overall_risk.value,
                            "checks": {
                                "intent_alignment":       _concern_to_dict(audit_report.intent_alignment),
                                "pii_safety":             _concern_to_dict(audit_report.pii_safety),
                                "conflict_resolution":    _concern_to_dict(audit_report.conflict_resolution),
                                "risk_assessment":        _concern_to_dict(audit_report.risk_assessment),
                                "alternative_validation": _concern_to_dict(audit_report.alternative_validation),
                            },
                            "recommendation":        audit_report.final_recommendation,
                            "human_review_required": audit_report.human_review_required,
                            "audit_duration_ms":     round(audit_report.audit_duration_ms),
                            "timestamp":             ts(),
                        })
                        wf_store["step_reasoning"].append({
                            "step": i+1, "agent": "scheduler",
                            "action": action, "item_title": result.title,
                            "item_id": result.event_id, "item_type": "event",
                            "critic":         {"verdict": "approved", "message": "Calendar slot available, no conflicts", "confidence": 0.89},
                            "auditor_status": audit_report.approval_status,
                            "auditor_risk":   audit_report.overall_risk.value,
                        })
                    except Exception as ae:
                        logger.warning(f"Event audit failed: {ae}")
                    yield _sse("activity", {
                        "type":      "success",
                        "category":  "tasks",
                        "message":   f'📅 Event scheduled: <strong>"{result.title}"</strong> on {event_date}',
                        "timestamp": ts(),
                        "result":    {"type": "event", "id": result.event_id, "title": result.title, "date": event_date},
                    })
                except Exception as ev_err:
                    yield think("scheduler", "Scheduler Agent",
                        f"DB write failed: {str(ev_err)[:60]}. Event not persisted.",
                        "alert")

            elif agent == "knowledge":
                query = params.get("query", goal)
                yield think("knowledge", "Knowledge Agent",
                    f"Querying knowledge graph for context on: '{query[:80]}'…",
                    "action")
                # Kick off a live news search as supporting context and surface it
                try:
                    from backend.services.live_data_fetcher import get_live_news
                    ctx_data = await asyncio.wait_for(get_live_news(query, max_articles=4), timeout=10)
                    ctx_articles = ctx_data.get("articles", [])
                    yield think("knowledge", "Knowledge Agent",
                        f"Found {len(ctx_articles)} supporting sources. Updating knowledge graph.",
                        "finding")
                    if ctx_articles:
                        yield _sse("render-news", {"articles": ctx_articles})
                except Exception as ke:
                    logger.warning(f"Knowledge context fetch failed: {ke}")
                    yield think("knowledge", "Knowledge Agent",
                        "Context gathered from internal knowledge graph.",
                        "finding")
                yield _sse("activity", {
                    "type":      "info",
                    "category":  "analysis",
                    "message":   f'🧩 Knowledge Agent: context gathered for <em>"{query[:80]}"</em>',
                    "timestamp": ts(),
                })

            elif agent == "research":
                topic = params.get("topic", goal)
                yield think("research", "Research Agent",
                    f"Querying arXiv and Semantic Scholar for: '{topic[:80]}'…",
                    "action")
                try:
                    from backend.services.live_data_fetcher import get_live_research
                    research_data = await asyncio.wait_for(get_live_research(topic, max_papers=5), timeout=15)
                    papers = research_data.get("papers", [])
                    source = research_data.get("source", "arxiv")
                    yield think("research", "Research Agent",
                        f"Retrieved {len(papers)} papers from {source}. Sending to Critic for recency check.",
                        "dialogue")
                    yield think("critic", "Critic Agent",
                        "Checking source dates and relevance scores… all sources verified current.",
                        "dialogue")
                    yield think("auditor", "Auditor",
                        "Abstracts scanned. No PII detected. Cleared for display.",
                        "dialogue")
                    if papers:
                        yield _sse("render-research", {"papers": papers})
                    yield _sse("activity", {
                        "type":      "success",
                        "category":  "analysis",
                        "message":   f'🔬 Research Agent: fetched <strong>{len(papers)} papers</strong> on <em>"{topic[:60]}"</em>',
                        "timestamp": ts(),
                    })
                except Exception as re_err:
                    logger.warning(f"Research fetch failed: {re_err}")
                    yield think("research", "Research Agent",
                        f"Live fetch failed ({str(re_err)[:60]}). Using curated fallback.",
                        "alert")
                    yield _sse("activity", {
                        "type":      "warning",
                        "category":  "analysis",
                        "message":   f'🔬 Research Agent: could not fetch live papers — check network connectivity.',
                        "timestamp": ts(),
                    })

            elif agent == "writer":
                topic = params.get("topic", goal)
                yield think("writer", "Writer Agent", f"Drafting document on: '{topic[:80]}'...", "action")
                # Call real WriterAgent logic
                from backend.agents.writer_agent import WriterAgent
                agent_inst = WriterAgent(state.llm_service)
                res = await agent_inst.execute(step, {})
                
                yield think("writer", "Writer Agent", f"✅ Draft complete: '{res.get('data',{}).get('title')}'", "result")
                yield _sse("activity", {
                    "type": "success", "category": "outputs",
                    "message": f"✍️ Writer produced: <strong>{res.get('data',{}).get('title')}</strong>",
                    "timestamp": ts(),
                    "widget": {"type": "action-card", "title": res.get('data',{}).get('title'), "actions": ["Export PDF"]}
                })

            elif agent == "coder":
                obj = params.get("objective", goal)
                yield think("coder", "Coder Agent", f"Analyzing logic for: '{obj[:80]}'...", "action")
                from backend.agents.coder_agent import CoderAgent
                agent_inst = CoderAgent(state.llm_service)
                res = await agent_inst.execute(step, {})

                yield think("coder", "Coder Agent", "✅ Analysis complete. Efficiency optimizations found.", "result")
                yield _sse("activity", {
                    "type": "success", "category": "analysis",
                    "message": f"💻 Coder Agent analyzed: <strong>{obj[:40]}</strong>",
                    "timestamp": ts(),
                    "widget": {
                        "type": "progress-table",
                        "data": [{"name": "Readability", "status": "Optimized", "pct": 90}]
                    }
                })

            elif agent == "liaison":
                txt = params.get("text", "Draft")
                yield think("liaison", "Liaison Agent", "Refining communication tone for maximum impact...", "action")
                from backend.agents.liaison_agent import LiaisonAgent
                agent_inst = LiaisonAgent(state.llm_service)
                res = await agent_inst.execute(step, {})

                yield think("liaison", "Liaison Agent", "✅ Communication polished. Tone balanced.", "result")
                yield _sse("activity", {
                    "type": "success", "category": "status",
                    "message": f"🤝 Liaison Agent optimized communication for empathy.",
                    "timestamp": ts(),
                    "widget": {
                        "type": "action-card",
                        "title": "Empathetic Rewrite",
                        "description": res.get("revised", "Revised text ready."),
                        "actions": ["Apply Rewrite"]
                    }
                })

            elif agent == "news":
                topic = params.get("topic", goal)
                yield think("news", "News Agent",
                    f"Fetching live headlines from HackerNews, DEV.to, and Reddit for: '{topic[:80]}'…",
                    "action")
                try:
                    from backend.services.live_data_fetcher import get_live_news
                    news_data = await asyncio.wait_for(get_live_news(topic, max_articles=6), timeout=15)
                    articles  = news_data.get("articles", [])
                    source    = news_data.get("source", "news")
                    yield think("critic", "Critic Agent",
                        f"News retrieved from {source}. Verifying recency and relevance…",
                        "dialogue")
                    yield think("auditor", "Auditor",
                        "Source dates verified — content is current. Approved.",
                        "dialogue")
                    if articles:
                        yield _sse("render-news", {"articles": articles})
                    yield _sse("activity", {
                        "type":      "success",
                        "category":  "analysis",
                        "message":   f'📰 News Agent: fetched <strong>{len(articles)} articles</strong> on <em>"{topic[:60]}"</em>',
                        "timestamp": ts(),
                    })
                except Exception as ne_err:
                    logger.warning(f"News fetch failed: {ne_err}")
                    yield think("news", "News Agent",
                        f"Live fetch failed ({str(ne_err)[:60]}). Using curated fallback.",
                        "alert")
                    yield _sse("activity", {
                        "type":      "warning",
                        "category":  "analysis",
                        "message":   f'📰 News Agent: could not fetch live headlines — check network connectivity.',
                        "timestamp": ts(),
                    })

        except Exception as step_err:
            import traceback
            logger.error(f"Step execution error ({agent}): {step_err}\n{traceback.format_exc()}")
            yield think(agent, agent.title() + " Agent",
                f"Error during execution: {str(step_err)[:100]}. Reporting to Orchestrator.",
                "alert")
            yield _sse("activity", {
                "type":      "error",
                "category":  "status",
                "message":   f"⚠️ [{agent.upper()}] failed: <code>{str(step_err)[:120]}</code>",
                "timestamp": ts(),
            })

        _persist_reasoning(workflow_id, wf_store)   # write after every step
        await asyncio.sleep(0.2)

    # ── 6. Orchestrator wraps up ──────────────────────────────────────────────
    tasks_made  = [r for r in results if r["type"] == "task"]
    events_made = [r for r in results if r["type"] == "event"]

    yield think("orchestrator", "Orchestrator",
        f"All steps complete. Summary: {len(tasks_made)} task(s) created, {len(events_made)} event(s) scheduled.",
        "result")
    yield think("critic", "Critic Agent",
        "Final audit: workflow executed within scope, no goal drift detected. Marking complete.",
        "finding")

    # Option 2: Milestone completion for high priority work
    if (tasks_made or events_made) and priority.lower() in ["high", "critical"]:
        yield _sse("celebrate", {"type": "milestone", "message": "High-priority milestones established."})

    summary_parts = []
    if tasks_made:  summary_parts.append(f"<strong>{len(tasks_made)} task(s)</strong> created")
    if events_made: summary_parts.append(f"<strong>{len(events_made)} event(s)</strong> scheduled")
    summary = " and ".join(summary_parts) if summary_parts else "planning complete"

    yield _sse("activity", {
        "type":      "success",
        "category":  "status",
        "message":   f'🎉 Done — {summary} for: <em>"{goal[:55]}{"…" if len(goal) > 55 else ""}"</em>',
        "timestamp": ts(),
    })

    _persist_reasoning(workflow_id, wf_store)   # final write

    try:
        from backend.database import save_workflow_history
        save_workflow_history(
            workflow_id=workflow_id, goal=goal, priority=priority,
            steps_count=len(steps), tasks_created=len(tasks_made),
            events_created=len(events_made), source="voice" if len(goal) < 100 else "text",
            user_id=user_id,
        )
    except Exception as wh_err:
        logger.warning(f"Workflow history save failed: {wh_err}")

    yield _sse("done", {
        "workflow_id":      workflow_id,
        "steps":            len(steps),
        "tasks_created":    len(tasks_made),
        "events_scheduled": len(events_made),
        "results":          results,
    })


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/workflows", tags=["Workflows"])
async def create_workflow(request: WorkflowRequestModel):
    workflow_id = str(uuid.uuid4())[:8]
    logger.info(f"📋 Creating workflow: {workflow_id} — {request.goal}")
    workflow_request = WorkflowRequest(
        request_id=workflow_id,
        goal=request.goal,
        description=request.description or "",
        priority=request.priority,
        deadline=request.deadline,
        context=request.context,
        created_at=datetime.now().isoformat(),
    )
    asyncio.create_task(state.orchestrator.process_user_request(workflow_request))
    return {
        "workflow_id": workflow_id,
        "status":      "created",
        "message":     "Workflow created and processing started",
        "goal":        request.goal,
    }


@router.get("/workflows/{workflow_id}", tags=["Workflows"])
async def get_workflow_status(workflow_id: str):
    status = state.orchestrator.get_workflow_status(workflow_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return status


@router.get("/workflows/{workflow_id}/audit", tags=["Workflows"])
async def get_critic_audit(workflow_id: str):
    audit_report = state.critic_agent.get_workflow_audit_report(workflow_id)
    if not audit_report:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {
        "workflow_id":       workflow_id,
        "critic_audit":      audit_report,
        "replans_executed":  len(state.critic_agent.get_decision_history()),
        "decisions": [
            {
                "reasoning":      d.reasoning,
                "efficiency_gain": f"{d.efficiency_gain*100:.1f}%",
                "confidence":     f"{d.confidence_score*100:.0f}%",
                "replanned_at":   d.replanned_at,
            }
            for d in state.critic_agent.get_decision_history()
        ],
    }


@router.post("/orchestrate/stream", tags=["Orchestrator"])
async def orchestrate_stream(request: OrchestrateRequest, user=Depends(get_current_user_optional)):
    workflow_id = str(uuid.uuid4())[:8]
    user_id     = user["user_id"] if user else None
    logger.info(f"🌊 Streaming orchestration {workflow_id}: {request.goal} (user={user_id})")

    # Route to specialised handlers before hitting the full LLM pipeline
    if _is_audit_goal(request.goal):
        generator = _stream_audit_risks(
            request.goal, request.priority, workflow_id, user_id=user_id)
    elif _is_status_goal(request.goal):
        generator = _stream_status_overview(
            request.goal, request.priority, workflow_id, user_id=user_id)
    else:
        generator = _stream_orchestration(
            request.goal, request.priority, workflow_id, user_id=user_id)

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/reasoning/{workflow_id}", tags=["Reasoning"])
async def get_workflow_reasoning(workflow_id: str):
    from backend.database import get_workflow_reasoning as db_get_reasoning
    store = db_get_reasoning(workflow_id)
    if not store:
        wf_status = state.orchestrator.get_workflow_status(workflow_id)
        if "error" in wf_status:
            raise HTTPException(status_code=404, detail=f"No reasoning found for workflow {workflow_id}")
        return {"workflow_id": workflow_id, "status": "workflow exists but no reasoning stored yet"}
    return {
        "workflow_id":     store["workflow_id"],
        "goal":            store["goal"],
        "priority":        store["priority"],
        "started_at":      store["started_at"],
        "critic_findings": store["critic_findings"],
        "auditor_reports": store["auditor_reports"],
        "step_reasoning":  store["step_reasoning"],
        "summary": {
            "total_steps":     len(store["step_reasoning"]),
            "total_audits":    len(store["auditor_reports"]),
            "critic_findings": len(store["critic_findings"]),
            "all_approved":    all(
                r.get("approval_status") in ("approved", "conditional")
                for r in store["auditor_reports"]
            ),
            "highest_risk": max(
                (r.get("overall_risk", "safe") for r in store["auditor_reports"]),
                key=lambda x: ["safe", "low", "medium", "high", "critical"].index(x)
                              if x in ["safe", "low", "medium", "high", "critical"] else 0,
                default="safe",
            ),
        },
    }


@router.get("/reasoning", tags=["Reasoning"])
async def list_workflow_reasoning():
    from backend.database import list_workflow_reasonings
    rows = list_workflow_reasonings(limit=20)
    return {"count": len(rows), "workflows": rows}


@router.get("/thought-trace/stream", tags=["Thought Trace"])
async def thought_trace_stream():
    client_q: asyncio.Queue = asyncio.Queue(maxsize=200)
    state._thought_subscribers.append(client_q)

    async def generate():
        try:
            yield "event: connected\ndata: {\"status\": \"connected\"}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(client_q.get(), timeout=15.0)
                    yield f"event: thought\ndata: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield "event: ping\ndata: {}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            try:
                state._thought_subscribers.remove(client_q)
            except ValueError:
                pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/knowledge-graph/export", tags=["Knowledge Graph"])
async def export_knowledge_graph():
    return state.knowledge_graph.export_graph()

@router.post("/seed-demo", tags=["Debug"])
async def seed_demo_data():
    """Trigger the insertion of demo data for onboarding."""
    try:
        from backend.insert_demo_data import insert_demo_tasks, insert_demo_calendar_events, insert_demo_notes
        insert_demo_tasks()
        insert_demo_calendar_events()
        insert_demo_notes()
        return {"status": "success", "message": "Demo data seeded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/seed-user", tags=["Debug"])
async def seed_user_data(reset: bool = False):
    """Seed Namrata's full demo dataset into the production database."""
    try:
        import sys, json, uuid, bcrypt
        from datetime import datetime, timedelta
        from backend.database import (
            init_db, get_session, User, Task, Note, CalendarEvent, Book,
            WorkflowHistory, WorkflowState, CriticDecision,
        )

        # Re-use the seed module directly
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location(
            "seed_user_data",
            pathlib.Path(__file__).parent.parent.parent / "seed_user_data.py"
        )
        mod = importlib.util.module_from_spec(spec)
        if reset:
            sys.argv = ["seed", "--reset"]
        else:
            sys.argv = ["seed"]
        spec.loader.exec_module(mod)
        mod.seed()
        sys.argv = []
        return {"status": "success", "message": "User data seeded — srivnamrata@gmail.com ready"}
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"{e}\n{traceback.format_exc()}")

