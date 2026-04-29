"""
Param Mitra Agent — The Supreme Friend & Guru
=============================================
A high-performance life coach that observes all data streams (Git, Email, Tasks, Meetings)
to identify gaps in code quality, communication, and human potential.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from backend.services.llm_utils import parse_llm_json

logger = logging.getLogger(__name__)

class ParamMitraAgent:
    def __init__(self, llm_service, github_service=None, email_service=None, task_service=None, pubsub_service=None):
        self.llm = llm_service
        self.github = github_service
        self.email = email_service
        self.tasks = task_service
        self.pubsub = pubsub_service

    @staticmethod
    def _clamp_score(value: Any, default: int = 75) -> int:
        try:
            return max(0, min(100, int(round(float(value)))))
        except Exception:
            return default

    @staticmethod
    def _first_non_empty(*values: Any, default: str = "") -> str:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return default

    @staticmethod
    def _first_numeric(*values: Any, default: float = 75.0) -> float:
        for value in values:
            if value is None:
                continue
            try:
                return float(value)
            except Exception:
                continue
        return default

    def _normalize_section(
        self,
        section: Any,
        *,
        default_assessment: str,
        default_insight: str,
        training_topic: Optional[str] = None,
        training_why: Optional[str] = None,
        training_link_hint: Optional[str] = None,
        default_micro_habit: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not isinstance(section, dict):
            section = {}

        assessment = self._first_non_empty(section.get("assessment"), default=default_assessment)
        insight = self._first_non_empty(section.get("insight"), default=default_insight)
        micro_habit = self._first_non_empty(section.get("micro_habit"), default=default_micro_habit)
        training = section.get("training")

        if isinstance(training, dict):
            topic = self._first_non_empty(training.get("topic"), default=training_topic or "")
            why = self._first_non_empty(training.get("why"), default=training_why or "")
            link_hint = self._first_non_empty(training.get("link_hint"), default=training_link_hint or "")
            training = {
                "topic": topic,
                "why": why,
                "link_hint": link_hint,
            }
        elif assessment == "needs_improvement" and training_topic:
            training = {
                "topic": training_topic,
                "why": training_why or "A small investment here would remove a recurring bottleneck.",
                "link_hint": training_link_hint or "Coursera / YouTube / Book",
            }
        else:
            training = None

        return {
            "assessment": assessment,
            "insight": insight,
            "micro_habit": micro_habit,
            "training": training,
        }

    def _normalize_audit(self, audit: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(audit, dict):
            audit = {}

        scores = audit.get("scores") if isinstance(audit.get("scores"), dict) else {}
        bottlenecks = audit.get("bottlenecks") if isinstance(audit.get("bottlenecks"), list) else []

        git_summary = self._first_non_empty(context.get("git_summary"), default="No recent commits.")
        email_summary = self._first_non_empty(context.get("email_summary"), default="No recent emails.")
        task_summary = self._first_non_empty(context.get("task_status"), default="No task data.")
        reading_summary = self._first_non_empty(context.get("goals"), default="No goals set.")

        summary = self._first_non_empty(
            audit.get("summary"),
            audit.get("guru_message"),
            audit.get("response"),
            default="Weekly insights are ready."
        )

        vibe_score = self._clamp_score(
            self._first_numeric(
                audit.get("vibe_score"),
                scores.get("overall"),
                scores.get("balance"),
                scores.get("code_mastery"),
                scores.get("communication"),
                scores.get("efficiency"),
                default=75,
            ),
            default=75,
        )

        code_section = audit.get("code") if isinstance(audit.get("code"), dict) else {}
        communication_section = audit.get("communication") if isinstance(audit.get("communication"), dict) else {}
        efficiency_section = audit.get("efficiency") if isinstance(audit.get("efficiency"), dict) else {}
        strategic_alignment = audit.get("strategic_alignment") if isinstance(audit.get("strategic_alignment"), dict) else {}
        wellness_section = audit.get("wellness") if isinstance(audit.get("wellness"), dict) else {}

        code_insight = self._first_non_empty(
            code_section.get("insight"),
            audit.get("code_insight"),
            default=f"Code activity looks steady. {git_summary}",
        )
        communication_insight = self._first_non_empty(
            communication_section.get("insight"),
            audit.get("communication_insight"),
            default=f"Communication looks consistent. {email_summary}",
        )
        efficiency_insight = self._first_non_empty(
            efficiency_section.get("insight"),
            audit.get("efficiency_insight"),
            default=f"Task progress is tracking against your goals. {task_summary}",
        )

        code_score = self._clamp_score(self._first_numeric(scores.get("code_mastery"), vibe_score, default=vibe_score), default=vibe_score)
        communication_score = self._clamp_score(self._first_numeric(scores.get("communication"), vibe_score, default=vibe_score), default=vibe_score)
        efficiency_score = self._clamp_score(self._first_numeric(scores.get("efficiency"), vibe_score, default=vibe_score), default=vibe_score)
        alignment_score = self._clamp_score(
            self._first_numeric(
                strategic_alignment.get("score"),
                scores.get("alignment"),
                min(100, max(0, int(round((vibe_score + efficiency_score) / 2)))),
                default=vibe_score,
            ),
            default=vibe_score,
        )

        if not strategic_alignment:
            strategic_alignment = {
                "score": alignment_score,
                "assessment": self._first_non_empty(
                    audit.get("alignment_assessment"),
                    default="Your work is moving in the right direction.",
                ),
                "suggestion": self._first_non_empty(
                    audit.get("alignment_suggestion"),
                    default="Keep focusing on the tasks that move the long-term goal forward.",
                ),
            }
        else:
            strategic_alignment = {
                "score": alignment_score,
                "assessment": self._first_non_empty(
                    strategic_alignment.get("assessment"),
                    default="Your work is moving in the right direction.",
                ),
                "suggestion": self._first_non_empty(
                    strategic_alignment.get("suggestion"),
                    default="Keep focusing on the tasks that move the long-term goal forward.",
                ),
            }

        if not audit.get("code"):
            audit_code_default = "needs_improvement" if code_score < 65 else ("good" if code_score < 85 else "great")
            code_section = self._normalize_section(
                code_section,
                default_assessment=audit_code_default,
                default_insight=code_insight,
                training_topic="Clean code review habits",
                training_why="Tighter review loops can improve code quality and reduce friction.",
            )
        else:
            code_section = self._normalize_section(
                code_section,
                default_assessment="good",
                default_insight=code_insight,
            )

        if not audit.get("communication"):
            comm_default = "needs_improvement" if communication_score < 65 else ("good" if communication_score < 85 else "great")
            communication_section = self._normalize_section(
                communication_section,
                default_assessment=comm_default,
                default_insight=communication_insight,
                training_topic="Clearer written communication",
                training_why="Sharpening tone and clarity helps the team move faster.",
                training_link_hint="Coursera / YouTube / Book",
            )
        else:
            communication_section = self._normalize_section(
                communication_section,
                default_assessment="good",
                default_insight=communication_insight,
            )

        if not audit.get("efficiency"):
            eff_default = "needs_improvement" if efficiency_score < 65 else ("good" if efficiency_score < 85 else "great")
            efficiency_section = self._normalize_section(
                efficiency_section,
                default_assessment=eff_default,
                default_insight=efficiency_insight,
                training_topic="Weekly planning and prioritization",
                training_why="A better prioritization loop can reduce task drift and context switching.",
                training_link_hint="Coursera / YouTube / Book",
            )
        else:
            efficiency_section = self._normalize_section(
                efficiency_section,
                default_assessment="good",
                default_insight=efficiency_insight,
            )

        burnout_risk = self._first_non_empty(wellness_section.get("burnout_risk"), default="low")
        wellness_insight = self._first_non_empty(wellness_section.get("insight"), default="Pacing looks healthy.")
        wellness_habit = self._first_non_empty(wellness_section.get("micro_habit"), default="Drink water and take a 5-minute screen break.")
        
        wellness_section_norm = {
            "burnout_risk": burnout_risk,
            "insight": wellness_insight,
            "micro_habit": wellness_habit,
        }

        cheer = self._first_non_empty(
            audit.get("cheer"),
            default="Keep going. The week is still yours."
        )

        return {
            "summary": summary,
            "vibe_score": vibe_score,
            "code": code_section,
            "communication": communication_section,
            "strategic_alignment": strategic_alignment,
            "efficiency": efficiency_section,
            "wellness": wellness_section_norm,
            "cheer": cheer,
            "raw_context": {
                "git_summary": git_summary,
                "email_summary": email_summary,
                "task_status": task_summary,
                "goals": reading_summary,
            },
        }

    async def generate_audit(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates weekly insights: specific feedback on code, communication, efficiency.
        Ingests auditor risk levels and critic replans to assess 'Spiritual Alignment'.
        """
        prompt = f"""You are Param Mitra — a wise, warm, honest Guru who is also a best friend.
Generate a weekly insight report based on this data:

Historical Context (Last week): {context.get('historical_context', 'No past context available.')}
Strategic Risks (from Auditor): {context.get('auditor_risks', 'No risks flagged.')}
User Long-term Goals: {context.get('user_goals', 'No goals set.')}

Code / Git Activity: {context.get('git_summary', 'No recent commits.')}
Email / Communication: {context.get('email_summary', 'No recent emails.')}
Tasks & Efficiency: {context.get('task_status', 'No task data.')}
Reading & Goals: {context.get('goals', 'No goals set.')}

Rules:
- Be specific. Reference actual data (PR titles, email threads, task names) when possible.
- Be encouraging first. Celebrate genuine wins.
- For communication, specifically look for tone. If someone was harsh or transactional, quote an instance.
- Assess 'Strategic Alignment': Are current tasks actually moving the needle on the User's Long-term Goals?
- Wellness & Burnout: Look at timestamps/volume. Are they working crazy hours? Call it out.
- Micro-Habits: Give one specific, 2-minute actionable habit per section instead of just generic advice.
- Only suggest a training if there is a REAL gap. If things look good, say so warmly.
- Cheer: end with a short personal motivational line (not generic).

Return ONLY valid JSON, no markdown:
{{
  "summary": "One sentence overall assessment of the week.",
  "vibe_score": number (0-100, where 100 is perfectly balanced),
  "code": {{
    "assessment": "great" | "good" | "needs_improvement",
    "insight": "Specific observation about code quality, commit messages, PR activity this week.",
    "micro_habit": "A tiny 2-minute habit to improve this.",
    "training": null
  }},
  "communication": {{
    "assessment": "great" | "good" | "needs_improvement",
    "insight": "Specific observation about tone.",
    "micro_habit": "A tiny 2-minute habit to improve this.",
    "training": null
  }},
  "strategic_alignment": {{
    "score": number (0-100),
    "assessment": "How well the weekly work aligns with the North Star goals.",
    "suggestion": "One sentence on how to realign."
  }},
  "efficiency": {{
    "assessment": "great" | "good" | "needs_improvement",
    "insight": "Specific observation about task completion, priorities, focus.",
    "micro_habit": "A tiny 2-minute habit to improve this.",
    "training": null
  }},
  "wellness": {{
    "burnout_risk": "high" | "medium" | "low",
    "insight": "Observation on pacing and work hours.",
    "micro_habit": "A habit for well-being."
  }},
  "cheer": "Short personal motivational line."
}}

If assessment is 'needs_improvement', populate training as:
{{"topic": "Course or skill name", "why": "One sentence reason", "link_hint": "Coursera / YouTube / Book"}}
"""
        try:
            raw = await self.llm.call(prompt)
            return self._normalize_audit(parse_llm_json(raw), context)
        except Exception as e:
            logger.error(f"Param Mitra error: {e}")
            fallback = {
                "summary": "You are moving, but the work would benefit from a sharper weekly focus.",
                "vibe_score": 72,
                "code": {
                    "assessment": "good",
                    "insight": "Code quality looks steady; keep tightening feedback loops and documentation.",
                    "training": None,
                },
                "communication": {
                    "assessment": "needs_improvement",
                    "insight": "Communication could be warmer and more explicit in a few places.",
                    "training": {
                        "topic": "Clearer written communication",
                        "why": "More context and tone control will reduce back-and-forth.",
                        "link_hint": "Coursera / YouTube / Book",
                    },
                },
                "strategic_alignment": {
                    "score": 68,
                    "assessment": "Your current activity is useful, but not all of it is directly advancing the North Star.",
                    "suggestion": "Trim one low-value task and spend that time on the highest-leverage item.",
                },
                "efficiency": {
                    "assessment": "needs_improvement",
                    "insight": "A few tasks are moving, but the week needs a stronger finish line.",
                    "micro_habit": "End your day by writing down 1 top priority for tomorrow.",
                    "training": {
                        "topic": "Weekly prioritization",
                        "why": "A tighter planning loop can help you finish more of the right work.",
                        "link_hint": "Coursera / YouTube / Book",
                    },
                },
                "wellness": {
                    "burnout_risk": "low",
                    "insight": "Work hours look reasonable based on task completions.",
                    "micro_habit": "Take a 5-minute walk outside after lunch.",
                },
                "cheer": "Small course corrections now will compound quickly. You've got this.",
            }
            return self._normalize_audit(fallback, context)

    async def check_accountability(self, task_title: str, delay_count: int, context: Dict[str, Any]) -> str:
        """Proactively intercepts user when a task is delayed repeatedly."""
        prompt = f"""You are Param Mitra, a life coach. The user has delayed a high-priority task '{task_title}' {delay_count} times.
        Look at their current context: {context.get('task_status', 'Busy')}
        Write a short, punchy, 2-sentence empathetic intervention asking WHY they are avoiding it, and suggesting breaking it down.
        Return raw text only.
        """
        try:
            raw = await self.llm.call(prompt)
            # LLM might return JSON or raw text depending on how call handles it
            try:
                import json
                data = json.loads(raw)
                return data.get("response", data.get("cheer", "Are we avoiding this? Let's break it down."))
            except Exception:
                return raw.strip()
        except Exception as e:
            logger.error(f"Accountability check failed: {e}")
            return f"I see you've delayed '{task_title}' again. Are we avoiding this because it's poorly scoped, or are you just overwhelmed? Let's break it down."
