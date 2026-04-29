"""
LLM Service — Vertex AI (primary) → Google AI Studio (fallback) → Mock (dev).
Set GEMINI_API_KEY env var to enable Google AI Studio fallback.
"""

import json
import os
import logging
from typing import Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


class LLMService(ABC):
    @abstractmethod
    async def call(self, prompt: str, **kwargs) -> str:
        pass


class MockLLMService(LLMService):
    """Returns stub JSON — only used in local dev (USE_MOCK_LLM=true)."""
    async def call(self, prompt: str, **kwargs) -> str:
        if "execution plan" in prompt.lower() or "concrete execution plan" in prompt.lower():
            goal_line = next((l for l in prompt.split("\n") if l.startswith("Goal:")), "Goal: task")
            goal_text = goal_line.replace("Goal:", "").strip()[:60]
            from datetime import datetime, timedelta
            due = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            
            if "analytic" in prompt.lower() or "report" in prompt.lower() or "chart" in prompt.lower():
                return json.dumps({
                    "goal": goal_text,
                    "schema_version": "workflow-plan/v1",
                    "total_steps": 1,
                    "steps": [
                        {"step_id": 0, "name": f"Analytics: {goal_text}", "type": "analytics",
                         "agent": "analytics", "depends_on": [], "inputs": {
                             "title": goal_text,
                             "data_source": "mock_data",
                             "metrics": ["completion_rate", "velocity"]
                         }, "expected_outputs": ["report_id"], "error_handling": "retry", "timeout_seconds": 30}
                    ],
                    "parallel_groups": [],
                    "estimated_duration_seconds": 30,
                })
                
            return json.dumps({
                "goal": goal_text,
                "schema_version": "workflow-plan/v1",
                "total_steps": 2,
                "steps": [
                    {"step_id": 0, "name": f"Create task for: {goal_text}", "type": "create_task",
                     "agent": "task", "depends_on": [], "inputs": {
                         "title": goal_text,
                         "description": goal_text,
                         "due_date": due,
                         "priority": "medium",
                     }, "expected_outputs": ["task_id"], "error_handling": "retry", "timeout_seconds": 30},
                    {"step_id": 1, "name": "Block time to work on goal", "type": "schedule_event",
                     "agent": "scheduler", "depends_on": [0], "inputs": {
                         "title": f"Work on: {goal_text[:40]}",
                         "date": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
                         "duration_minutes": 60,
                     }, "expected_outputs": ["event_id"], "error_handling": "retry", "timeout_seconds": 30},
                ],
                "parallel_groups": [[0], [1]],
                "estimated_duration_seconds": 90,
            })
        if "writer agent" in prompt.lower() or "draft a high-quality document" in prompt.lower():
            return json.dumps({
                "title": "AI Strategy Brief",
                "content": f"Summary for {prompt.split('Topic:')[-1].splitlines()[0].strip() or 'the requested topic'}.",
                "word_count": 120,
            })
        if "coder agent" in prompt.lower() or "analyze the code for bugs" in prompt.lower():
            return json.dumps({
                "analysis": "Loop indexing can be simplified for readability.",
                "suggested_fix": "for item in x: print(item)",
                "complexity_impact": "low",
            })
        if "liaison agent" in prompt.lower() or "rewrite this for" in prompt.lower():
            return json.dumps({
                "original": "Do this now.",
                "revised": "Could you please take a look at this when you have a moment?",
                "tone_changes": ["Added politeness", "softened urgency", "kept the request clear"],
            })
        if "param mitra" in prompt.lower() or "weekly insight report" in prompt.lower():
            return json.dumps({
                "summary": "You’re making steady progress, with the clearest wins in task execution and room to sharpen communication.",
                "vibe_score": 82,
                "code": {
                    "assessment": "good",
                    "insight": "Code activity looks healthy and consistent, with enough momentum to keep shipping.",
                    "micro_habit": "Review your own PR for 2 minutes before requesting a review.",
                    "training": None,
                },
                "communication": {
                    "assessment": "needs_improvement",
                    "insight": "Your communication would benefit from a little more context and warmth in a few places.",
                    "micro_habit": "Add one sentence of positive context before giving negative feedback.",
                    "training": {
                        "topic": "Clearer written communication",
                        "why": "A more explicit tone can cut down on follow-up questions and friction.",
                        "link_hint": "Coursera / YouTube / Book",
                    },
                },
                "strategic_alignment": {
                    "score": 79,
                    "assessment": "Most of the current work aligns with your long-term goals, but a few items still look exploratory.",
                    "suggestion": "Keep one eye on the North Star and trim any work that does not clearly support it.",
                },
                "efficiency": {
                    "assessment": "good",
                    "insight": "Task flow is reasonably balanced, and you are finishing more than you are starting.",
                    "micro_habit": "Write down tomorrow's top priority before you close your laptop today.",
                    "training": None,
                },
                "wellness": {
                    "burnout_risk": "low",
                    "insight": "Your pacing looks sustainable. You haven't had late-night commits.",
                    "micro_habit": "Take a 5-minute stretch break every 90 minutes."
                },
                "cheer": "Keep going. Small wins are stacking up.",
            })
            
        if "life coach. the user has delayed" in prompt.lower():
            return "I see you've delayed this high-priority task again. Is it feeling too overwhelming right now? Let's break it down into a 15-minute chunk and just start."
        if "revised plan" in prompt.lower():
            return json.dumps({"revised_plan": [], "explanation": "Optimized", "efficiency_gain": 0.20, "confidence": 0.80})
        if "on track" in prompt.lower():
            return json.dumps({"on_track": True, "reasoning": "Progress aligns", "recommended_action": "Continue"})
        if "more efficient" in prompt.lower():
            return json.dumps({"has_better_approach": True, "efficiency_gain": 0.25, "alternative_plan": [], "reasoning": "Can parallelize"})
        return json.dumps({"response": "OK"})


class GoogleAIStudioLLMService(LLMService):
    """Uses google-genai SDK with a Gemini API key — no Vertex AI quota needed."""

    # Models to try in order — google-genai uses bare model IDs
    MODELS = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
        "gemini-1.5-pro",
    ]

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        from google import genai
        self.client    = genai.Client(api_key=api_key)
        # Normalise model name — strip "models/" prefix if present, use bare ID
        self.model     = model.replace("models/", "").split("/")[-1]
        # If passed an unknown name, fall back to flash
        if self.model not in self.MODELS and not self.model.startswith("gemini"):
            self.model = "gemini-2.0-flash"
        logger.info(f"✅ Google AI Studio LLM: {self.model}")

    async def call(self, prompt: str, **kwargs) -> str:
        import asyncio
        loop     = asyncio.get_event_loop()
        models   = [self.model] + [m for m in self.MODELS if m != self.model]
        last_err = None
        for model in models:
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda m=model: self.client.models.generate_content(
                        model=m, contents=prompt)
                )
                if model != self.model:
                    logger.info(f"✅ Switched to working AI Studio model: {model}")
                    self.model = model
                return response.text
            except Exception as e:
                err = str(e)
                if any(k in err for k in ["404", "not found", "INVALID_ARGUMENT", "invalid"]):
                    logger.warning(f"⚠️  AI Studio model {model} failed, trying next…")
                    last_err = e
                    continue
                raise
        raise last_err


class VertexAILLMService(LLMService):
    """Vertex AI Gemini with automatic model fallback."""

    FALLBACK_MODELS = [
        "gemini-2.0-flash", "gemini-2.0-flash-001",
        "gemini-1.5-flash-001", "gemini-1.5-flash",
        "gemini-1.5-pro-001",  "gemini-1.5-pro",
    ]

    def __init__(self, project_id: str, location: str = "us-central1",
                 model: str = "gemini-2.0-flash"):
        import vertexai
        from vertexai.generative_models import GenerativeModel
        self.project_id = project_id
        self.location   = location
        self.model_name = model
        vertexai.init(project=project_id, location=location)
        self._GenerativeModel = GenerativeModel
        self.model = GenerativeModel(model)

    async def call(self, prompt: str, **kwargs) -> str:
        from vertexai.generative_models import GenerativeModel
        models_to_try = [self.model_name] + [m for m in self.FALLBACK_MODELS if m != self.model_name]
        last_err = None
        for model_name in models_to_try:
            try:
                model    = GenerativeModel(model_name)
                response = await model.generate_content_async(prompt)
                if model_name != self.model_name:
                    logger.info(f"✅ Switched to working Vertex model: {model_name}")
                    self.model_name = model_name
                return response.text
            except Exception as e:
                err_str = str(e)
                if any(k in err_str for k in ["404", "not found", "does not have access", "PERMISSION_DENIED"]):
                    logger.warning(f"⚠️  Vertex model {model_name} unavailable, trying next…")
                    last_err = e
                    continue
                raise
        raise last_err


def create_llm_service(use_mock: bool = True,
                       project_id: Optional[str] = None,
                       model: str = "gemini-2.0-flash") -> LLMService:
    if use_mock:
        logger.info("Using Mock LLM Service (development)")
        return MockLLMService()

    # If a Gemini API key is available, prefer Google AI Studio (no Vertex quota needed)
    if GEMINI_API_KEY:
        logger.info("Using Google AI Studio LLM (GEMINI_API_KEY set)")
        return GoogleAIStudioLLMService(api_key=GEMINI_API_KEY, model=model)

    if not project_id:
        raise ValueError("GCP project_id required for Vertex AI")

    logger.info(f"Using Vertex AI LLM Service (project: {project_id}, model: {model})")
    return VertexAILLMService(project_id, model=model)
