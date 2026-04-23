"""
LLM Service - Integration with Google Vertex AI
"""

import json
import logging
from typing import Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class LLMService(ABC):
    @abstractmethod
    async def call(self, prompt: str, **kwargs) -> str:
        pass


class MockLLMService(LLMService):
    async def call(self, prompt: str, **kwargs) -> str:
        if "execution plan" in prompt.lower():
            return json.dumps({
                "goal": "Execute workflow", "total_steps": 3,
                "steps": [
                    {"step_id": 0, "name": "Prepare context",  "type": "note",     "agent": "knowledge", "depends_on": [], "timeout_seconds": 10},
                    {"step_id": 1, "name": "Schedule meeting",  "type": "calendar", "agent": "scheduler", "depends_on": [0], "timeout_seconds": 20},
                    {"step_id": 2, "name": "Create task",       "type": "task",     "agent": "task",      "depends_on": [], "timeout_seconds": 10}
                ]
            })
        if "revised plan" in prompt.lower():
            return json.dumps({"revised_plan": [], "explanation": "Optimized"})
        if "on track" in prompt.lower():
            return json.dumps({"on_track": True, "reasoning": "Progress aligns", "recommended_action": "Continue"})
        if "more efficient" in prompt.lower():
            return json.dumps({"has_better_approach": True, "efficiency_gain": 0.25, "alternative_plan": [], "reasoning": "Can parallelize"})
        return json.dumps({"response": "OK"})


class VertexAILLMService(LLMService):
    """
    Vertex AI Gemini service with automatic model fallback.
    Tries models in order until one works.
    """

    # Models in preference order — newest/cheapest first
    FALLBACK_MODELS = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-001",
        "gemini-1.5-flash-001",
        "gemini-1.5-flash",
        "gemini-1.5-pro-001",
        "gemini-1.5-pro",
        "gemini-1.0-pro",
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

        # Try to build model — validate it exists at init time
        self.model = self._try_init_model(model)

    def _try_init_model(self, model_name: str):
        """Try to initialise a model, return the model object."""
        from vertexai.generative_models import GenerativeModel
        logger.info(f"🤖 Initialising Vertex AI model: {model_name}")
        return GenerativeModel(model_name)

    async def call(self, prompt: str, **kwargs) -> str:
        """
        Call Vertex AI. If the configured model returns 404,
        automatically try fallback models and remember the working one.
        """
        # Build list: configured model first, then fallbacks
        models_to_try = [self.model_name] + [
            m for m in self.FALLBACK_MODELS if m != self.model_name
        ]

        last_err = None
        for model_name in models_to_try:
            try:
                model = self._try_init_model(model_name)
                response = model.generate_content(prompt)
                if model_name != self.model_name:
                    logger.info(f"✅ Switched to working model: {model_name}")
                    self.model_name = model_name   # remember for next call
                    self.model = model
                return response.text
            except Exception as e:
                err_str = str(e)
                if "404" in err_str or "not found" in err_str.lower() or "does not have access" in err_str.lower():
                    logger.warning(f"⚠️  Model {model_name} not available, trying next...")
                    last_err = e
                    continue
                # Any other error (quota, auth, etc) — raise immediately
                logger.error(f"Vertex AI call failed ({model_name}): {e}")
                raise

        logger.error(f"❌ All Vertex AI models failed. Last error: {last_err}")
        raise last_err


def create_llm_service(use_mock: bool = True,
                       project_id: Optional[str] = None,
                       model: str = "gemini-2.0-flash") -> LLMService:
    if use_mock:
        logger.info("Using Mock LLM Service (development)")
        return MockLLMService()
    if not project_id:
        raise ValueError("GCP project_id required for Vertex AI")
    logger.info(f"Using Vertex AI LLM Service (project: {project_id}, model: {model})")
    return VertexAILLMService(project_id, model=model)
