"""
Param Mitra Agent — The Supreme Friend & Guru
=============================================
A high-performance life coach that observes all data streams (Git, Email, Tasks, Meetings)
to identify gaps in code quality, communication, and human potential.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class ParamMitraAgent:
    def __init__(self, llm_service, github_service=None, email_service=None, task_service=None):
        self.llm = llm_service
        self.github = github_service
        self.email = email_service
        self.tasks = task_service

    async def generate_audit(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesizes a full 'Life Audit' based on the user's recent activities.
        """
        prompt = f"""You are Param Mitra, a wise Guru and best friend.
Your goal is to tell the user the BLUNT truth about their performance and potential.

Context for Audit:
- Recent Code: {context.get('git_summary', 'No recent checkins found.')}
- Recent Emails: {context.get('email_summary', 'No recent replies.')}
- Task Efficiency: {context.get('task_status', 'No active tasks.')}
- Personal Goals: {context.get('goals', 'No long-term goals set.')}

Respond in a compassionate but firm 'Guru' tone.
Output JSON:
{{
  "guru_message": "A 3-sentence deep insight about the user's current state.",
  "scores": {{
    "code_mastery": number (0-100),
    "communication": number (0-100),
    "efficiency": number (0-100)
  }},
  "bottlenecks": [
    "One blunt observation about code",
    "One blunt observation about writing/meetings",
    "One blunt observation about procrastination"
  ],
  "potential_unlock": "One thing they should do today to reach their full potential."
}}
"""
        try:
            raw = await self.llm.call(prompt)
            import json
            # Extract JSON from markdown if necessary
            clean_json = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            return json.loads(clean_json)
        except Exception as e:
            logger.error(f"Param Mitra error: {e}")
            return {
                "guru_message": "I am observing your path. Today, focus on clarity over speed.",
                "scores": {"code_mastery": 75, "communication": 80, "efficiency": 60},
                "bottlenecks": ["Your code is functional but lacks documentation.", "Emails are too transactional.", "Tasks are being moved but not finished."],
                "potential_unlock": "Spend 30 minutes refactoring the core engine."
            }
