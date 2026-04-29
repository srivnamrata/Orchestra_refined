"""
FastAPI application factory.
Creates the app, wires up lifespan, middleware, static files, and all routers.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api import state
from backend.api.routers import (
    agents, books, debate, demo, events, guru,
    integrations, mock_data, notes, tasks, workflows,
)
from backend.auth.router import router as auth_router
from backend.config import get_config

logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Multi-Agent Productivity Assistant Starting (Lifespan)")

    cfg = get_config()
    state.config = cfg

    # ── Redis ──────────────────────────────────────────────────────────────
    try:
        import redis as redis_lib
        state.redis_client = redis_lib.from_url(cfg.REDIS_URL, decode_responses=True)
        state.redis_client.ping()
        logger.info(f"✅ Redis connected: {cfg.REDIS_URL}")
    except Exception as e:
        logger.warning(f"⚠️  Redis unavailable ({e}) — auth will not work")
        state.redis_client = None

    # ── Core services ──────────────────────────────────────────────────────
    from backend.services.llm_service import create_llm_service
    from backend.services.pubsub_service import create_pubsub_service
    from backend.services.knowledge_graph_service import KnowledgeGraphService

    state.llm_service    = create_llm_service(use_mock=cfg.USE_MOCK_LLM, project_id=cfg.GCP_PROJECT_ID, model=cfg.LLM_MODEL)
    state.pubsub_service = create_pubsub_service(use_mock=cfg.USE_MOCK_PUBSUB, project_id=cfg.GCP_PROJECT_ID)

    firestore_client = None
    if cfg.USE_FIRESTORE:
        try:
            from google.cloud import firestore
            firestore_client = firestore.AsyncClient(project=cfg.GCP_PROJECT_ID)
            logger.info("✅ Firestore client initialized.")
        except Exception as e:
            logger.error(f"❌ Firestore failed: {e}")

    state.knowledge_graph = KnowledgeGraphService(firestore_client=firestore_client)

    # ── Agents ─────────────────────────────────────────────────────────────
    from backend.agents.critic_agent import CriticAgent
    from backend.agents.auditor_agent import AuditorAgent
    from backend.agents.orchestrator_agent import OrchestratorAgent
    from backend.agents.librarian_agent import LibrarianAgent
    from backend.agents.param_mitra_agent import ParamMitraAgent
    from backend.agents.research_agent import ResearchAgent
    from backend.agents.scheduler_agent import SchedulerAgent
    from backend.agents.news_agent import NewsAgent
    from backend.agents.debate_engine import MultiAgentDebateEngine
    from backend.agents.proactive_monitor_agent import ProactiveMonitorAgent
    from backend.services.github_service import GitHubService
    from backend.services.slack_service import SlackService
    from backend.services.email_service import EmailService

    state.critic_agent     = CriticAgent(state.llm_service, state.knowledge_graph, state.pubsub_service)
    state.security_auditor = AuditorAgent(state.llm_service, state.knowledge_graph)
    state.orchestrator     = OrchestratorAgent(state.llm_service, state.critic_agent, state.knowledge_graph, state.pubsub_service)
    state.github_service   = GitHubService()
    state.slack_service    = SlackService()
    state.email_service    = EmailService()
    state.veda_librarian   = LibrarianAgent(state.llm_service)
    state.param_mitra      = ParamMitraAgent(state.llm_service)

    state.proactive_monitor = ProactiveMonitorAgent(
        state.llm_service, state.critic_agent, state.security_auditor,
        state.knowledge_graph, state.pubsub_service, param_mitra_agent=state.param_mitra
    )

    from backend.agents.task_agent import TaskAgent
    from backend.agents.knowledge_agent import KnowledgeAgent
    from backend.agents.analytics_agent import AnalyticsAgent

    state.orchestrator.register_sub_agent("scheduler", SchedulerAgent(state.llm_service))
    state.orchestrator.register_sub_agent("librarian", state.veda_librarian)
    state.orchestrator.register_sub_agent("guru",      state.param_mitra)
    state.orchestrator.register_sub_agent("research",  ResearchAgent(state.knowledge_graph))
    state.orchestrator.register_sub_agent("task",      TaskAgent(state.knowledge_graph))
    state.orchestrator.register_sub_agent("knowledge", KnowledgeAgent(state.knowledge_graph))
    state.orchestrator.register_sub_agent("news",      NewsAgent(state.knowledge_graph))
    state.orchestrator.register_sub_agent("analytics", AnalyticsAgent(state.knowledge_graph, state.llm_service))

    state.debate_engine = MultiAgentDebateEngine({
        "security_auditor": state.security_auditor,
        "knowledge_agent":  state.orchestrator.sub_agents.get("knowledge"),
        "task_agent":       state.orchestrator.sub_agents.get("task"),
        "scheduler_agent":  state.orchestrator.sub_agents.get("scheduler"),
    })

    # ── Database ───────────────────────────────────────────────────────────
    try:
        from backend.database import init_db
        init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️ Database initialization warning: {e}")

    state.proactive_monitor.start()
    logger.info("✅ Proactive Monitor Agent started in background")

    yield

    logger.info("🛑 Shutting down...")


# ── App factory ──────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="Multi-Agent Productivity Assistant",
        description="AI-powered workflow orchestration with autonomous planning and execution",
        version="1.0.0",
        lifespan=lifespan,
    )

    cors_origins = [
        o.strip()
        for o in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*", "X-Session-Token"],
    )

    if os.path.exists(FRONTEND_DIR):
        app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    # ── Static page routes ────────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def serve_dashboard():
        index_path = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "Dashboard not found. Ensure frontend folder exists."}

    @app.get("/trace", include_in_schema=False)
    async def serve_trace():
        trace_path = os.path.join(FRONTEND_DIR, "trace.html")
        if os.path.exists(trace_path):
            return FileResponse(trace_path)
        return {"message": "Trace dashboard not found. Ensure frontend folder exists."}

    @app.get("/login", include_in_schema=False)
    async def serve_login():
        login_path = os.path.join(FRONTEND_DIR, "login.html")
        if os.path.exists(login_path):
            return FileResponse(login_path)
        return {"message": "Login page not found."}

    # ── Routers ───────────────────────────────────────────────────────────
    for router in [
        auth_router,
        tasks.router,
        events.router,
        notes.router,
        books.router,
        guru.router,
        agents.router,
        debate.router,
        workflows.router,
        demo.router,
        mock_data.router,
        integrations.router,
    ]:
        app.include_router(router)

    # ── Global error handler ──────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.error(f"Unhandled exception: {exc}")
        cfg = state.config
        return JSONResponse(
            status_code=500,
            content={
                "error":  "Internal server error",
                "detail": str(exc) if (cfg and cfg.API_DEBUG) else "An error occurred",
            },
        )

    return app


app = create_app()
