"""
Full demo seed for srivnamrata@gmail.com — covers every Orchestra agent and UI component.

Projects:
  1. AI Innovation Summit        → Orchestrator + Scheduler + TaskAgent
  2. Cloud Infrastructure 2026   → Critic (bottleneck), ProactiveMonitor
  3. Agentic R&D Lab             → Researcher + News + Veda/Librarian
  4. Security & Compliance Q2    → Auditor + Debate + ParamMitra/Guru

Run:  PYTHONPATH=. python3 backend/seed_user_data.py [--reset]
"""

import sys, json, uuid
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

import bcrypt
from backend.database import (
    init_db, get_session,
    User, Task, Note, CalendarEvent, Book,
    WorkflowHistory, WorkflowState, CriticDecision,
)

# ── helpers ──────────────────────────────────────────────────────────────────

def gid(prefix="id"):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"

def hpw(plain):
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

NOW = datetime.utcnow()

def dt(days=0, hours=0, minutes=0):
    return NOW + timedelta(days=days, hours=hours, minutes=minutes)


# ── main seed ────────────────────────────────────────────────────────────────

def seed():
    init_db()
    db = get_session()

    try:
        # ── 0. User ────────────────────────────────────────────────────────
        user = db.query(User).filter(User.email == "srivnamrata@gmail.com").first()
        if not user:
            user = User(
                email="srivnamrata@gmail.com",
                name="Namrata Srivastava",
                password_hash=hpw("Atharv19@"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"✅ User created: {user.email}")
        else:
            # Always refresh password hash so login works
            user.password_hash = hpw("Atharv19@")
            db.commit()
            print(f"✅ User refreshed: {user.email}")

        uid = user.id

        if "--reset" in sys.argv:
            for model in [CriticDecision, WorkflowHistory, WorkflowState,
                          Task, CalendarEvent, Note, Book]:
                db.query(model).filter(getattr(model, "user_id", None) == uid
                                       if hasattr(model, "user_id") else True).delete()
            db.commit()
            print("🗑  Existing data cleared")

        # ══════════════════════════════════════════════════════════════════
        # PROJECT 1 — AI INNOVATION SUMMIT
        # Showcases: OrchestratorAgent decomposing a complex goal into parallel
        # tasks, SchedulerAgent blocking calendar around dependencies,
        # TaskAgent tracking subtask progress.
        # ══════════════════════════════════════════════════════════════════
        print("\n🏗  Project 1: AI Innovation Summit")

        db.add(Note(note_id=gid("note"), title="Summit Vision & Goals",
            content="""# AI Innovation Summit — Product Brief

## Objective
Launch Orchestra's Multi-Agent framework to 500+ AI practitioners and showcase
autonomous workflow orchestration live on stage.

## Key Outcomes
- Live demo of 6-agent collaboration solving a real product problem in < 3 min
- 3 enterprise pilot sign-ups from attendees
- Press coverage from 2 tier-1 tech publications

## Orchestrator Strategy
The OrchestratorAgent will decompose the summit into 4 parallel workstreams:
Research → Design → Logistics → Marketing, with the CriticAgent monitoring for
schedule risk and the AuditorAgent validating all speaker contracts for PII.

## Agent Assignments
| Agent       | Responsibility                       |
|-------------|--------------------------------------|
| Scheduler   | Block calendar, send invites         |
| Researcher  | Speaker vetting, competitor summits  |
| TaskAgent   | Track 40+ action items across teams  |
| Auditor     | Contract review, NDA compliance      |
| Critic      | Detect timeline bottlenecks          |
""",
            category="Strategy", tags="summit,AI,launch,orchestrator",
            is_pinned=True, created_by="Namrata Srivastava", user_id=uid,
            created_at=dt(-12)))

        db.add(Note(note_id=gid("note"), title="Speaker Briefing Template",
            content="""# Speaker Briefing — AI Innovation Summit

## Session Format
- Keynote: 40 min + 10 min Q&A
- Workshop: 90 min hands-on
- Panel: 60 min moderated

## Tech Requirements Checklist
- [ ] Slide deck submitted 7 days before event
- [ ] Demo environment access provisioned
- [ ] AV check 2 hours before slot
- [ ] Bio & headshot for programme booklet

## Confirmed Speakers (Research Agent verified)
1. Dr. Aisha Patel — "Self-Correcting LLM Loops" (Keynote)
2. Marcus Chen — "RAG at Scale in Production" (Workshop)
3. Priya Mehta — "Multi-Agent Ethics & Guardrails" (Panel)

## ResearchAgent Note
Competitor summit (NeurIPS Satellite) scheduled same week —
CriticAgent flagged 18% attendance risk. Mitigation: hybrid stream.
""",
            category="Events", tags="summit,speakers,research",
            is_pinned=False, created_by="Namrata Srivastava", user_id=uid,
            created_at=dt(-8)))

        summit_tasks = [
            Task(task_id=gid("task"), title="Confirm venue — Taj Santacruz ballroom",
                 description="Negotiate AV package, catering for 500 pax, and breakout rooms. "
                             "Get written confirmation by Friday.",
                 priority="critical", status="completed",
                 due_date=dt(-3), completed_at=dt(-2), created_at=dt(-14),
                 assigned_to="Namrata Srivastava", subtasks=3, source="orchestrator", user_id=uid),
            Task(task_id=gid("task"), title="Finalise speaker list & send invites",
                 description="10 confirmed, 3 pending. ResearchAgent pulled LinkedIn bios. "
                             "Auditor checking NDAs.",
                 priority="high", status="completed",
                 due_date=dt(-1), completed_at=dt(-1), created_at=dt(-10),
                 assigned_to="Namrata Srivastava", subtasks=4, source="orchestrator", user_id=uid),
            Task(task_id=gid("task"), title="Design summit landing page",
                 description="Glassmorphism hero, speaker cards, agenda timeline. "
                             "WriterAgent drafted copy; awaiting design sign-off.",
                 priority="high", status="in_progress",
                 due_date=dt(2), created_at=dt(-6),
                 assigned_to="Namrata Srivastava", subtasks=5, source="orchestrator", user_id=uid),
            Task(task_id=gid("task"), title="Live demo script & rehearsal",
                 description="Script the 3-min live multi-agent demo on stage. "
                             "OrchestratorAgent will auto-generate the workflow; "
                             "need fallback slides if API is slow.",
                 priority="critical", status="in_progress",
                 due_date=dt(4), created_at=dt(-5),
                 assigned_to="Namrata Srivastava", subtasks=6, source="orchestrator", user_id=uid),
            Task(task_id=gid("task"), title="Media & press outreach",
                 description="Brief TechCrunch, The Gradient, Import AI newsletter. "
                             "NewsAgent monitoring for competitor announcements.",
                 priority="medium", status="open",
                 due_date=dt(6), created_at=dt(-3),
                 assigned_to="Namrata Srivastava", subtasks=3, source="orchestrator", user_id=uid),
            Task(task_id=gid("task"), title="Post-event debrief & NPS survey",
                 description="Collect 48-hour post-event feedback. "
                             "AuditorAgent will flag any PII in survey responses.",
                 priority="low", status="open",
                 due_date=dt(12), created_at=dt(-1),
                 assigned_to="Namrata Srivastava", subtasks=2, source="orchestrator", user_id=uid),
        ]
        db.add_all(summit_tasks)

        summit_events = [
            CalendarEvent(event_id=gid("event"), title="Summit Kickoff Sync",
                description="OrchestratorAgent pre-briefed all sub-agents. Assign workstreams.",
                start_time=dt(0, 9), end_time=dt(0, 10),
                location="Zoom — Link in invite", duration_minutes=60,
                status="scheduled", attendees=json.dumps(["Namrata","Marcus","Priya","Aisha"]),
                organizer="Namrata Srivastava", color="#7c4dff", user_id=uid),
            CalendarEvent(event_id=gid("event"), title="Speaker AV Rehearsal",
                description="Dry run with all speakers. ResearchAgent prepared Q&A brief.",
                start_time=dt(3, 14), end_time=dt(3, 16),
                location="Taj Santacruz — Hall B", duration_minutes=120,
                status="scheduled", attendees=json.dumps(["All Speakers","AV Team"]),
                organizer="Namrata Srivastava", color="#7c4dff", user_id=uid),
            CalendarEvent(event_id=gid("event"), title="AI Innovation Summit — Day 1",
                description="LIVE EVENT. OrchestratorAgent running real-time workflow on stage.",
                start_time=dt(7, 9), end_time=dt(7, 18),
                location="Taj Santacruz, Mumbai", duration_minutes=540,
                status="scheduled", attendees=json.dumps(["500+ Attendees"]),
                organizer="Namrata Srivastava", color="#1a73e8", user_id=uid),
            CalendarEvent(event_id=gid("event"), title="Sponsor Dinner",
                description="Private dinner with 3 enterprise sponsors. "
                             "SchedulerAgent blocked this slot 10 days in advance.",
                start_time=dt(7, 19), end_time=dt(7, 22),
                location="Taj Santacruz — Wasabi Restaurant", duration_minutes=180,
                status="scheduled", attendees=json.dumps(["Sponsors","Namrata","CTO"]),
                organizer="Namrata Srivastava", color="#34a853", user_id=uid),
        ]
        db.add_all(summit_events)

        # ══════════════════════════════════════════════════════════════════
        # PROJECT 2 — CLOUD INFRASTRUCTURE MIGRATION 2026
        # Showcases: CriticAgent detecting a scheduling conflict (meeting booked
        # before dependent tasks finish), ProactiveMonitorAgent alerting on
        # overdue items, DebateEngine resolving the cut-over strategy dispute.
        # ══════════════════════════════════════════════════════════════════
        print("🏗  Project 2: Cloud Infrastructure Migration 2026")

        db.add(Note(note_id=gid("note"), title="Migration Risk Register",
            content="""# Cloud Migration 2026 — Risk Register

## CriticAgent Analysis (auto-generated 2026-04-22)
The Critic flagged a HIGH-RISK scheduling conflict:
- "Migration Go-Live Review" is booked for Day+1
- "Provision Staging Environment" task is not due until Day+3
- **Confidence: 91%** — recommend pushing review by 48 hours OR fast-tracking staging

## Open Risks
| ID   | Risk                              | Owner    | Mitigation                |
|------|-----------------------------------|----------|---------------------------|
| R-01 | Staging not ready before review   | DevOps   | CriticAgent replan ✅     |
| R-02 | Legacy DB audit missed deadline   | DBA team | Escalated to ProactiveMonitor |
| R-03 | 12 microservices deploy in 1 day  | Platform | Parallelise with TaskAgent |
| R-04 | Rollback plan untested            | SRE      | Schedule chaos drill      |

## DebateEngine Ruling (2026-04-23)
Motion: "Big-bang cutover vs phased migration"
- Security Auditor: Phased (lower blast radius)
- Orchestrator: Big-bang (faster, cheaper)
- **Verdict**: Phased with 3 waves — adopted unanimously
""",
            category="Technical", tags="migration,cloud,risk,critic",
            is_pinned=True, created_by="Namrata Srivastava", user_id=uid,
            created_at=dt(-9)))

        db.add(Note(note_id=gid("note"), title="Runbook — GCP Cloud Run Migration",
            content="""# GCP Cloud Run Migration Runbook

## Pre-cutover Checklist (AuditorAgent verified)
- [x] IAM roles scoped to least privilege
- [x] Secrets migrated to Secret Manager
- [x] VPC Service Controls enabled
- [ ] Cloud Armor WAF rules applied (PENDING — AuditorAgent flagged)
- [ ] DLP scan on exported DB backup

## Wave 1 Services (non-critical)
- api-gateway, auth-service, notification-service

## Wave 2 Services (core)
- orchestrator-api, task-service, calendar-service

## Wave 3 Services (data-sensitive)
- user-service, billing-service, analytics-pipeline

## Rollback Trigger
If error rate > 2% for 5 minutes → automatic rollback via Cloud Deploy
""",
            category="Technical", tags="runbook,GCP,migration,auditor",
            is_pinned=False, created_by="Namrata Srivastava", user_id=uid,
            created_at=dt(-6)))

        dep_staging = gid("task")
        dep_deploy  = gid("task")
        migration_tasks = [
            Task(task_id=gid("task"), title="Audit legacy database — identify deprecated tables",
                 description="Scan all 47 tables. Flag PII columns for DLP. "
                             "OVERDUE — ProactiveMonitorAgent sent alert on 2026-04-26.",
                 priority="critical", status="in_progress",
                 due_date=dt(-2), created_at=dt(-14),
                 assigned_to="Namrata Srivastava", subtasks=4, source="manual", user_id=uid),
            Task(task_id=dep_staging, title="Provision GCP staging environment",
                 description="Spin up Cloud Run, AlloyDB, Redis, and Pub/Sub in us-central1. "
                             "Terraform plan reviewed by AuditorAgent.",
                 priority="high", status="in_progress",
                 due_date=dt(3), created_at=dt(-7),
                 assigned_to="Namrata Srivastava", subtasks=5, source="orchestrator", user_id=uid),
            Task(task_id=dep_deploy, title="Deploy 12 microservices to staging",
                 description="Wave 1: api-gateway, auth, notifications. "
                             "Wave 2: orchestrator, tasks, calendar. "
                             "CriticAgent detected this depends on staging being ready.",
                 priority="high", status="open",
                 due_date=dt(4), created_at=dt(-5), dependencies=dep_staging,
                 assigned_to="Namrata Srivastava", subtasks=7, source="orchestrator", user_id=uid),
            Task(task_id=gid("task"), title="Load test — 10k concurrent users",
                 description="Run Locust load test against staging. "
                             "Target: p99 latency < 200ms. AuditorAgent monitoring for data leaks.",
                 priority="high", status="open",
                 due_date=dt(6), created_at=dt(-3), dependencies=dep_deploy,
                 assigned_to="Namrata Srivastava", subtasks=3, source="orchestrator", user_id=uid),
            Task(task_id=gid("task"), title="Production cutover — Wave 1",
                 description="Phased cutover as decided by DebateEngine. "
                             "SchedulerAgent blocked 4-hour maintenance window at 2am IST.",
                 priority="critical", status="open",
                 due_date=dt(10), created_at=dt(-2),
                 assigned_to="Namrata Srivastava", subtasks=6, source="orchestrator", user_id=uid),
            Task(task_id=gid("task"), title="Post-migration monitoring — 72hr watch",
                 description="ProactiveMonitorAgent runs every 5 min. "
                             "Alert on: error rate, latency, DB connections, memory.",
                 priority="medium", status="open",
                 due_date=dt(14), created_at=dt(-1),
                 assigned_to="Namrata Srivastava", subtasks=2, source="orchestrator", user_id=uid),
        ]
        db.add_all(migration_tasks)

        migration_events = [
            CalendarEvent(event_id=gid("event"), title="⚠️ Migration Go-Live Review",
                description="CriticAgent WARNING: Staging tasks not yet complete. "
                             "This meeting was rescheduled from Day+1 after Critic flagged the conflict.",
                start_time=dt(5, 10), end_time=dt(5, 11, 30),
                location="War Room — Google Meet", duration_minutes=90,
                status="scheduled",
                attendees=json.dumps(["Namrata","DevOps Lead","SRE","DBA"]),
                organizer="Namrata Srivastava", color="#ea4335", user_id=uid),
            CalendarEvent(event_id=gid("event"), title="Chaos Engineering Drill",
                description="Simulate 3 failure scenarios. Rollback must complete in < 10 min.",
                start_time=dt(8, 14), end_time=dt(8, 16),
                location="Staging Environment (remote)", duration_minutes=120,
                status="scheduled",
                attendees=json.dumps(["SRE Team","Namrata"]),
                organizer="SRE Lead", color="#fbbc04", user_id=uid),
            CalendarEvent(event_id=gid("event"), title="Production Cutover — Wave 1 (2am IST)",
                description="SchedulerAgent auto-booked this maintenance window. "
                             "All on-call engineers notified via PagerDuty.",
                start_time=dt(10, -3), end_time=dt(10, 1),  # 2am IST = ~8:30pm UTC prev day
                location="Remote — all engineers on standby", duration_minutes=240,
                status="scheduled",
                attendees=json.dumps(["On-Call Team","Namrata","CTO"]),
                organizer="Namrata Srivastava", color="#ea4335", user_id=uid),
        ]
        db.add_all(migration_events)

        # ══════════════════════════════════════════════════════════════════
        # PROJECT 3 — AGENTIC R&D LAB
        # Showcases: ResearchAgent pulling arXiv papers, NewsAgent monitoring
        # competitive landscape, VedaLibrarian tracking reading list,
        # KnowledgeGraph connecting concepts.
        # ══════════════════════════════════════════════════════════════════
        print("🏗  Project 3: Agentic R&D Lab")

        db.add(Note(note_id=gid("note"), title="ResearchAgent — Weekly Digest #12",
            content="""# Research Digest — Week of April 28, 2026
*Auto-generated by ResearchAgent from arXiv cs.AI + cs.LG*

## Top Papers This Week

### 1. "Critic-Guided Autonomous Replanning in Multi-Agent Systems"
**Authors**: Zhang et al., Google DeepMind
**Key Finding**: Critic agents that use confidence-weighted scoring reduce
wasted compute by 34% vs greedy re-planners.
**Orchestra Relevance**: Directly validates our CriticAgent design ✅

### 2. "RAG-Critic: Retrieval Augmented Self-Correction"
**Authors**: Patel et al., Stanford HAI
**Key Finding**: Combining retrieval with critic loops achieves GPT-4-level
accuracy on 3x smaller models.
**Orchestra Relevance**: Potential upgrade path for LibrarianAgent

### 3. "PII Leakage in Multi-Agent Pipelines: A Systematic Study"
**Authors**: Mehta et al., MIT CSAIL
**Key Finding**: 23% of multi-agent systems leak user PII through tool call logs.
**Orchestra Relevance**: AuditorAgent addresses exactly this gap ✅

## NewsAgent Alerts
- OpenAI announced "Assistants API v3" — adds multi-agent orchestration primitives
- Anthropic released Claude 4 Opus — benchmark on our eval suite pending
- Google released Gemini 2.5 Flash — faster than Pro, relevant for TaskAgent

## Recommended Reading (added to Veda Library)
- "Designing Multi-Agent Systems" — Wooldridge (Chapter 7: Coordination)
- "The Alignment Problem" — Brian Christian (Ethics context for AuditorAgent)
""",
            category="Research", tags="arXiv,LLM,agents,research-agent,digest",
            is_pinned=True, created_by="ResearchAgent", user_id=uid,
            created_at=dt(-1)))

        db.add(Note(note_id=gid("note"), title="Competitive Intelligence — Agent Platforms",
            content="""# Competitive Intel — AI Agent Platforms
*NewsAgent continuous monitoring — updated 2026-04-27*

## Direct Competitors
| Platform      | Strengths                    | Gap vs Orchestra            |
|---------------|------------------------------|-----------------------------|
| AutoGen       | Multi-agent graphs           | No Critic/self-correction   |
| CrewAI        | Role-based agents            | No live scheduling layer    |
| LangGraph     | Stateful flows               | No audit/PII scanning       |
| Vertex AI AG  | GCP-native                   | No debate engine            |

## Orchestra Differentiators (validated by ResearchAgent)
1. **CriticAgent** — only platform with confidence-weighted replanning
2. **DebateEngine** — multi-agent adversarial reasoning before decisions
3. **AuditorAgent** — real-time PII detection in tool call outputs
4. **ProactiveMonitor** — background anomaly detection, not just reactive

## Recommended Demo Script for Hackathon
- Goal: "Plan our cloud migration cutover"
- Watch: Critic detects scheduling conflict, Debate resolves strategy,
  Auditor flags PII in runbook, Monitor alerts on overdue tasks
- Runtime: ~2.5 minutes live
""",
            category="Research", tags="competitive,intelligence,news-agent",
            is_pinned=False, created_by="NewsAgent", user_id=uid,
            created_at=dt(-2)))

        db.add(Note(note_id=gid("note"), title="Experiment Log — Self-Correcting Loops",
            content="""# Experiment Log — Self-Correcting Agent Loops

## Hypothesis
A CriticAgent with access to task history and calendar context will reduce
re-work by > 25% compared to a vanilla planner.

## Experiment Design
- Control: Standard OrchestratorAgent (no Critic)
- Treatment: Orchestra full stack (Critic + Auditor + Monitor)
- Metric: Tasks completed on-time / total tasks over 30 days

## Results (Week 3)
| Metric            | Control | Treatment | Δ      |
|-------------------|---------|-----------|--------|
| On-time rate      | 61%     | 84%       | +23pp  |
| Replans needed    | 12      | 3         | -75%   |
| PII incidents     | 4       | 0         | -100%  |
| User satisfaction | 3.2/5   | 4.6/5     | +44%   |

## Conclusion
**Hypothesis validated.** Full agent stack outperforms control on all metrics.
CriticAgent alone accounts for 18pp of the 23pp improvement.

## Next Steps (TaskAgent tracked)
- [ ] Expand to 100-task benchmark
- [ ] Test with adversarial goals (ambiguous, contradictory)
- [ ] Submit to NeurIPS workshop
""",
            category="Research", tags="experiment,critic,metrics",
            is_pinned=False, created_by="Namrata Srivastava", user_id=uid,
            created_at=dt(-4)))

        rd_tasks = [
            Task(task_id=gid("task"), title="Synthesise arXiv papers on autonomous replanning",
                 description="ResearchAgent queued 8 papers. Read, annotate, extract key findings "
                             "for the Orchestra technical report.",
                 priority="high", status="in_progress",
                 due_date=dt(3), created_at=dt(-7),
                 assigned_to="Namrata Srivastava", subtasks=3, source="orchestrator", user_id=uid),
            Task(task_id=gid("task"), title="Benchmark CriticAgent vs AutoGen Critic",
                 description="Run 50-task evaluation. NewsAgent will monitor if AutoGen publishes "
                             "benchmark results during our test window.",
                 priority="high", status="open",
                 due_date=dt(8), created_at=dt(-4),
                 assigned_to="Namrata Srivastava", subtasks=5, source="orchestrator", user_id=uid),
            Task(task_id=gid("task"), title="Write technical blog post — Orchestra architecture",
                 description="WriterAgent drafted outline. ResearchAgent cross-referenced with "
                             "3 published surveys. Target: 2500 words.",
                 priority="medium", status="in_progress",
                 due_date=dt(5), created_at=dt(-5),
                 assigned_to="Namrata Srivastava", subtasks=4, source="orchestrator", user_id=uid),
            Task(task_id=gid("task"), title="Submit to NeurIPS 2026 Agents Workshop",
                 description="Deadline: May 15. AuditorAgent will check paper for "
                             "double-blind compliance and author info leaks.",
                 priority="critical", status="open",
                 due_date=dt(17), created_at=dt(-2),
                 assigned_to="Namrata Srivastava", subtasks=6, source="manual", user_id=uid),
            Task(task_id=gid("task"), title="Veda Library curation — add 10 foundational papers",
                 description="LibrarianAgent will index each paper, extract key concepts, "
                             "and link to KnowledgeGraph nodes.",
                 priority="low", status="open",
                 due_date=dt(10), created_at=dt(-1),
                 assigned_to="Namrata Srivastava", subtasks=2, source="manual", user_id=uid),
        ]
        db.add_all(rd_tasks)

        rd_events = [
            CalendarEvent(event_id=gid("event"), title="Research Sprint Planning",
                description="SchedulerAgent proposed this slot based on calendar availability "
                             "and task deadlines. OrchestratorAgent pre-loaded research context.",
                start_time=dt(1, 10), end_time=dt(1, 11),
                location="Zoom", duration_minutes=60,
                status="scheduled",
                attendees=json.dumps(["Namrata","Research Team"]),
                organizer="Namrata Srivastava", color="#34a853", user_id=uid),
            CalendarEvent(event_id=gid("event"), title="NeurIPS Paper Review Session",
                description="Internal review before submission. AuditorAgent will run "
                             "blind compliance check during the meeting.",
                start_time=dt(14, 14), end_time=dt(14, 16),
                location="Virtual", duration_minutes=120,
                status="scheduled",
                attendees=json.dumps(["Namrata","Co-authors"]),
                organizer="Namrata Srivastava", color="#34a853", user_id=uid),
        ]
        db.add_all(rd_events)

        # Veda Library books
        books = [
            Book(book_id=gid("book"), title="Designing Multi-Agent Systems",
                 author="Michael Wooldridge", status="in-progress",
                 current_page=187, total_pages=312,
                 created_at=dt(-20), updated_at=dt(-1), user_id=uid),
            Book(book_id=gid("book"), title="The Alignment Problem",
                 author="Brian Christian", status="in-progress",
                 current_page=94, total_pages=368,
                 created_at=dt(-15), updated_at=dt(-3), user_id=uid),
            Book(book_id=gid("book"), title="Artificial Intelligence: A Modern Approach",
                 author="Russell & Norvig", status="completed",
                 current_page=1132, total_pages=1132,
                 created_at=dt(-60), updated_at=dt(-30),
                 finished_at=dt(-30), user_id=uid),
            Book(book_id=gid("book"), title="Building LLM Applications",
                 author="Valentina Alto", status="to-read",
                 current_page=0, total_pages=280,
                 created_at=dt(-5), updated_at=dt(-5), user_id=uid),
            Book(book_id=gid("book"), title="Prompt Engineering for Developers",
                 author="Isa Fulford & Andrew Ng", status="completed",
                 current_page=95, total_pages=95,
                 created_at=dt(-45), updated_at=dt(-40),
                 finished_at=dt(-40), user_id=uid),
        ]
        db.add_all(books)

        # ══════════════════════════════════════════════════════════════════
        # PROJECT 4 — SECURITY & COMPLIANCE Q2
        # Showcases: AuditorAgent PII detection, DebateEngine resolving
        # security vs velocity tradeoffs, ParamMitra weekly coaching,
        # ProactiveMonitor escalation flow.
        # ══════════════════════════════════════════════════════════════════
        print("🏗  Project 4: Security & Compliance Q2")

        db.add(Note(note_id=gid("note"), title="AuditorAgent — Q2 Security Findings",
            content="""# AuditorAgent Security Report — Q2 2026
*Generated: 2026-04-27 | Confidence: 94%*

## Executive Summary
3 HIGH severity findings, 7 MEDIUM, 12 LOW across the Orchestra codebase
and operational data. All HIGH findings have mitigation tasks created.

## HIGH Severity Findings

### H-01: PII in Workflow Logs
- **Location**: workflow_state.reasoning_json
- **Finding**: Employee names and emails found in 14 workflow traces
- **Risk**: GDPR Art. 17 non-compliance (right to erasure)
- **Mitigation**: TaskAgent created "Implement log anonymisation" task

### H-02: Unencrypted Export — Compensation Data
- **Location**: /api/export/compensation
- **Finding**: CSV export contains salary + SSN fields without DLP masking
- **Risk**: Data breach liability, regulatory fine
- **Mitigation**: Task blocked pending DebateEngine ruling on masking approach

### H-03: Over-permissioned Service Account
- **Location**: GCP IAM — orchestra-prod@...
- **Finding**: roles/owner instead of roles/run.invoker
- **Risk**: Privilege escalation vector
- **Mitigation**: DevOps ticket created, ETA Day+2

## DebateEngine Session — Compensation Export (2026-04-26)
**Motion**: "Should the export be blocked entirely or masked and released?"
- AuditorAgent: BLOCK (zero-risk)
- OrchestratorAgent: MASK-AND-RELEASE (HR needs data)
- **Verdict**: Mask SSN + salary bands, release with DLP watermark — 3:1 vote
""",
            category="Security", tags="audit,PII,compliance,GDPR",
            is_pinned=True, created_by="AuditorAgent", user_id=uid,
            created_at=dt(-1)))

        db.add(Note(note_id=gid("note"), title="Param Mitra — Weekly Coaching (Apr 28)",
            content="""# Param Mitra Weekly Coaching
*Your AI Guru — Personalised Productivity Insight*

## Your Week at a Glance
- Tasks completed: 4 / 11 (36% completion rate)
- Calendar load: 18 hours of meetings (HIGH — target < 12)
- Overdue items: 2 (Audit Legacy DB, missing from last sprint)
- Vibe Score: **72%** — "Stretched but focused"

## Observations

### 🔴 Bottleneck: Meeting Overload
You have 3 back-to-back meetings every morning this week.
CriticAgent detected this blocks your deep-work time for the R&D tasks.

**Param Mitra Recommendation**: Protect 9am–11am as focus time.
Ask SchedulerAgent to decline low-priority meeting invites automatically.

### 🟡 Risk: NeurIPS Deadline Creep
The submission deadline is Day+17 but writing tasks are only 40% done.
At current velocity, you'll need 4 focused writing sessions.

**Recommendation**: Block 3-hour "Writing Sprint" slots on Days 2, 5, 9, 12.
OrchestratorAgent can pre-load research context before each session.

### 🟢 Win: Cloud Migration Proactive Risk Management
You caught the Go-Live Review scheduling conflict 6 days early — thanks to
CriticAgent. This saved an estimated 14 hours of rework.

## This Week's Focus
1. Protect morning focus time (SchedulerAgent will help)
2. One cloud migration task per day — don't let staging slip further
3. Start NeurIPS draft — even 500 words per session compounds fast

*"Small consistent actions outperform heroic last-minute efforts." — Param Mitra*
""",
            category="Coaching", tags="param-mitra,productivity,guru,coaching",
            is_pinned=False, created_by="ParamMitraAgent", user_id=uid,
            created_at=dt(0)))

        security_tasks = [
            Task(task_id=gid("task"), title="Export employee compensation data — masked",
                 description="DebateEngine ruled: mask SSN + salary bands before export. "
                             "AuditorAgent must sign off before file leaves the system. "
                             "DLP watermark required.",
                 priority="critical", status="in_progress",
                 due_date=dt(1), created_at=dt(-3),
                 assigned_to="Namrata Srivastava", subtasks=4, source="orchestrator", user_id=uid),
            Task(task_id=gid("task"), title="Fix over-permissioned GCP service account",
                 description="AuditorAgent H-03: Change roles/owner → roles/run.invoker. "
                             "Also audit all service accounts — 6 others may be affected.",
                 priority="critical", status="open",
                 due_date=dt(2), created_at=dt(-1),
                 assigned_to="Namrata Srivastava", subtasks=3, source="auditor", user_id=uid),
            Task(task_id=gid("task"), title="Implement workflow log anonymisation",
                 description="AuditorAgent H-01: Strip PII from reasoning_json before persistence. "
                             "Use Presidio or Cloud DLP. Test with 50 historical workflows.",
                 priority="high", status="open",
                 due_date=dt(5), created_at=dt(-1),
                 assigned_to="Namrata Srivastava", subtasks=5, source="auditor", user_id=uid),
            Task(task_id=gid("task"), title="Quarterly GDPR audit — data inventory",
                 description="Map all personal data flows. AuditorAgent will cross-check "
                             "against 14 GDPR articles. Generate compliance report.",
                 priority="high", status="open",
                 due_date=dt(9), created_at=dt(-2),
                 assigned_to="Namrata Srivastava", subtasks=6, source="manual", user_id=uid),
            Task(task_id=gid("task"), title="Employee performance review — Q1 self-assessment",
                 description="Param Mitra pre-filled template with data from task history, "
                             "meeting load, and vibe scores. Review and personalise.",
                 priority="medium", status="open",
                 due_date=dt(4), created_at=dt(-4),
                 assigned_to="Namrata Srivastava", subtasks=2, source="manual", user_id=uid),
            Task(task_id=gid("task"), title="Security training — mandatory GDPR module",
                 description="SchedulerAgent auto-enrolled team in LMS module after AuditorAgent "
                             "flagged the PII findings. Completion deadline: Day+4.",
                 priority="medium", status="completed",
                 due_date=dt(-1), completed_at=dt(-1), created_at=dt(-8),
                 assigned_to="Namrata Srivastava", subtasks=1, source="auditor", user_id=uid),
        ]
        db.add_all(security_tasks)

        security_events = [
            CalendarEvent(event_id=gid("event"), title="1:1 with Engineering Director",
                description="Param Mitra pre-brief: Discuss career growth, project bottlenecks, "
                             "and the R&D benchmark results. Agenda sent 24h in advance.",
                start_time=dt(2, 11), end_time=dt(2, 12),
                location="Director's Office / Zoom", duration_minutes=60,
                status="scheduled",
                attendees=json.dumps(["Namrata","Engineering Director"]),
                organizer="Engineering Director", color="#8b5cf6", user_id=uid),
            CalendarEvent(event_id=gid("event"), title="DebateEngine Session — Export Strategy",
                description="Agents: AuditorAgent vs OrchestratorAgent. "
                             "Topic: Block or mask-and-release compensation export? "
                             "Verdict: Mask + DLP watermark (recorded in notes).",
                start_time=dt(-1, 14), end_time=dt(-1, 15),
                location="Virtual — auto-convened by DebateEngine", duration_minutes=60,
                status="completed",
                attendees=json.dumps(["AuditorAgent","OrchestratorAgent","Namrata"]),
                organizer="DebateEngine", color="#ea4335", user_id=uid),
            CalendarEvent(event_id=gid("event"), title="GDPR Compliance Review",
                description="External DPO review of AuditorAgent findings. "
                             "SchedulerAgent sent encrypted calendar invite to DPO.",
                start_time=dt(9, 14), end_time=dt(9, 15, 30),
                location="Legal Dept / Zoom", duration_minutes=90,
                status="scheduled",
                attendees=json.dumps(["Namrata","DPO","Legal Counsel"]),
                organizer="Namrata Srivastava", color="#8b5cf6", user_id=uid),
            CalendarEvent(event_id=gid("event"), title="Param Mitra Focus Block — NeurIPS Writing",
                description="SchedulerAgent blocked this as a focus session based on "
                             "Param Mitra's recommendation. No meetings allowed.",
                start_time=dt(2, 9), end_time=dt(2, 12),
                location="No interruptions", duration_minutes=180,
                status="scheduled",
                attendees=json.dumps(["Namrata"]),
                organizer="ParamMitraAgent", color="#34a853", user_id=uid),
        ]
        db.add_all(security_events)

        # ══════════════════════════════════════════════════════════════════
        # WORKFLOW HISTORY — shows the Orchestrator Run History panel
        # ══════════════════════════════════════════════════════════════════
        print("📋 Seeding workflow history...")

        workflows = [
            WorkflowHistory(workflow_id=gid("wf"),
                goal="Plan the AI Innovation Summit — assign tasks, block calendar, brief speakers",
                priority="high", status="completed", steps_count=7, tasks_created=6,
                events_created=4, source="text", user_id=uid,
                created_at=dt(-12), completed_at=dt(-12)),
            WorkflowHistory(workflow_id=gid("wf"),
                goal="Detect scheduling conflicts in Cloud Migration project and replan",
                priority="critical", status="completed", steps_count=5, tasks_created=2,
                events_created=1, source="text", user_id=uid,
                created_at=dt(-5), completed_at=dt(-5)),
            WorkflowHistory(workflow_id=gid("wf"),
                goal="Research latest papers on autonomous agent replanning for NeurIPS submission",
                priority="medium", status="completed", steps_count=4, tasks_created=2,
                events_created=0, source="text", user_id=uid,
                created_at=dt(-4), completed_at=dt(-4)),
            WorkflowHistory(workflow_id=gid("wf"),
                goal="Run security audit on compensation data export and initiate debate session",
                priority="critical", status="completed", steps_count=6, tasks_created=3,
                events_created=1, source="text", user_id=uid,
                created_at=dt(-1), completed_at=dt(-1)),
            WorkflowHistory(workflow_id=gid("wf"),
                goal="Generate weekly Param Mitra coaching report and block focus time",
                priority="medium", status="completed", steps_count=3, tasks_created=0,
                events_created=2, source="text", user_id=uid,
                created_at=dt(0), completed_at=dt(0)),
        ]
        db.add_all(workflows)

        # ══════════════════════════════════════════════════════════════════
        # CRITIC DECISIONS — shows the Critic's autonomous replan panel
        # ══════════════════════════════════════════════════════════════════
        print("🔍 Seeding critic decisions...")

        critic_decisions = [
            CriticDecision(
                workflow_id=workflows[1].workflow_id,
                reasoning="Migration Go-Live Review is scheduled for Day+1 but Provision Staging "
                          "task is not due until Day+3. If staging slips even 1 day (67% historical "
                          "probability), the review meeting will have no results to review. "
                          "Recommend: push review to Day+5 OR fast-track staging by parallelising "
                          "with Deploy Microservices task.",
                efficiency_gain=0.34, confidence_score=0.91,
                original_plan_json=json.dumps({"review_date": "Day+1", "staging_date": "Day+3"}),
                revised_plan_json=json.dumps({"review_date": "Day+5", "staging_date": "Day+3",
                                              "rationale": "Align review after staging is provably ready"}),
                accepted=True, replanned_at=dt(-5)),
            CriticDecision(
                workflow_id=workflows[0].workflow_id,
                reasoning="Summit landing page task and live demo script task are assigned to the "
                          "same person with overlapping deadlines. Both require 3+ hours of focused "
                          "work. Recommend splitting: assign page design to WriterAgent pipeline, "
                          "keep demo script with Namrata.",
                efficiency_gain=0.22, confidence_score=0.84,
                original_plan_json=json.dumps({"page_owner": "Namrata", "demo_owner": "Namrata"}),
                revised_plan_json=json.dumps({"page_owner": "WriterAgent", "demo_owner": "Namrata",
                                              "rationale": "Parallel execution saves 2 days"}),
                accepted=True, replanned_at=dt(-8)),
            CriticDecision(
                workflow_id=workflows[3].workflow_id,
                reasoning="Compensation export task was created before DebateEngine ruling. "
                          "Original task had no DLP masking requirement. Post-debate, task needs "
                          "3 additional subtasks: (1) apply Presidio masking, (2) DLP watermark, "
                          "(3) AuditorAgent sign-off gate. Efficiency loss accepted for compliance.",
                efficiency_gain=-0.15, confidence_score=0.97,
                original_plan_json=json.dumps({"subtasks": 1, "dlp": False}),
                revised_plan_json=json.dumps({"subtasks": 4, "dlp": True, "auditor_gate": True}),
                accepted=True, replanned_at=dt(-1)),
        ]
        db.add_all(critic_decisions)

        db.commit()

        print(f"""
{'='*60}
✅ ORCHESTRA DATABASE SEEDED SUCCESSFULLY
{'='*60}

👤 Login Credentials
   Email:    srivnamrata@gmail.com
   Password: Atharv19@

📊 Data Created
   Project 1 — AI Innovation Summit
     • 6 tasks  |  4 events  |  2 notes

   Project 2 — Cloud Infrastructure Migration
     • 6 tasks  |  3 events  |  2 notes
     • 3 Critic decisions with reasoning

   Project 3 — Agentic R&D Lab
     • 5 tasks  |  2 events  |  3 notes
     • 5 books in Veda Library

   Project 4 — Security & Compliance Q2
     • 6 tasks  |  4 events  |  2 notes

   Workflow History: 5 runs
   Critic Decisions: 3 autonomous replans

🎯 Hackathon Demo Flow
   1. Onboarding  → show Namrata's personalised dashboard
   2. Intelligence → Fetch Latest (news + research + tasks)
   3. Summit wf   → run "Plan AI Innovation Summit" goal
   4. Critic       → show Migration conflict + replan
   5. Auditor      → show PII finding on compensation task
   6. Debate       → replay Export Strategy debate
   7. Param Mitra  → show weekly coaching with vibe score
   8. Veda         → show reading list + progress
   9. Agent Trace  → show full reasoning timeline
{'='*60}
""")

    except Exception as e:
        db.rollback()
        import traceback; traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
