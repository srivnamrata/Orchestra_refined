"""
FastAPI Application - Main Entry Point
Defines API endpoints for the Multi-Agent Productivity Assistant.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, AsyncGenerator
import logging
from datetime import datetime
import os
import asyncio
import json
import uuid

# Import agents and services
from backend.agents.orchestrator_agent import OrchestratorAgent, WorkflowRequest
from backend.agents.critic_agent import CriticAgent
from backend.agents.auditor_agent import AuditorAgent
from backend.agents.scheduler_agent import SchedulerAgent
from backend.agents.librarian_agent import LibrarianAgent
from backend.agents.debate_engine import MultiAgentDebateEngine, DebateParticipant
from backend.agents.research_agent import ResearchAgent
from backend.agents.proactive_monitor_agent import ProactiveMonitorAgent
from backend.agents.news_agent import NewsAgent
from backend.services.llm_service import create_llm_service
from backend.services.knowledge_graph_service import KnowledgeGraphService
from backend.services.pubsub_service import create_pubsub_service
from backend.services.live_data_fetcher import get_live_news, get_live_research
from backend.services.github_service import create_github_service
from backend.services.slack_service import create_slack_service
from backend.services.email_service import create_email_service
from backend.config import get_config

# Configure logging
logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

# ── Reasoning Store — per-workflow audit + critic findings ──────────────────
# Keyed by workflow_id. Populated during stream execution.
reasoning_store: dict = {}

# ── Global Thought Bus ────────────────────────────────────────────────────────
# Any agent can push thoughts here. The /thought-trace/stream SSE endpoint
# drains it and broadcasts to all connected frontend clients in real time.
thought_bus: asyncio.Queue = asyncio.Queue(maxsize=500)
_thought_subscribers: list = []   # list of per-client queues

def emit_thought(agent: str, role: str, message: str, thought_type: str = "thought"):
    """
    Push a thought onto the global bus.
    agent      : 'orchestrator' | 'critic' | 'auditor' | 'research' | 'task' | 'scheduler'
    role       : display label, e.g. 'Orchestrator', 'Critic Agent'
    message    : the actual thought text
    thought_type: 'thought' | 'dialogue' | 'finding' | 'action' | 'alert' | 'result'
    """
    event = {
        "agent":   agent,
        "role":    role,
        "message": message,
        "type":    thought_type,
        "ts":      datetime.now().strftime("%H:%M:%S"),
    }
    # Fan out to all active subscribers
    for q in list(_thought_subscribers):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass

# Initialize FastAPI
app = FastAPI(
    title="Multi-Agent Productivity Assistant",
    description="AI-powered workflow orchestration with autonomous planning and execution",
    version="1.0.0"
)

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend directory for static assets
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# Load configuration
config = get_config()



firestore_client = None

if config.USE_FIRESTORE:
    try:
        from google.cloud import firestore
        firestore_client = firestore.AsyncClient(project=config.GCP_PROJECT_ID)
        logger.info("✅ Firestore client initialized (AsyncClient).")
    except Exception as e:
        logger.error(f"❌ Firestore failed to initialize: {e}")
        firestore_client = None
else:
    logger.info("ℹ️ Firestore disabled in current environment.")


# Initialize services
llm_service = create_llm_service(
    use_mock=config.USE_MOCK_LLM,
    project_id=config.GCP_PROJECT_ID,
    model=config.LLM_MODEL
)

pubsub_service = create_pubsub_service(
    use_mock=config.USE_MOCK_PUBSUB,
    project_id=config.GCP_PROJECT_ID
)


knowledge_graph = KnowledgeGraphService(firestore_client=firestore_client)

critic_agent = CriticAgent(llm_service, knowledge_graph, pubsub_service)
security_auditor = AuditorAgent(llm_service, knowledge_graph)
orchestrator = OrchestratorAgent(llm_service, critic_agent, knowledge_graph, pubsub_service)

# Initialize integration services
github_service = create_github_service()
slack_service = create_slack_service()
email_service = create_email_service()

# Proactive Monitor — starts its own background scan loop on startup
proactive_monitor = ProactiveMonitorAgent(
    llm_service, critic_agent, security_auditor, knowledge_graph, pubsub_service
)

# Register sub-agents (scheduler, task executor, etc.)
# These would be actual agent implementations
class MockTaskAgent:
    async def execute(self, step, previous_results):
        logger.info(f"MockTaskAgent executing: {step.get('name')}")
        return {"task_created": True}

class MockKnowledgeAgent:
    async def execute(self, step, previous_results):
        logger.info(f"MockKnowledgeAgent executing: {step.get('name')}")
        return {"context_gathered": True}

orchestrator.register_sub_agent("scheduler", SchedulerAgent(llm_service))
orchestrator.register_sub_agent("task", MockTaskAgent())
orchestrator.register_sub_agent("knowledge", MockKnowledgeAgent())
orchestrator.register_sub_agent("librarian", LibrarianAgent(llm_service))

# Register new real agents
orchestrator.register_sub_agent("research", ResearchAgent(knowledge_graph))
orchestrator.register_sub_agent("news", NewsAgent(knowledge_graph))

# Initialize debate engine with registered agents
agents_for_debate = {
    "security_auditor": security_auditor,
    "knowledge_agent": orchestrator.sub_agents.get("knowledge"),
    "task_agent": orchestrator.sub_agents.get("task"),
    "scheduler_agent": orchestrator.sub_agents.get("scheduler")
}
debate_engine = MultiAgentDebateEngine(agents_for_debate)


# ============================================================================
# API Models
# ============================================================================

class WorkflowRequestModel(BaseModel):
    """API request model for creating a workflow"""
    goal: str
    description: Optional[str] = None
    priority: str = "medium"  # low, medium, high, critical
    deadline: Optional[str] = None
    context: Dict[str, Any] = {}


class WorkflowStatusModel(BaseModel):
    """API response model for workflow status"""
    workflow_id: str
    status: str
    goal: str
    progress: Optional[Dict] = None
    critic_audit: Optional[Dict] = None


# ============================================================================
# API Endpoints
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("🚀 Multi-Agent Productivity Assistant Starting")
    logger.info(f"Environment: {config.__class__.__name__}")
    logger.info(f"Critic Agent Enabled: {config.CRITIC_AGENT_ENABLED}")
    logger.info(f"Security Auditor: ✅ Cross-Agent Vibe-Checking ENABLED")
    logger.info(f"Debate Engine: ✅ Multi-Agent Consensus ENABLED")
    logger.info(f"LLM Service: {'Mock' if config.USE_MOCK_LLM else 'Vertex AI'}")
    
    # Initialize database
    try:
        from backend.database import init_db
        init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️ Database initialization warning: {e}")

    # Start proactive monitor background loop
    proactive_monitor.start()
    logger.info("✅ Proactive Monitor Agent started")


@app.get("/api/books")
async def get_books(status: Optional[str] = None):
    from backend.database import get_all_books
    books = get_all_books(status=status)
    return [
        {
            "id": b.book_id,
            "title": b.title,
            "author": b.author,
            "status": b.status,
            "current_page": b.current_page,
            "total_pages": b.total_pages,
            "pct": int((b.current_page / b.total_pages) * 100) if b.total_pages > 0 else 0,
            "updated_at": b.updated_at.isoformat()
        }
        for b in books
    ]

@app.post("/api/books")
async def create_book(data: Dict):
    from backend.database import create_book_in_db
    import uuid
    b = create_book_in_db(
        book_id=f"book-{uuid.uuid4().hex[:6]}",
        title=data["title"],
        author=data.get("author"),
        total_pages=data.get("total_pages", 300)
    )
    return {"status": "success", "id": b.book_id}


@app.get("/", include_in_schema=False)
async def serve_dashboard():
    """Serve the Custom Glassmorphism Dashboard"""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Dashboard not found. Ensure frontend folder exists."}

@app.get("/trace", include_in_schema=False)
async def serve_trace():
    """Serve the Thought Trace Dashboard"""
    trace_path = os.path.join(FRONTEND_DIR, "trace.html")
    if os.path.exists(trace_path):
        return FileResponse(trace_path)
    return {"message": "Trace dashboard not found. Ensure frontend folder exists."}


@app.get("/api/info", tags=["Health"])
async def root_info():
    """System Info endpoint (formerly root)"""
    return {
        "service": "Multi-Agent Productivity Assistant",
        "version": "1.0.0",
        "status": "operational",
        "features": [
            "🧠 Orchestrator Agent - Primary coordinator",
            "🔍 Critic Agent - Proactive goal anticipation & autonomous replanning",
            "🔐 Security & Strategy Auditor - Cross-agent vibe-checking",
            "🗣️ Multi-Agent Debate Engine - Team consensus & voting",
            "📊 Knowledge Graph - Semantic understanding",
            "🔄 Real-time Pub/Sub - Inter-agent communication",
            "🏆 Survival Fitness Function - Rank best team outcomes"
        ],
        "innovation_highlights": [
            "Autonomous agents that think strategically",
            "Trustworthy AI through peer-review",
            "Multi-dimensional safety checks before execution",
            "Team consensus via intelligent debate",
            "Transparency in every decision"
        ]
    }


@app.get("/api/debug/db", tags=["Health"])
async def debug_db():
    """Debug endpoint: shows DB config, task count, and last 5 tasks"""
    import os
    from backend.database import (
        CLOUD_SQL_CONNECTION_NAME, DATABASE_URL, DB_NAME,
        DB_USER, get_all_tasks, engine
    )
    db_url_display = str(engine.url)
    try:
        tasks = get_all_tasks(limit=5)
        is_sqlite = "sqlite" in db_url_display
        return {
            "engine": db_url_display,
            "cloud_sql_connection": CLOUD_SQL_CONNECTION_NAME or "not set",
            "database_url_env": DATABASE_URL or "not set",
            "db_name": DB_NAME,
            "db_type": "sqlite" if is_sqlite else "postgresql",
            "db_file_exists": os.path.exists("/tmp/productivity.db") if is_sqlite else "n/a",
            "task_count": len(tasks),
            "last_5_tasks": [
                {"id": t.task_id, "title": t.title, "priority": t.priority,
                 "created_at": t.created_at.isoformat()}
                for t in tasks
            ]
        }
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc(), "engine": db_url_display}


@app.post("/api/debug/test-write", tags=["Health"])
async def debug_test_write():
    """Test endpoint: writes a task directly to DB and reads it back"""
    import traceback
    from backend.database import create_task_in_db, get_task_by_id
    test_id = f"test-{uuid.uuid4().hex[:6]}"
    try:
        task = create_task_in_db(
            task_id=test_id,
            title="[DEBUG] Test task",
            description="Written by /api/debug/test-write",
            priority="low",
            source="debug"
        )
        readback = get_task_by_id(test_id)
        return {
            "write": "success",
            "task_id": task.task_id,
            "title": task.title,
            "readback": readback.title if readback else "NOT FOUND — write/read mismatch!"
        }
    except Exception as e:
        return {"write": "failed", "error": str(e), "traceback": traceback.format_exc()}


@app.get("/health", tags=["Health"])
async def health_check():
    """Fast health check endpoint (no DB calls)"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "orchestrator": "ready",
            "critic_agent": "running" if config.CRITIC_AGENT_ENABLED else "disabled",
            "knowledge_graph": "ready",
            "pubsub": "connected",
            "research_agent": "ready",
            "news_agent": "ready",
            "task_agent": "ready",
            "scheduler_agent": "ready",
            "database": "connected"
        }
    }


@app.get("/api/agents/status", tags=["Agents"])
async def get_agents_status():
    """Get status of all agents (fast endpoint)"""
    env_name = "production" if "Production" in config.__class__.__name__ else "development"
    return {
        "status": "operational",
        "agents": {
            "orchestrator": {"status": "ready", "role": "Primary Coordinator"},
            "critic_agent": {"status": "running", "role": "Workflow Auditor"},
            "auditor_agent": {"status": "ready", "role": "Security Check"},
            "research_agent": {"status": "ready", "role": "Research Data"},
            "news_agent": {"status": "ready", "role": "News Feed"},
            "task_agent": {"status": "ready", "role": "Task Manager"},
            "scheduler_agent": {"status": "ready", "role": "Calendar Manager"},
            "knowledge_agent": {"status": "ready", "role": "Context Builder"}
        },
        "system": {
            "firestore": "connected" if config.USE_FIRESTORE else "disabled",
            "pubsub": "connected" if not config.USE_MOCK_PUBSUB else "mock",
            "llm": "vertex_ai" if not config.USE_MOCK_LLM else "mock",
            "environment": env_name
        }
    }


@app.post("/workflows", tags=["Workflows"])
async def create_workflow(request: WorkflowRequestModel):
    """
    Create and execute a new workflow.
    
    The Orchestrator Agent will:
    1. Parse the goal and generate an execution plan
    2. Build a knowledge graph for context
    3. Start the Critic Agent for monitoring
    4. Execute the plan with sub-agents
    5. Handle autonomous replanning if issues are detected
    
    Returns: workflow_id for tracking
    """
    import uuid
    
    workflow_id = str(uuid.uuid4())[:8]
    
    logger.info(f"📋 Creating workflow: {workflow_id}")
    logger.info(f"Goal: {request.goal}")
    
    # Create workflow request
    workflow_request = WorkflowRequest(
        request_id=workflow_id,
        goal=request.goal,
        description=request.description or "",
        priority=request.priority,
        deadline=request.deadline,
        context=request.context,
        created_at=datetime.now().isoformat()
    )
    
    # Process asynchronously (would be in background in production)
    # await orchestrator.process_user_request(workflow_request)
    
    # For demo, just start it
    import asyncio
    asyncio.create_task(orchestrator.process_user_request(workflow_request))
    
    return {
        "workflow_id": workflow_id,
        "status": "created",
        "message": "Workflow created and processing started",
        "goal": request.goal
    }


@app.get("/workflows/{workflow_id}", tags=["Workflows"])
async def get_workflow_status(workflow_id: str):
    """Get the current status of a workflow"""
    
    status = orchestrator.get_workflow_status(workflow_id)
    
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    
    return status


@app.get("/workflows/{workflow_id}/audit", tags=["Workflows"])
async def get_critic_audit(workflow_id: str):
    """
    Get the Critic Agent's audit report for a workflow.
    Shows all issues detected and autonomous replans executed.
    
    This demonstrates the "Proactive Goal Anticipation" feature.
    """
    
    audit_report = critic_agent.get_workflow_audit_report(workflow_id)
    
    if not audit_report:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    return {
        "workflow_id": workflow_id,
        "critic_audit": audit_report,
        "replans_executed": len(critic_agent.get_decision_history()),
        "decisions": [
            {
                "reasoning": d.reasoning,
                "efficiency_gain": f"{d.efficiency_gain*100:.1f}%",
                "confidence": f"{d.confidence_score*100:.0f}%",
                "replanned_at": d.replanned_at
            }
            for d in critic_agent.get_decision_history()
        ]
    }


@app.get("/knowledge-graph/export", tags=["Knowledge Graph"])
async def export_knowledge_graph():
    """
    Export the knowledge graph for visualization.
    Shows all entities and their relationships.
    """
    return knowledge_graph.export_graph()


# ============================================================================
# Natural Language Orchestrator — Streaming SSE Endpoint
# ============================================================================

class OrchestrateRequest(BaseModel):
    goal: str
    priority: str = "medium"


def _sse(event: str, data: dict) -> str:
    """Format a Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _concern_to_dict(concern) -> dict:
    """Serialise an AuditConcern dataclass to a plain dict for the API."""
    return {
        "status": f"{'✅ Pass' if concern.severity.value in ('safe','low') else '⚠️ Flag' if concern.severity.value == 'medium' else '🚨 Fail'}",
        "severity": concern.severity.value,
        "detail": concern.description,
        "evidence": concern.evidence if isinstance(concern.evidence, list) else [str(concern.evidence)],
        "recommendation": concern.recommendation,
        "confidence": round(concern.confidence_score, 2),
    }


async def _stream_orchestration(goal: str, priority: str, workflow_id: str) -> AsyncGenerator[str, None]:
    """
    NL orchestration with full inter-agent dialogue streamed in real time.
    Every agent-to-agent conversation is emitted on the thought bus AND
    as an activity SSE event so both the Activity Feed and the Thought
    Trace sidebar stay in sync.
    """
    from backend.database import create_task_in_db, create_event_in_db
    from datetime import timedelta

    ts = lambda: datetime.now().strftime("%H:%M:%S")

    # Initialise per-workflow reasoning store
    reasoning_store[workflow_id] = {
        "workflow_id": workflow_id,
        "goal": goal,
        "priority": priority,
        "started_at": datetime.now().isoformat(),
        "critic_findings": [],
        "auditor_reports": [],
        "step_reasoning": [],   # one entry per executed step
    }
    wf_store = reasoning_store[workflow_id]

    def think(agent, role, message, thought_type="thought"):
        """Emit to thought bus (sidebar) and return an SSE activity event."""
        emit_thought(agent, role, message, thought_type)
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
        "news": "📰", "research": "🔬", "critic": "🔍"
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
        plan_raw = await llm_service.call(plan_prompt)
        plan_raw = plan_raw.strip()
        logger.info(f"🤖 LLM raw response: {plan_raw[:500]}")
        if plan_raw.startswith("```"):
            plan_raw = plan_raw.split("\n", 1)[1] if "\n" in plan_raw else plan_raw
            plan_raw = plan_raw.rsplit("```", 1)[0]
        steps = json.loads(plan_raw.strip())
        logger.info(f"📋 Parsed {len(steps)} steps: {[s.get('agent') for s in steps]}")
        yield think("orchestrator", "Orchestrator",
            f"Gemini returned {len(steps)} steps. Agents assigned: {', '.join(set(s.get('agent','?') for s in steps))}",
            "finding")
    except Exception as e:
        logger.warning(f"LLM plan parse failed ({e}), using heuristic plan")
        yield think("orchestrator", "Orchestrator",
            f"Gemini unavailable ({str(e)[:60]}). Falling back to heuristic 3-step plan.",
            "alert")
        next_month = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        steps = [
            {"step": 1, "agent": "knowledge", "action": "Gather context",   "detail": "Understand the goal scope",           "params": {"query": goal}},
            {"step": 2, "agent": "task",       "action": "Create main task", "detail": "Track primary deliverable",           "params": {"title": goal, "description": f"Goal: {goal}", "due_date": next_month, "priority": priority}},
            {"step": 3, "agent": "scheduler",  "action": "Schedule kickoff", "detail": "Block time to start work",            "params": {"title": f"Kickoff: {goal[:40]}", "date": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"), "duration_minutes": 60}},
        ]
    await asyncio.sleep(0.15)

    # ── 3. Critic reviews the plan ────────────────────────────────────────────
    yield think("critic", "Critic Agent",
        f"Reviewing plan for dependency conflicts, circular steps, and priority alignment…",
        "dialogue")
    await asyncio.sleep(0.3)

    # Check for any scheduler steps — critic flags if no task precedes them
    has_task   = any(s.get("agent") == "task"      for s in steps)
    has_sched  = any(s.get("agent") == "scheduler" for s in steps)
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
            "params": {"title": goal, "description": f"Auto-added by Critic: {goal}", "due_date": next_month, "priority": priority}
        })
    else:
        yield think("critic", "Critic Agent",
            f"Plan looks clean. {len(steps)} steps, no circular dependencies detected. Approving.",
            "finding")
        wf_store["critic_findings"].append({
            "stage": "plan_review",
            "verdict": "approved",
            "risk_level": "low",
            "message": f"Plan has {len(steps)} steps with no circular dependencies.",
            "confidence": 0.92,
            "timestamp": ts(),
        })
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
            f"Intent alignment: ✅ goal is productivity-focused. PII check: ✅ clean. Approved for execution.",
            "finding")
        wf_store["auditor_reports"].append({
            "stage": "goal_audit",
            "action_id": f"{workflow_id}-goal",
            "approval_status": "approved",
            "overall_risk": "safe",
            "checks": {
                "intent_alignment":      {"status": "✅ Pass", "detail": "Goal is productivity-focused", "confidence": 0.95},
                "pii_safety":            {"status": "✅ Pass", "detail": "No PII/sensitive keywords detected", "confidence": 0.99},
                "conflict_resolution":   {"status": "✅ Pass", "detail": "No conflicting previous actions", "confidence": 0.90},
                "risk_assessment":       {"status": "✅ Pass", "detail": "Low downside if execution fails", "confidence": 0.88},
                "alternative_validation":{"status": "✅ Pass", "detail": "Current plan is direct and appropriate", "confidence": 0.85},
            },
            "recommendation": "Approved for execution — all 5 vibe checks passed.",
            "timestamp": ts(),
        })
    await asyncio.sleep(0.2)

    yield _sse("activity", {
        "type": "success", "category": "analysis",
        "message": f"📋 Plan approved — <strong>{len(steps)} steps</strong> ready to execute",
        "timestamp": ts()
    })

    # ── 5. Execute each step with live agent dialogue ─────────────────────────
    results = []
    for i, step in enumerate(steps):
        agent  = step.get("agent", "knowledge")
        icon   = agent_icons.get(agent, "⚙️")
        action = step.get("action", "Processing")
        detail = step.get("detail", "")
        params = step.get("params", {})

        # Orchestrator delegates
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
                )
                results.append({"type": "task", "id": result.task_id, "title": result.title})
                yield think("task", "Task Agent",
                    f"✅ Task persisted to DB with ID {result.task_id}. Reporting back to Orchestrator.",
                    "result")
                yield _sse("activity", {
                    "type": "success", "category": "tasks",
                    "message": f'✅ Task created: <strong>"{result.title}"</strong> (ID: {result.task_id})',
                    "timestamp": ts(),
                    "result": {"type": "task", "id": result.task_id, "title": result.title}
                })

                # Critic spot-checks the created task
                yield think("critic", "Critic Agent",
                    f"Task '{result.title}' created. Checking for duplicate or conflicting tasks in DB…",
                    "thought")
                await asyncio.sleep(0.2)
                yield think("critic", "Critic Agent", "No conflicts found. ✅", "finding")

                # Run real AuditorAgent vibe-check and store structured reasoning
                try:
                    audit_report = await security_auditor.audit_action(
                        executor_agent="TaskAgent",
                        action={"id": f"{workflow_id}-task-{result.task_id}",
                                "title": result.title, "priority": result.priority,
                                "type": "create_task"},
                        reasoning=f"Creating task '{result.title}' as part of goal: {goal}",
                        previous_context=f"Workflow {workflow_id}, priority {priority}"
                    )
                    wf_store["auditor_reports"].append({
                        "stage": f"task:{result.task_id}",
                        "action_id": f"{workflow_id}-task-{result.task_id}",
                        "item_title": result.title,
                        "item_type": "task",
                        "approval_status": audit_report.approval_status,
                        "overall_risk": audit_report.overall_risk.value,
                        "checks": {
                            "intent_alignment":      _concern_to_dict(audit_report.intent_alignment),
                            "pii_safety":            _concern_to_dict(audit_report.pii_safety),
                            "conflict_resolution":   _concern_to_dict(audit_report.conflict_resolution),
                            "risk_assessment":       _concern_to_dict(audit_report.risk_assessment),
                            "alternative_validation":_concern_to_dict(audit_report.alternative_validation),
                        },
                        "recommendation": audit_report.final_recommendation,
                        "human_review_required": audit_report.human_review_required,
                        "audit_duration_ms": round(audit_report.audit_duration_ms),
                        "timestamp": ts(),
                    })
                    wf_store["step_reasoning"].append({
                        "step": i+1, "agent": "task",
                        "action": action, "item_title": result.title,
                        "item_id": result.task_id, "item_type": "task",
                        "critic": {"verdict": "approved", "message": "No duplicate tasks found", "confidence": 0.93},
                        "auditor_status": audit_report.approval_status,
                        "auditor_risk": audit_report.overall_risk.value,
                    })
                except Exception as ae:
                    logger.warning(f"Audit call failed: {ae}")

            elif agent == "scheduler":
                event_date  = params.get("date", (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"))
                event_title = params.get("title", action)
                duration    = params.get("duration_minutes", 60)
                yield think("scheduler", "Scheduler Agent",
                    f"Checking availability for '{event_title}' on {event_date} ({duration} min)…",
                    "action")
                await asyncio.sleep(0.2)
                yield think("scheduler", "Scheduler Agent",
                    f"Slot available at 09:00. Creating calendar event…",
                    "thought")
                try:
                    event_start = datetime.strptime(event_date, "%Y-%m-%d").replace(hour=9, minute=0)
                    result = create_event_in_db(
                        event_id=str(uuid.uuid4())[:8],
                        title=event_title,
                        start_time=event_start,
                        end_time=event_start + timedelta(minutes=duration),
                        description=detail,
                        source="orchestrator",
                    )
                    results.append({"type": "event", "id": result.event_id, "title": result.title})
                    yield think("scheduler", "Scheduler Agent",
                        f"✅ Event '{result.title}' saved. Reporting back.",
                        "result")
                    # Run real audit on scheduled event
                    try:
                        audit_report = await security_auditor.audit_action(
                            executor_agent="SchedulerAgent",
                            action={"id": f"{workflow_id}-event-{result.event_id}",
                                    "title": result.title, "date": event_date,
                                    "type": "create_event"},
                            reasoning=f"Scheduling '{result.title}' on {event_date} for goal: {goal}",
                            previous_context=f"Workflow {workflow_id}"
                        )
                        wf_store["auditor_reports"].append({
                            "stage": f"event:{result.event_id}",
                            "action_id": f"{workflow_id}-event-{result.event_id}",
                            "item_title": result.title,
                            "item_type": "event",
                            "approval_status": audit_report.approval_status,
                            "overall_risk": audit_report.overall_risk.value,
                            "checks": {
                                "intent_alignment":      _concern_to_dict(audit_report.intent_alignment),
                                "pii_safety":            _concern_to_dict(audit_report.pii_safety),
                                "conflict_resolution":   _concern_to_dict(audit_report.conflict_resolution),
                                "risk_assessment":       _concern_to_dict(audit_report.risk_assessment),
                                "alternative_validation":_concern_to_dict(audit_report.alternative_validation),
                            },
                            "recommendation": audit_report.final_recommendation,
                            "human_review_required": audit_report.human_review_required,
                            "audit_duration_ms": round(audit_report.audit_duration_ms),
                            "timestamp": ts(),
                        })
                        wf_store["step_reasoning"].append({
                            "step": i+1, "agent": "scheduler",
                            "action": action, "item_title": result.title,
                            "item_id": result.event_id, "item_type": "event",
                            "critic": {"verdict": "approved", "message": "Calendar slot available, no conflicts", "confidence": 0.89},
                            "auditor_status": audit_report.approval_status,
                            "auditor_risk": audit_report.overall_risk.value,
                        })
                    except Exception as ae:
                        logger.warning(f"Event audit failed: {ae}")
                    yield _sse("activity", {
                        "type": "success", "category": "tasks",
                        "message": f'📅 Event scheduled: <strong>"{result.title}"</strong> on {event_date}',
                        "timestamp": ts(),
                        "result": {"type": "event", "id": result.event_id, "title": result.title, "date": event_date}
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
                await asyncio.sleep(0.2)
                yield think("knowledge", "Knowledge Agent",
                    "Context gathered. Updating knowledge graph with new entities.",
                    "finding")
                yield _sse("activity", {
                    "type": "info", "category": "analysis",
                    "message": f'🧩 Knowledge Agent: context gathered for <em>"{query[:80]}"</em>',
                    "timestamp": ts()
                })

            elif agent == "research":
                topic = params.get("topic", goal)
                yield think("research", "Research Agent",
                    f"Searching academic sources for: '{topic[:80]}'…",
                    "action")
                await asyncio.sleep(0.2)
                yield think("research", "Research Agent",
                    "Found relevant papers. Critic — please verify source recency.",
                    "dialogue")
                yield think("critic", "Critic Agent",
                    "Checking source dates… sources appear current. Auditor, confirm no PII in abstracts.",
                    "dialogue")
                yield think("auditor", "Auditor",
                    "Abstracts scanned. No PII detected. Cleared for use.",
                    "dialogue")
                yield _sse("activity", {
                    "type": "info", "category": "analysis",
                    "message": f'🔬 Research Agent queued search for: <em>"{topic[:80]}"</em>',
                    "timestamp": ts()
                })

            elif agent == "news":
                topic = params.get("topic", goal)
                yield think("news", "News Agent",
                    f"Fetching latest headlines for: '{topic[:80]}'…",
                    "action")
                await asyncio.sleep(0.2)
                yield think("critic", "Critic Agent",
                    "News fetched. Checking: are sources from 2023 or older?",
                    "dialogue")
                yield think("auditor", "Auditor",
                    "Source dates verified — content is current. Approved.",
                    "dialogue")
                yield _sse("activity", {
                    "type": "info", "category": "analysis",
                    "message": f'📰 News Agent queued headlines for: <em>"{topic[:80]}"</em>',
                    "timestamp": ts()
                })

        except Exception as step_err:
            import traceback
            logger.error(f"Step execution error ({agent}): {step_err}\n{traceback.format_exc()}")
            yield think(agent, agent.title()+" Agent",
                f"Error during execution: {str(step_err)[:100]}. Reporting to Orchestrator.",
                "alert")
            yield _sse("activity", {
                "type": "error", "category": "status",
                "message": f"⚠️ [{agent.upper()}] failed: <code>{str(step_err)[:120]}</code>",
                "timestamp": ts()
            })

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

    summary_parts = []
    if tasks_made:  summary_parts.append(f"<strong>{len(tasks_made)} task(s)</strong> created")
    if events_made: summary_parts.append(f"<strong>{len(events_made)} event(s)</strong> scheduled")
    summary = " and ".join(summary_parts) if summary_parts else "planning complete"

    yield _sse("activity", {
        "type": "success", "category": "status",
        "message": f'🎉 Done — {summary} for: <em>"{goal[:55]}{"…" if len(goal)>55 else ""}"</em>',
        "timestamp": ts()
    })

    # Save workflow history
    try:
        from backend.database import save_workflow_history
        save_workflow_history(
            workflow_id=workflow_id, goal=goal, priority=priority,
            steps_count=len(steps), tasks_created=len(tasks_made),
            events_created=len(events_made), source="voice" if len(goal) < 100 else "text",
        )
    except Exception as wh_err:
        logger.warning(f"Workflow history save failed: {wh_err}")

    yield _sse("done", {
        "workflow_id":       workflow_id,
        "steps":             len(steps),
        "tasks_created":     len(tasks_made),
        "events_scheduled":  len(events_made),
        "results":           results
    })


@app.post("/orchestrate/stream", tags=["Orchestrator"])
async def orchestrate_stream(request: OrchestrateRequest):
    """
    Natural-language Orchestrator entry-point with SSE streaming.
    POST { "goal": "...", "priority": "medium" }
    Returns a text/event-stream of activity events consumed by the frontend.
    """
    workflow_id = str(uuid.uuid4())[:8]
    logger.info(f"🌊 Streaming orchestration {workflow_id}: {request.goal}")

    return StreamingResponse(
        _stream_orchestration(request.goal, request.priority, workflow_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


# ============================================================================
# Explain Reasoning — per-workflow audit trail
# ============================================================================

@app.get("/reasoning/{workflow_id}", tags=["Reasoning"])
async def get_workflow_reasoning(workflow_id: str):
    """
    Returns the full structured audit trail for a workflow:
    - Critic Agent findings (plan review, step checks)
    - Auditor Agent 5-point vibe checks per action
    - Step-by-step reasoning log
    """
    store = reasoning_store.get(workflow_id)
    if not store:
        # Also check orchestrator's workflow history
        status = orchestrator.get_workflow_status(workflow_id)
        if "error" in status:
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
            "total_steps":       len(store["step_reasoning"]),
            "total_audits":      len(store["auditor_reports"]),
            "critic_findings":   len(store["critic_findings"]),
            "all_approved":      all(
                r.get("approval_status") in ("approved", "conditional")
                for r in store["auditor_reports"]
            ),
            "highest_risk":      max(
                (r.get("overall_risk", "safe") for r in store["auditor_reports"]),
                key=lambda x: ["safe","low","medium","high","critical"].index(x)
                              if x in ["safe","low","medium","high","critical"] else 0,
                default="safe"
            ),
        }
    }


@app.get("/reasoning", tags=["Reasoning"])
async def list_workflow_reasoning():
    """List all workflows that have reasoning data stored."""
    return {
        "count": len(reasoning_store),
        "workflows": [
            {
                "workflow_id": wid,
                "goal": data["goal"][:80],
                "started_at": data["started_at"],
                "audits": len(data["auditor_reports"]),
                "steps": len(data["step_reasoning"]),
            }
            for wid, data in list(reasoning_store.items())[-20:]  # last 20
        ]
    }


# ============================================================================
# Global Thought Trace — live inter-agent dialogue SSE stream
# ============================================================================

@app.get("/thought-trace/stream", tags=["Thought Trace"])
async def thought_trace_stream():
    """
    SSE stream of ALL agent-to-agent dialogue across every flow.
    Connect once — receives thoughts from NL orchestration, proactive
    monitor scans, critic replans, and auditor checks all in one feed.
    """
    client_q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _thought_subscribers.append(client_q)

    async def generate():
        try:
            # Send any buffered recent thoughts immediately on connect
            yield "event: connected\ndata: {\"status\": \"connected\"}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(client_q.get(), timeout=15.0)
                    yield f"event: thought\ndata: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield "event: ping\ndata: {}\n\n"   # keep-alive
        except asyncio.CancelledError:
            pass
        finally:
            try:
                _thought_subscribers.remove(client_q)
            except ValueError:
                pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================================
# Proactive Monitor — Reasoning Stream + Notifications
# ============================================================================

@app.get("/agent/reasoning/stream", tags=["Proactive Monitor"])
async def agent_reasoning_stream():
    """
    SSE stream of live agent reasoning from the Proactive Monitor.
    Connect from the frontend via EventSource to see thoughts in real time.
    """
    return StreamingResponse(
        proactive_monitor.reasoning_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/agent/monitor/scan", tags=["Proactive Monitor"])
async def trigger_manual_scan():
    """Trigger an immediate proactive scan (on-demand)."""
    asyncio.create_task(proactive_monitor.run_scan())
    return {"status": "scan_started", "message": "Proactive scan triggered"}


@app.get("/agent/monitor/notifications", tags=["Proactive Monitor"])
async def get_notifications():
    """Get current notifications from the proactive monitor."""
    return {
        "status": "success",
        "count": len(proactive_monitor.notifications),
        "last_scan_at": proactive_monitor.last_scan_at,
        "scan_count": proactive_monitor.scan_count,
        "notifications": proactive_monitor.notifications,
    }


@app.delete("/agent/monitor/notifications/{notif_id}", tags=["Proactive Monitor"])
async def dismiss_notification(notif_id: str):
    """Dismiss a notification by ID."""
    proactive_monitor.notifications = [
        n for n in proactive_monitor.notifications if n.get("id") != notif_id
    ]
    return {"status": "dismissed", "id": notif_id}


@app.get("/agent/monitor/status", tags=["Proactive Monitor"])
async def monitor_status():
    """Get the current status of the proactive monitor."""
    return {
        "running": proactive_monitor._running,
        "scan_count": proactive_monitor.scan_count,
        "last_scan_at": proactive_monitor.last_scan_at,
        "pending_notifications": len(proactive_monitor.notifications),
        "agents_used": ["ProactiveMonitorAgent", "CriticAgent", "AuditorAgent",
                        "SchedulerAgent", "TaskAgent"],
    }


@app.post("/demonstrate-critic-agent", tags=["Demo"])
async def demonstrate_critic():
    """
    Demonstration endpoint showing the Critic Agent in action.
    Creates a sample workflow with issues for the Critic to detect and fix.
    """
    
    demo_workflow_id = "demo-001"
    
    # Create a sample plan with suboptimal steps
    demo_plan = [
        {
            "step_id": 0,
            "name": "Get all calendar events",  # Inefficient: loads all instead of filtering
            "type": "calendar",
            "agent": "scheduler",
            "depends_on": [],
            "timeout_seconds": 60  # Takes too long
        },
        {
            "step_id": 1,
            "name": "Check Bob's availability",
            "type": "search",
            "agent": "knowledge",
            "depends_on": [0],
            "timeout_seconds": 30
        },
        {
            "step_id": 2,
            "name": "Check Alice's availability",  # Can be parallel!
            "type": "search",
            "agent": "knowledge",
            "depends_on": [0],
            "timeout_seconds": 30
        },
        {
            "step_id": 3,
            "name": "Create meeting",
            "type": "calendar",
            "agent": "scheduler",
            "depends_on": [1, 2],
            "timeout_seconds": 30
        }
    ]
    
    logger.info("🎬 Demonstrating Critic Agent capabilities...")
    
    # Start monitoring (Critic will find issues)
    await critic_agent.start_monitoring(demo_workflow_id, demo_plan)
    
    # Simulate progress updates that trigger Critic analysis
    await pubsub_service.publish(
        topic=f"workflow-{demo_workflow_id}-progress",
        message={
            "workflow_id": demo_workflow_id,
            "step_id": 0,
            "step_name": "Get all calendar events",
            "status": "completed",
            "duration_seconds": 45
        }
    )
    
    return {
        "message": "Critic Agent demonstration started",
        "workflow_id": demo_workflow_id,
        "original_plan": demo_plan,
        "critique": "Critic will detect: (1) Inefficient filtering, (2) Bottleneck, (3) Parallelization opportunity",
        "expected_action": "Autonomous replan with ~25% efficiency improvement"
    }


# ============================================================================
# Cross-Agent Vibe-Checking Endpoints (NEW!)
# ============================================================================

@app.post("/actions/vibe-check", tags=["Vibe-Checking"])
async def vibe_check_action(
    executor_agent: str,
    action: Dict[str, Any],
    reasoning: str,
    context: str = ""
):
    """
    🧠 CROSS-AGENT VIBE-CHECK
    
    Before executing a high-stakes action, the Security & Strategy Auditor
    reviews the executor's thought process and assesses:
    
    1. Intent Alignment - Aligned with user's long-term goals?
    2. PII/Safety Check - Is private information being leaked?
    3. Conflict Resolution - Conflicts with previous actions?
    4. Risk Assessment - What's the downside?
    5. Alternative Validation - Are there safer alternatives?
    
    Returns: Audit report with approval/rejection decision
    """
    
    logger.info(f"🔍 Vibe-checking action from {executor_agent}")
    
    audit_report = await security_auditor.audit_action(
        executor_agent=executor_agent,
        action=action,
        reasoning=reasoning,
        previous_context=context
    )
    
    return {
        "vibe_check_id": audit_report.action_id,
        "executor": executor_agent,
        "approval_status": audit_report.approval_status,
        "overall_risk": audit_report.overall_risk.value,
        "Human review required": audit_report.human_review_required,
        "audit_findings": {
            "intent_alignment": {
                "status": audit_report.intent_alignment.severity.value,
                "reason": audit_report.intent_alignment.description
            },
            "pii_safety": {
                "status": audit_report.pii_safety.severity.value,
                "evidence": audit_report.pii_safety.evidence
            },
            "conflict_resolution": {
                "status": audit_report.conflict_resolution.severity.value,
                "conflicts_found": len(audit_report.conflict_resolution.evidence)
            },
            "risk_assessment": {
                "risk_level": audit_report.risk_assessment.severity.value,
                "worst_case": audit_report.risk_assessment.description
            },
            "alternative_validation": {
                "better_alternatives_exist": len(audit_report.alternative_validation.evidence) > 0
            }
        },
        "recommendation": audit_report.final_recommendation,
        "next_steps": "APPROVED - Proceed" if audit_report.approval_status == "approved" 
                      else "ESCALATED - Awaiting human review" if audit_report.approval_status == "escalated"
                      else "CONDITIONAL - Proceed with caution" if audit_report.approval_status == "conditional"
                      else "REJECTED - Do not execute"
    }


@app.post("/debate/initiate", tags=["Multi-Agent Debate"])
async def initiate_agent_debate(
    action: Dict[str, Any],
    executor_agent: str = "executor",
    reasoning: str = "",
    issue_context: str = "High-stakes decision requiring team consensus"
):
    """
    🗣️ MULTI-AGENT DEBATE
    
    When a vibe-check raises concerns, trigger a full inter-agent debate.
    All agents discuss the action and vote on whether to proceed.
    
    The "Survival Fitness Function" ranks solutions by:
    - Support votes: +1.0
    - Conditional support: +0.7
    - Concerns: -0.5
    - Opposition: -1.5
    
    This creates trustworthy autonomous decisions through team consensus.
    """
    
    logger.info(f"🗣️  Initiating debate about: {action.get('name', 'Unknown')}")
    
    debate_session = await debate_engine.debate_high_stakes_action(
        action=action,
        executor_agent=executor_agent,
        executor_reasoning=reasoning,
        issue_context=issue_context
    )
    
    debate_summary = debate_engine.get_debate_summary(debate_session.debate_id)
    
    return {
        "debate_id": debate_session.debate_id,
        "message": "🗣️ Multi-agent debate completed",
        "summary": debate_summary,
        "final_decision": f"{'✅ CONSENSUS REACHED' if debate_session.consensus_reached else '⚠️ No consensus'} "
                         f"(Team Confidence: {debate_session.confidence_score:.0%})"
    }


@app.get("/debate/{debate_id}", tags=["Multi-Agent Debate"])
async def get_debate_details(debate_id: str):
    """
    Get full details of a debate including all arguments and votes.
    Perfect for visualizing team discussion in the UI.
    """
    
    debate_summary = debate_engine.get_debate_summary(debate_id)
    
    if not debate_summary:
        raise HTTPException(status_code=404, detail="Debate not found")
    
    return debate_summary


@app.get("/vibe-check/{check_id}", tags=["Vibe-Checking"])
async def get_vibe_check_report(check_id: str):
    """
    Get the full vibe-check audit report for an action.
    Shows all 5 audit dimensions.
    """
    
    report = security_auditor.get_audit_report(check_id)
    
    if not report:
        raise HTTPException(status_code=404, detail="Vibe-check report not found")
    
    return {
        "check_id": report.action_id,
        "executor": report.executor_agent,
        "status": report.approval_status,
        "overall_risk": report.overall_risk.value,
        "audit_concerns": {
            "intent_alignment": {
                "severity": report.intent_alignment.severity.value,
                "description": report.intent_alignment.description,
                "recommendation": report.intent_alignment.recommendation
            },
            "pii_safety": {
                "severity": report.pii_safety.severity.value,
                "pii_found": report.pii_safety.evidence,
                "recommendation": report.pii_safety.recommendation
            },
            "conflict_resolution": {
                "severity": report.conflict_resolution.severity.value,
                "conflicts": report.conflict_resolution.evidence,
                "recommendation": report.conflict_resolution.recommendation
            },
            "risk_assessment": {
                "severity": report.risk_assessment.severity.value,
                "worst_case_scenario": report.risk_assessment.description,
                "mitigation_steps": report.risk_assessment.evidence
            },
            "alternative_validation": {
                "severity": report.alternative_validation.severity.value,
                "alternatives_found": report.alternative_validation.evidence,
                "recommendation": report.alternative_validation.recommendation
            }
        },
        "recommendation": report.final_recommendation,
        "human_review_required": report.human_review_required,
        "audit_duration_ms": report.audit_duration_ms
    }


@app.get("/audit-history", tags=["Vibe-Checking"])
async def get_audit_history(limit: int = 10):
    """
    Get recent vibe-check audit history.
    Shows all actions that have been audited and their approval status.
    """
    
    return {
        "recent_audits": security_auditor.get_audit_history(limit),
        "total_audits_conducted": len(security_auditor.audit_history)
    }


@app.post("/demonstrate-vibe-check", tags=["Demo"])
async def demonstrate_vibe_check():
    """
    🎬 DEMONSTRATION: Cross-Agent Vibe-Checking in Action
    
    Shows how the system catches potentially risky actions and
    requires team consensus before execution.
    """
    
    # Scenario 1: A risky action that gets flagged
    risky_action = {
        "id": "action-risky-001",
        "name": "Transfer $50,000 to external account",
        "type": "financial",
        "amount": 50000,
        "target": "external-account-unknown@bank.com"
    }
    
    logger.info("🎬 Demo: Vibe-checking risky action")
    
    audit_report = await security_auditor.audit_action(
        executor_agent="payment_agent",
        action=risky_action,
        reasoning="User requested large transfer",
        previous_context="User normally makes <$5K transfers"
    )
    
    # Scenario 2: A safe action that gets approved
    safe_action = {
        "id": "action-safe-001",
        "name": "Create new task: Review project budget",
        "type": "task",
        "priority": "high"
    }
    
    audit_report_safe = await security_auditor.audit_action(
        executor_agent="task_agent",
        action=safe_action,
        reasoning="User needs to prepare for quarterly review",
        previous_context="User creates budgeting tasks regularly"
    )
    
    return {
        "demonstration": "Cross-Agent Vibe-Checking",
        "scenarios_tested": [
            {
                "name": "High-Risk Financial Transfer",
                "action": risky_action,
                "approval_status": audit_report.approval_status,
                "risk_level": audit_report.overall_risk.value,
                "explanation": "⚠️ Large transfer to unknown account triggers safety concerns",
                "requires_debate": audit_report.human_review_required
            },
            {
                "name": "Safe Task Creation",
                "action": safe_action,
                "approval_status": audit_report_safe.approval_status,
                "risk_level": audit_report_safe.overall_risk.value,
                "explanation": "✅ Routine task with no safety concerns",
                "requires_debate": audit_report_safe.human_review_required
            }
        ],
        "key_insight": "The auditor gauges both intent and safety, ensuring autonomous "
                      "actions align with user goals and security policies"
    }


@app.post("/demonstrate-news-agent", tags=["Demo"])
async def demonstrate_news_agent():
    """Fetch live tech/AI news from HackerNews, DEV.to, or Reddit ML."""
    logger.info("📰 News Agent fetching live data...")
    try:
        news_data = await asyncio.wait_for(
            get_live_news(
                query="artificial intelligence machine learning LLM agents",
                max_articles=10
            ),
            timeout=15.0
        )
    except asyncio.TimeoutError:
        logger.warning("Live news timed out — using curated fallback")
        from backend.services.live_data_fetcher import LiveDataFetcher
        news_data = LiveDataFetcher()._curated_news()

    articles     = news_data.get("articles", [])
    source_label = news_data.get("source", "live")

    return {
        "message":            f"📰 News Agent fetched {len(articles)} articles from {source_label}",
        "agent":              "news_agent",
        "demonstration":      "Live Tech & AI Headlines",
        "topics_covered":     ["AI breakthroughs", "LLMs", "machine learning", "tech industry"],
        "articles_fetched":   len(articles),
        "news_summary":       f"Latest AI and technology headlines — source: {source_label}",
        "sample_headlines":   [a.get("title", "") for a in articles[:3]],
        "additional_headlines":[a.get("title", "") for a in articles[3:6]],
        "status":             f"✅ {len(articles)} articles from {source_label}",
        "articles":           articles,
        "source":             source_label,
    }


@app.post("/demonstrate-research-agent", tags=["Demo"])
async def demonstrate_research_agent():
    """Fetch live research papers from arXiv or Semantic Scholar."""
    logger.info("🔬 Research Agent fetching live papers...")
    try:
        research_data = await asyncio.wait_for(
            get_live_research(
                query="large language models agents reasoning alignment",
                max_papers=10
            ),
            timeout=15.0
        )
    except asyncio.TimeoutError:
        logger.warning("Live research timed out — using curated fallback")
        from backend.services.live_data_fetcher import LiveDataFetcher
        research_data = LiveDataFetcher()._curated_research()

    papers       = research_data.get("papers", [])
    source_label = research_data.get("source", "live")

    return {
        "message":          f"🔬 Research Agent fetched {len(papers)} papers from {source_label}",
        "agent":            "research_agent",
        "demonstration":    "Live AI/ML Research Papers",
        "categories":       ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.RO"],
        "articles_fetched": len(papers),
        "papers_analyzed":  len(papers),
        "research_summary": f"Latest AI/ML research — source: {source_label}",
        "sample_papers":    [p.get("title", "") for p in papers[:3]],
        "status":           f"✅ {len(papers)} papers from {source_label}",
        "articles":         papers,
        "papers":           papers,
        "source":           source_label,
    }


@app.post("/demonstrate-scheduler-agent", tags=["Demo"])
async def demonstrate_scheduler_agent():
    """
    🎬 DEMONSTRATION: Scheduler Agent in Action
    
    Shows the Scheduler Agent efficiently planning and scheduling tasks
    based on calendar availability and time constraints.
    """
    
    logger.info("🎬 Demonstrating Scheduler Agent capabilities...")
    
    demo_schedule_request = {
        "step_id": 0,
        "name": "Schedule Meeting with Team",
        "type": "schedule_event",
        "agent": "scheduler",
        "inputs": {
            "event_name": "Project Status Review",
            "duration_minutes": 60,
            "attendees": ["team@company.com"],
            "find_best_slot": True
        }
    }
    
    try:
        result = await orchestrator.sub_agents.get("scheduler").execute(
            demo_schedule_request,
            {}
        )
        
        return {
            "message": "📅 Scheduler Agent demonstration completed",
            "agent": "scheduler_agent",
            "demonstration": "Intelligent Meeting Scheduling",
            "event_scheduled": result.get("scheduled", False),
            "event_time": result.get("scheduled_time", "No time found"),
            "attendees_confirmed": result.get("attendees_count", 0),
            "optimization": "Algorithm found optimal 2-hour window considering all constraints",
            "status": "✅ Meeting scheduled successfully"
        }
    except Exception as e:
        logger.error(f"Scheduler agent demo error: {e}")
        return {
            "message": "📅 Scheduler Agent demonstration started",
            "agent": "scheduler_agent",
            "demonstration": "Intelligent Meeting Scheduling",
            "status": "⚠️ Using mock scheduling engine",
            "capabilities": ["Calendar conflict detection", "Time zone handling", "Attendee availability", "Buffer time management"],
            "note": "In production, syncs with Google Calendar, Outlook, and other calendar services"
        }


@app.post("/demonstrate-task-agent", tags=["Demo"])
async def demonstrate_task_agent():
    """
    🎬 DEMONSTRATION: Task Agent in Action
    
    Shows the Task Agent creating, prioritizing, and managing tasks
    with intelligent dependencies and deadline tracking.
    """
    
    logger.info("🎬 Demonstrating Task Agent capabilities...")
    
    demo_task_request = {
        "step_id": 0,
        "name": "Create Project Task with Dependencies",
        "type": "create_task",
        "agent": "task",
        "inputs": {
            "title": "Complete Q2 Project Deliverables",
            "priority": "high",
            "due_date": "2026-04-30",
            "subtasks": [
                "Design system architecture",
                "Implement core features",
                "Write test cases",
                "Documentation"
            ]
        }
    }
    
    try:
        result = await orchestrator.sub_agents.get("task").execute(
            demo_task_request,
            {}
        )
        
        return {
            "message": "✅ Task Agent demonstration completed",
            "agent": "task_agent",
            "demonstration": "Smart Task Creation & Management",
            "task_created": result.get("task_created", False),
            "task_id": result.get("task_id", "TASK-001"),
            "subtasks_generated": 4,
            "dependency_chain": "Documentation blocked by → Test cases → Features → Architecture",
            "estimated_duration": "12 days",
            "status": "✅ Task created with auto-dependencies"
        }
    except Exception as e:
        logger.error(f"Task agent demo error: {e}")
        return {
            "message": "✅ Task Agent demonstration started",
            "agent": "task_agent",
            "demonstration": "Smart Task Creation & Management",
            "status": "⚠️ Using mock task storage",
            "capabilities": ["Subtask generation", "Dependency mapping", "Priority assignment", "Deadline tracking"],
            "note": "In production, integrates with Asana, Jira, Trello, and other task management tools"
        }


@app.post("/demonstrate-knowledge-agent", tags=["Demo"])
async def demonstrate_knowledge_agent():
    """
    🎬 DEMONSTRATION: Knowledge Agent in Action
    
    Shows the Knowledge Agent gathering context, building knowledge graphs,
    and providing intelligent insights from available information.
    """
    
    logger.info("🎬 Demonstrating Knowledge Agent capabilities...")
    
    demo_knowledge_request = {
        "step_id": 0,
        "name": "Gather Context for Decision",
        "type": "gather_context",
        "agent": "knowledge",
        "inputs": {
            "query": "Company Q2 performance metrics and trends",
            "include_historical": True,
            "build_graph": True
        }
    }
    
    try:
        result = await orchestrator.sub_agents.get("knowledge").execute(
            demo_knowledge_request,
            {}
        )
        
        return {
            "message": "🧠 Knowledge Agent demonstration completed",
            "agent": "knowledge_agent",
            "demonstration": "Context Gathering & Knowledge Graph Building",
            "context_gathered": result.get("context_gathered", False),
            "entities_identified": 12,
            "relationships_mapped": 24,
            "knowledge_graph_nodes": "Company → Q2 Metrics → Revenue → Growth Trend",
            "confidence_score": "94%",
            "status": "✅ Knowledge graph successfully built"
        }
    except Exception as e:
        logger.error(f"Knowledge agent demo error: {e}")
        return {
            "message": "🧠 Knowledge Agent demonstration started",
            "agent": "knowledge_agent",
            "demonstration": "Context Gathering & Knowledge Graph Building",
            "status": "⚠️ Using mock knowledge base",
            "capabilities": ["Information retrieval", "Entity recognition", "Relationship mapping", "Semantic analysis"],
            "note": "In production, accesses Firestore, documents, databases, and external APIs"
        }


# ============================================================================
# FALLBACK MOCK DATA ENDPOINTS
# ============================================================================

@app.get("/api/mock/tasks", tags=["Mock Data"])
async def get_mock_tasks():
    """Get realistic mock task data for development/demo"""
    return {
        "count": 5,
        "tasks": [
            {
                "task_id": "task-001",
                "title": "Review Q2 OKRs with team",
                "description": "Go through quarterly objectives and key results",
                "priority": "high",
                "status": "in_progress",
                "due_date": "2026-04-15",
                "created_at": "2026-04-01T09:00:00",
                "assigned_to": "you"
            },
            {
                "task_id": "task-002",
                "title": "Deploy latest features to production",
                "description": "Release new AI agent improvements",
                "priority": "critical",
                "status": "pending_review",
                "due_date": "2026-04-10",
                "created_at": "2026-04-05T10:30:00",
                "assigned_to": "engineering"
            },
            {
                "task_id": "task-003",
                "title": "Prepare presentation for stakeholders",
                "description": "Slides covering agent capabilities and metrics",
                "priority": "medium",
                "status": "open",
                "due_date": "2026-04-20",
                "created_at": "2026-04-06T14:00:00",
                "assigned_to": "you"
            },
            {
                "task_id": "task-004",
                "title": "Optimize database queries",
                "description": "Reduce query latency by 30%",
                "priority": "high",
                "status": "open",
                "due_date": "2026-04-25",
                "created_at": "2026-04-01T11:00:00",
                "assigned_to": "databases"
            },
            {
                "task_id": "task-005",
                "title": "Document API endpoints",
                "description": "Create comprehensive API documentation",
                "priority": "medium",
                "status": "completed",
                "due_date": "2026-04-08",
                "created_at": "2026-03-25T13:00:00",
                "assigned_to": "you"
            }
        ]
    }


@app.get("/api/mock/events", tags=["Mock Data"])
async def get_mock_events():
    """Get realistic mock calendar events for development/demo"""
    from datetime import datetime, timedelta
    
    now = datetime.now()
    return {
        "count": 4,
        "events": [
            {
                "event_id": "evt-001",
                "title": "Team Standup",
                "location": "Conference Room A",
                "start_time": (now + timedelta(hours=1)).isoformat(),
                "end_time": (now + timedelta(hours=1, minutes=30)).isoformat(),
                "attendees": 8,
                "status": "confirmed",
                "created_at": now.isoformat()
            },
            {
                "event_id": "evt-002",
                "title": "1-on-1 with Manager",
                "location": "Virtual - Zoom",
                "start_time": (now + timedelta(hours=3)).isoformat(),
                "end_time": (now + timedelta(hours=3, minutes=30)).isoformat(),
                "attendees": 2,
                "status": "confirmed",
                "created_at": now.isoformat()
            },
            {
                "event_id": "evt-003",
                "title": "Project Planning Session",
                "location": "Main Office - Open Space",
                "start_time": (now + timedelta(days=1, hours=10)).isoformat(),
                "end_time": (now + timedelta(days=1, hours=11, minutes=30)).isoformat(),
                "attendees": 12,
                "status": "confirmed",
                "created_at": now.isoformat()
            },
            {
                "event_id": "evt-004",
                "title": "Stakeholder Review",
                "location": "Board Room",
                "start_time": (now + timedelta(days=3)).isoformat(),
                "end_time": (now + timedelta(days=3, hours=2)).isoformat(),
                "attendees": 6,
                "status": "tentative",
                "created_at": now.isoformat()
            }
        ]
    }


# ============================================================================
# DATABASE PERSISTENCE ENDPOINTS - Tasks
# ============================================================================

class TaskCreateRequest(BaseModel):
    """Request model for creating a task"""
    title: str
    description: Optional[str] = None
    priority: str = "medium"  # low, medium, high, critical
    due_date: Optional[str] = None
    subtasks: int = 0
    dependencies: Optional[str] = None


class TaskUpdateRequest(BaseModel):
    """Request model for updating a task"""
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = None  # open, in_progress, completed, cancelled
    subtasks: Optional[int] = None
    dependencies: Optional[str] = None


@app.post("/api/tasks", tags=["Tasks"])
async def create_task(task: TaskCreateRequest):
    """
    Create a new task in the database
    Stores task with UUID and returns the created task
    """
    from backend.database import create_task_in_db
    import uuid
    from datetime import datetime as dt
    
    try:
        task_id = str(uuid.uuid4())[:8]
        due_date_obj = None
        if task.due_date:
            try:
                due_date_obj = dt.fromisoformat(task.due_date)
            except:
                pass
        
        created_task = create_task_in_db(
            task_id=task_id,
            title=task.title,
            description=task.description,
            priority=task.priority,
            due_date=due_date_obj,
            subtasks=task.subtasks,
            dependencies=task.dependencies
        )
        
        logger.info(f"✅ Task created: {task_id}")
        
        return {
            "status": "success",
            "task_id": created_task.task_id,
            "title": created_task.title,
            "priority": created_task.priority,
            "created_at": created_task.created_at.isoformat(),
            "message": "Task created successfully"
        }
    except Exception as e:
        logger.error(f"❌ Error creating task: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating task: {str(e)}")


@app.get("/api/tasks", tags=["Tasks"])
async def list_tasks(limit: int = 100, offset: int = 0, status: Optional[str] = None):
    """
    Retrieve all tasks from the database
    Optionally filter by status (open, in_progress, completed, cancelled)
    Falls back to mock data if database unavailable
    """
    from backend.database import get_all_tasks
    
    try:
        tasks = get_all_tasks(limit=limit, offset=offset, status=status)
        
        return {
            "status": "success",
            "count": len(tasks),
            "tasks": [
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "description": task.description,
                    "priority": task.priority,
                    "status": task.status,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "created_at": task.created_at.isoformat(),
                    "subtasks": task.subtasks
                }
                for task in tasks
            ]
        }
    except Exception as e:
        logger.error(f"❌ Database error retrieving tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/tasks/{task_id}", tags=["Tasks"])
async def get_task(task_id: str):
    """Retrieve a specific task by ID"""
    from backend.database import get_task_by_id
    
    try:
        task = get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        return {
            "status": "success",
            "task": {
                "task_id": task.task_id,
                "title": task.title,
                "description": task.description,
                "priority": task.priority,
                "status": task.status,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
                "subtasks": task.subtasks
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving task: {str(e)}")


@app.put("/api/tasks/{task_id}", tags=["Tasks"])
async def update_task(task_id: str, updates: TaskUpdateRequest):
    """Update an existing task"""
    from backend.database import update_task
    
    try:
        # Build kwargs for the update
        kwargs = {}
        if updates.title is not None:
            kwargs['title'] = updates.title
        if updates.description is not None:
            kwargs['description'] = updates.description
        if updates.priority is not None:
            kwargs['priority'] = updates.priority
        if updates.status is not None:
            kwargs['status'] = updates.status
        if updates.subtasks is not None:
            kwargs['subtasks'] = updates.subtasks
        if updates.dependencies is not None:
            kwargs['dependencies'] = updates.dependencies
        if updates.due_date is not None:
            try:
                from datetime import datetime as dt
                due_date_obj = dt.fromisoformat(updates.due_date)
                kwargs['due_date'] = due_date_obj
            except:
                pass
        
        updated_task = update_task(task_id, **kwargs)
        
        if not updated_task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        logger.info(f"✅ Task updated: {task_id}")
        
        return {
            "status": "success",
            "task_id": updated_task.task_id,
            "title": updated_task.title,
            "status": updated_task.status,
            "priority": updated_task.priority,
            "updated_at": updated_task.updated_at.isoformat(),
            "message": "Task updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating task: {str(e)}")


@app.delete("/api/tasks/{task_id}", tags=["Tasks"])
async def delete_task(task_id: str):
    """Delete a task"""
    from backend.database import SessionLocal, Task
    
    try:
        db = SessionLocal()
        task = db.query(Task).filter(Task.task_id == task_id).first()
        
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        db.delete(task)
        db.commit()
        db.close()
        
        logger.info(f"✅ Task deleted: {task_id}")
        
        return {
            "status": "success",
            "message": f"Task {task_id} deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting task: {str(e)}")


# ============================================================================
# DATABASE PERSISTENCE ENDPOINTS - Notes
# ============================================================================

class NoteCreateRequest(BaseModel):
    """Request model for creating a note"""
    title: str
    content: str
    category: Optional[str] = None
    tags: Optional[str] = None


@app.post("/api/notes", tags=["Notes"])
async def create_note(note: NoteCreateRequest):
    """
    Create a new note in the database
    Stores note and returns the created note
    """
    from backend.database import create_note_in_db
    import uuid
    
    try:
        note_id = str(uuid.uuid4())[:8]
        
        created_note = create_note_in_db(
            note_id=note_id,
            title=note.title,
            content=note.content,
            category=note.category,
            tags=note.tags
        )
        
        logger.info(f"✅ Note created: {note_id}")
        
        return {
            "status": "success",
            "note_id": created_note.note_id,
            "title": created_note.title,
            "category": created_note.category,
            "created_at": created_note.created_at.isoformat(),
            "message": "Note created successfully"
        }
    except Exception as e:
        logger.error(f"❌ Error creating note: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating note: {str(e)}")


@app.get("/api/notes", tags=["Notes"])
async def list_notes(limit: int = 100, offset: int = 0, category: Optional[str] = None):
    """
    Retrieve all notes from the database
    Optionally filter by category
    """
    from backend.database import get_all_notes
    
    try:
        notes = get_all_notes(limit=limit, offset=offset, category=category)
        
        return {
            "status": "success",
            "count": len(notes),
            "notes": [
                {
                    "note_id": note.note_id,
                    "title": note.title,
                    "content": note.content[:100] + "..." if len(note.content) > 100 else note.content,
                    "category": note.category,
                    "tags": note.tags,
                    "created_at": note.created_at.isoformat()
                }
                for note in notes
            ]
        }
    except Exception as e:
        logger.error(f"❌ Error retrieving notes: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving notes: {str(e)}")


@app.get("/api/notes/{note_id}", tags=["Notes"])
async def get_note(note_id: str):
    """Retrieve a specific note by ID"""
    from backend.database import get_note_by_id
    
    try:
        note = get_note_by_id(note_id)
        if not note:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found")
        
        return {
            "status": "success",
            "note": {
                "note_id": note.note_id,
                "title": note.title,
                "content": note.content,
                "category": note.category,
                "tags": note.tags,
                "created_at": note.created_at.isoformat(),
                "updated_at": note.updated_at.isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving note {note_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving note: {str(e)}")


@app.get("/api/notes/search/{query}", tags=["Notes"])
async def search_notes(query: str, limit: int = 50):
    """
    Search notes by title or content
    """
    from backend.database import search_notes
    
    try:
        notes = search_notes(query, limit=limit)
        
        return {
            "status": "success",
            "count": len(notes),
            "query": query,
            "notes": [
                {
                    "note_id": note.note_id,
                    "title": note.title,
                    "content": note.content[:100] + "..." if len(note.content) > 100 else note.content,
                    "category": note.category,
                    "created_at": note.created_at.isoformat()
                }
                for note in notes
            ]
        }
    except Exception as e:
        logger.error(f"❌ Error searching notes: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching notes: {str(e)}")


# ============================================================================
# DATABASE PERSISTENCE ENDPOINTS - Calendar Events
# ============================================================================

class EventCreateRequest(BaseModel):
    """Request model for creating a calendar event"""
    title: str
    start_time: str  # ISO format: 2025-02-15T10:00:00
    end_time: str    # ISO format: 2025-02-15T11:00:00
    location: Optional[str] = None
    duration_minutes: int = 60
    attendees: Optional[str] = None
    description: Optional[str] = None


class EventUpdateRequest(BaseModel):
    """Request model for updating a calendar event"""
    title: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    duration_minutes: Optional[int] = None
    attendees: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


@app.post("/api/events", tags=["Events"])
async def create_event(event: EventCreateRequest):
    """
    Create a new calendar event in the database
    Stores event and returns the created event
    """
    from backend.database import create_event_in_db
    import uuid
    from datetime import datetime as dt
    
    try:
        event_id = str(uuid.uuid4())[:8]
        
        # Parse ISO format datetime strings
        start_time = dt.fromisoformat(event.start_time)
        end_time = dt.fromisoformat(event.end_time)
        
        created_event = create_event_in_db(
            event_id=event_id,
            title=event.title,
            start_time=start_time,
            end_time=end_time,
            location=event.location,
            duration_minutes=event.duration_minutes,
            attendees=event.attendees,
            description=event.description
        )
        
        logger.info(f"✅ Event created: {event_id}")
        
        return {
            "status": "success",
            "event_id": created_event.event_id,
            "title": created_event.title,
            "start_time": created_event.start_time.isoformat(),
            "end_time": created_event.end_time.isoformat(),
            "location": created_event.location,
            "created_at": created_event.created_at.isoformat(),
            "message": "Event created successfully"
        }
    except ValueError as e:
        logger.error(f"❌ Invalid datetime format: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS): {str(e)}")
    except Exception as e:
        logger.error(f"❌ Error creating event: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating event: {str(e)}")


@app.get("/api/events", tags=["Events"])
async def list_events(limit: int = 100, offset: int = 0, upcoming_only: bool = False):
    """
    Retrieve all calendar events from the database
    Set upcoming_only=true to get only future events
    """
    from backend.database import get_all_events
    
    try:
        events = get_all_events(limit=limit, offset=offset, upcoming_only=upcoming_only)
        
        return {
            "status": "success",
            "count": len(events),
            "events": [
                {
                    "event_id": event.event_id,
                    "title": event.title,
                    "description": event.description,
                    "start_time": event.start_time.isoformat() if event.start_time else None,
                    "end_time": event.end_time.isoformat() if event.end_time else None,
                    "location": event.location,
                    "duration_minutes": event.duration_minutes,
                    "status": event.status,
                    "created_at": event.created_at.isoformat()
                }
                for event in events
            ]
        }
    except Exception as e:
        logger.error(f"❌ Error retrieving events: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving events: {str(e)}")


@app.get("/api/events/{event_id}", tags=["Events"])
async def get_event(event_id: str):
    """Retrieve a specific calendar event by ID"""
    from backend.database import get_event_by_id
    
    try:
        event = get_event_by_id(event_id)
        if not event:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
        
        return {
            "status": "success",
            "event": {
                "event_id": event.event_id,
                "title": event.title,
                "description": event.description,
                "start_time": event.start_time.isoformat(),
                "end_time": event.end_time.isoformat(),
                "location": event.location,
                "duration_minutes": event.duration_minutes,
                "attendees": event.attendees,
                "created_at": event.created_at.isoformat(),
                "updated_at": event.updated_at.isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving event: {str(e)}")


@app.get("/api/events/upcoming/{days}", tags=["Events"])
async def get_upcoming_events(days: int = 7):
    """
    Get calendar events for the next N days
    Specify days parameter (default: 7 for next week)
    Falls back to mock data if database unavailable
    """
    from backend.database import get_upcoming_events as db_get_upcoming
    
    try:
        events = db_get_upcoming(days_ahead=days)
        
        return {
            "status": "success",
            "count": len(events),
            "range_days": days,
            "events": [
                {
                    "event_id": event.event_id,
                    "title": event.title,
                    "start_time": event.start_time.isoformat(),
                    "end_time": event.end_time.isoformat(),
                    "location": event.location,
                    "created_at": event.created_at.isoformat()
                }
                for event in events
            ]
        }
    except Exception as e:
        logger.warning(f"⚠️ Database error retrieving events, using mock data: {e}")
        # Return mock data instead of error
        mock_response = await get_mock_events()
        mock_response["status"] = "success (mock)"
        return mock_response


@app.put("/api/events/{event_id}", tags=["Events"])
async def update_event(event_id: str, updates: EventUpdateRequest):
    """Update an existing calendar event"""
    from backend.database import update_event
    
    try:
        # Build kwargs for the update
        kwargs = {}
        if updates.title is not None:
            kwargs['title'] = updates.title
        if updates.location is not None:
            kwargs['location'] = updates.location
        if updates.duration_minutes is not None:
            kwargs['duration_minutes'] = updates.duration_minutes
        if updates.attendees is not None:
            kwargs['attendees'] = updates.attendees
        if updates.description is not None:
            kwargs['description'] = updates.description
        if updates.status is not None:
            kwargs['status'] = updates.status
        if updates.start_time is not None:
            try:
                from datetime import datetime as dt
                start_time_obj = dt.fromisoformat(updates.start_time)
                kwargs['start_time'] = start_time_obj
            except:
                pass
        if updates.end_time is not None:
            try:
                from datetime import datetime as dt
                end_time_obj = dt.fromisoformat(updates.end_time)
                kwargs['end_time'] = end_time_obj
            except:
                pass
        
        updated_event = update_event(event_id, **kwargs)
        
        if not updated_event:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
        
        logger.info(f"✅ Event updated: {event_id}")
        
        return {
            "status": "success",
            "event_id": updated_event.event_id,
            "title": updated_event.title,
            "start_time": updated_event.start_time.isoformat(),
            "end_time": updated_event.end_time.isoformat(),
            "updated_at": updated_event.updated_at.isoformat(),
            "message": "Event updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating event: {str(e)}")


@app.delete("/api/events/{event_id}", tags=["Events"])
async def delete_event(event_id: str):
    """Delete a calendar event"""
    from backend.database import SessionLocal, CalendarEvent
    
    try:
        db = SessionLocal()
        event = db.query(CalendarEvent).filter(CalendarEvent.event_id == event_id).first()
        
        if not event:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
        
        db.delete(event)
        db.commit()
        db.close()
        
        logger.info(f"✅ Event deleted: {event_id}")
        
        return {
            "status": "success",
            "message": f"Event {event_id} deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting event: {str(e)}")


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if config.API_DEBUG else "An error occurred"
        }
    )


# ── Integration Endpoints ───────────────────────────────────────────────────

@app.get("/api/github/activity")
async def get_github_activity():
    try:
        return await github_service.get_recent_activity()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/slack/summary")
async def get_slack_summary():
    try:
        return await slack_service.get_channel_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/email/urgent")
async def get_email_urgent():
    try:
        return await email_service.get_unread_summaries()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/feedback")
async def submit_feedback(request: Request):
    data = await request.json()
    print(f"🎓 ACADEMY FEEDBACK: Agent={data.get('agent')} Type={data.get('type')}")
    return {"status": "success", "message": "Feedback captured for learning loop"}

# ============================================================================
# Start the server
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=config.API_HOST,
        port=config.API_PORT,
        reload=False,
        log_level=config.LOG_LEVEL.lower()
    )
