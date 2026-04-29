"""
CRITIC AGENT - The Innovation Core
Proactively audits workflow progress, detects bottlenecks, and replans autonomously.
This agent embodies "Agentic AI" - it doesn't just execute, it thinks strategically.
"""

import json
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging
from enum import Enum
from backend.services.llm_utils import parse_llm_json
from backend.agents.workflow_schema import WorkflowPlan
from backend.api.routers.trace import emit_trace

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk levels for detected issues"""
    CRITICAL = "critical"      # Workflow will fail
    HIGH = "high"             # Major inefficiency
    MEDIUM = "medium"         # Could be better
    LOW = "low"               # Minor optimization


@dataclass
class WorkflowIssue:
    """Detected workflow issue"""
    issue_type: str
    risk_level: RiskLevel
    description: str
    affected_steps: List[int]
    detection_time: str
    evidence: Dict[str, Any]


@dataclass
class ReplanDecision:
    """Autonomous replan decision made by Critic Agent"""
    original_plan: WorkflowPlan
    revised_plan: WorkflowPlan
    reasoning: str
    efficiency_gain: float  # percentage
    risk_mitigation: List[str]
    confidence_score: float  # 0.0-1.0
    replanned_at: str


class CriticAgent:
    """
    The Critic Agent autonomously monitors workflow execution and proactively replans.
    
    Key Responsibilities:
    1. Monitor workflow progress in real-time via Pub/Sub
    2. Audit against the Knowledge Graph for context
    3. Detect dead-ends, bottlenecks, and inefficiencies
    4. Generate alternative execution paths
    5. Autonomously decide to replan if efficiency improves >15%
    6. Provide transparent reasoning for decisions
    """
    
    def __init__(self, llm_service, knowledge_graph_service, pubsub_service):
        self.llm_service = llm_service
        self.knowledge_graph = knowledge_graph_service
        self.pubsub = pubsub_service
        self.current_workflows: Dict[str, Dict] = {}
        self.decision_history: List[ReplanDecision] = []
        
    async def start_monitoring(self, workflow_id: str, workflow_plan: Any,
                               goal: str = ""):
        """
        Start monitoring a workflow for potential issues.
        goal is stored explicitly so _detect_goal_drift never has to
        guess it from plan[0] (steps don't own the workflow goal).
        """
        logger.info(f"🔍 Critic Agent starting monitoring for workflow {workflow_id}")
        normalized_plan = WorkflowPlan.from_payload(workflow_plan, default_goal=goal)
        self.current_workflows[workflow_id] = {
            "plan":       normalized_plan,
            "goal":       goal or normalized_plan.goal,  # authoritative source of the workflow goal
            "progress":   [],
            "issues":     [],
            "start_time": datetime.now().isoformat(),
            "status":     "monitoring",
        }
        
        # Subscribe to workflow progress events
        await self.pubsub.subscribe(
            topic=f"workflow-{workflow_id}-progress",
            callback=self._on_progress_update,
            context={"workflow_id": workflow_id}
        )
    
    async def _on_progress_update(self, message: Dict[str, Any], context: Dict):
        """
        Called whenever a step in the workflow completes.
        This is where the magic happens - continuous auditing.
        """
        workflow_id = context["workflow_id"]
        step_result = message
        
        logger.info(f"📊 Received progress update for {workflow_id}: {step_result['step_name']}")
        
        # Record progress
        self.current_workflows[workflow_id]["progress"].append(step_result)
        
        # AUDIT: Detect issues
        issues = await self._audit_workflow(workflow_id)
        
        if issues:
            logger.warning(f"⚠️ Detected {len(issues)} issues in workflow {workflow_id}")
            for issue in issues:
                self.current_workflows[workflow_id]["issues"].append(issue)
                
                # HIGH RISK = Take action immediately
                if issue.risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
                    await self._attempt_replan(workflow_id, issue)
    
    async def _audit_workflow(self, workflow_id: str) -> List[WorkflowIssue]:
        """
        Comprehensive audit of workflow health.
        """
        try:
            await emit_trace("critic", "thinking", f"Auditing workflow {workflow_id} for inefficiencies...")
        except Exception:
            pass
        workflow = self.current_workflows[workflow_id]
        issues = []
        
        # 1. DEADLOCK DETECTION
        deadlock_issue = await self._detect_deadlock(workflow)
        if deadlock_issue:
            issues.append(deadlock_issue)
        
        # 2. BOTTLENECK DETECTION
        bottleneck_issues = await self._detect_bottlenecks(workflow)
        issues.extend(bottleneck_issues)
        
        # 3. GOAL DRIFT DETECTION
        drift_issue = await self._detect_goal_drift(workflow)
        if drift_issue:
            issues.append(drift_issue)
        
        # 4. EFFICIENCY ANALYSIS
        inefficiency_issue = await self._detect_inefficiency(workflow)
        if inefficiency_issue:
            issues.append(inefficiency_issue)
        
        return issues
    
    async def _detect_deadlock(self, workflow: Dict) -> Optional[WorkflowIssue]:
        """
        Detect circular dependencies that could cause infinite loops.
        Uses Knowledge Graph to analyze task dependencies.
        """
        plan = workflow["plan"]
        dependencies = {}
        
        for step in plan.steps:
            dependencies[step.step_id] = list(step.depends_on)
        
        # Check for cycles using graph traversal
        visited = set()
        rec_stack = set()
        
        def has_cycle(step_id):
            visited.add(step_id)
            rec_stack.add(step_id)
            
            for dep in dependencies.get(step_id, []):
                if dep not in visited:
                    if has_cycle(dep):
                        return True
                elif dep in rec_stack:
                    return True
            
            rec_stack.remove(step_id)
            return False
        
        # Check all steps
        for step_id in dependencies:
            if step_id not in visited:
                if has_cycle(step_id):
                    return WorkflowIssue(
                        issue_type="circular_dependency",
                        risk_level=RiskLevel.CRITICAL,
                        description=f"Circular dependency detected in workflow steps",
                        affected_steps=list(rec_stack),
                        detection_time=datetime.now().isoformat(),
                        evidence={"dependencies": dependencies}
                    )
        
        return None
    
    async def _detect_bottlenecks(self, workflow: Dict) -> List[WorkflowIssue]:
        """
        Detect bottlenecks - steps that are taking too long or blocking others.
        """
        issues = []
        progress = workflow["progress"]
        plan = workflow["plan"]
        
        if not progress:
            return issues
        
        # Calculate average step duration
        step_durations = {}
        for execution in progress:
            step_id = execution.get("step_id")
            step_name = execution.get("step_name")
            duration = execution.get("duration_seconds", 0)

            key = step_id if step_id is not None else step_name
            if key not in step_durations:
                step_durations[key] = []
            step_durations[key].append(duration)
        
        # Identify outliers (steps taking 2x average time)
        avg_duration = sum(sum(v) for v in step_durations.values()) / len(progress) if progress else 0
        
        steps_by_id = {step.step_id: step for step in plan.steps}
        steps_by_name = {step.name: step for step in plan.steps}

        for step_key, durations in step_durations.items():
            avg_step_duration = sum(durations) / len(durations)
            
            if avg_step_duration > (avg_duration * 2) and avg_step_duration > 5:  # >5 sec and 2x avg
                step_obj = steps_by_id.get(step_key)
                if step_obj is None:
                    step_obj = steps_by_name.get(step_key)
                
                # Check how many steps depend on this
                dependents = 0
                if step_obj is not None:
                    dependents = sum(1 for s in plan.steps if step_obj.step_id in s.depends_on)
                
                if dependents > 0:
                    affected_step_id = step_obj.step_id if step_obj is not None else -1
                    issues.append(WorkflowIssue(
                        issue_type="bottleneck",
                        risk_level=RiskLevel.HIGH if dependents > 2 else RiskLevel.MEDIUM,
                        description=f"Step '{step_obj.name if step_obj else step_key}' is a bottleneck (avg {avg_step_duration:.1f}s). "
                                   f"{dependents} downstream steps waiting.",
                        affected_steps=[affected_step_id],
                        detection_time=datetime.now().isoformat(),
                        evidence={
                            "avg_duration": avg_step_duration,
                            "baseline_duration": avg_duration,
                            "dependent_steps": dependents
                        }
                    ))
        
        return issues
    
    async def _detect_goal_drift(self, workflow: Dict) -> Optional[WorkflowIssue]:
        """
        Detect if workflow has drifted from original goal.
        Uses LLM to compare current progress against original objective.
        """
        progress_text = "\n".join(
            f"- {p['step_name']}: {p['status']}"
            for p in workflow["progress"][-5:]
        )
        original_goal = workflow.get("goal") or "Unknown"
        
        prompt = f"""
        Original Goal: {original_goal}
        
        Recent Progress:
        {progress_text}
        
        Is this workflow still on track to achieve the original goal?
        Respond with JSON: {{"on_track": true/false, "reasoning": "...", "recommended_action": "..."}}
        """
        
        try:
            response = await self.llm_service.call(prompt)
            analysis  = parse_llm_json(response)
        except Exception as e:
            logger.warning(f"Goal drift check failed: {e}")
            return None   # safe fallback: don't flag a problem we can't verify

        if not analysis.get("on_track"):
            return WorkflowIssue(
                issue_type="goal_drift",
                risk_level=RiskLevel.HIGH,
                description=f"Workflow drifted from goal. {analysis.get('reasoning')}",
                affected_steps=[],
                detection_time=datetime.now().isoformat(),
                evidence={"analysis": analysis},
            )

        return None
    
    async def _detect_inefficiency(self, workflow: Dict) -> Optional[WorkflowIssue]:
        """Detect if a more efficient path exists for the same goal."""
        plan = workflow["plan"]
        goal = plan.goal or workflow.get("goal") or ""
        plan_text = json.dumps(plan.to_dict(), indent=2)

        prompt = f"""
        Goal: {goal}

        Current Plan:
        {plan_text}

        Suggest a more efficient plan if one exists. Respond with JSON only:
        {{
            "has_better_approach": true,
            "efficiency_gain": 0.2,
            "alternative_plan": [...],
            "reasoning": "..."
        }}
        """

        try:
            response = await self.llm_service.call(prompt)
            analysis  = parse_llm_json(response)
        except Exception as e:
            logger.warning(f"Inefficiency check failed: {e}")
            return None

        gain = analysis.get("efficiency_gain", 0)
        if analysis.get("has_better_approach") and gain > 0.15:
            return WorkflowIssue(
                issue_type="suboptimal_plan",
                risk_level=RiskLevel.HIGH,   # HIGH so _attempt_replan is triggered
                description=f"More efficient approach found ({gain*100:.0f}% faster). {analysis.get('reasoning')}",
                affected_steps=[step.step_id for step in plan.steps],
                detection_time=datetime.now().isoformat(),
                evidence={
                    "alternative_plan": analysis.get("alternative_plan"),
                    "efficiency_gain":  gain,
                },
            )

        return None
    
    async def _attempt_replan(self, workflow_id: str, issue: WorkflowIssue):
        """Attempt an autonomous replan in response to a detected issue."""
        logger.info(f"🧠 Critic Agent attempting autonomous replan for {workflow_id}")
        try:
            await emit_trace("critic", "thinking", f"Generating autonomous replan for issue: {issue.description}")
        except Exception:
            pass

        workflow      = self.current_workflows[workflow_id]
        original_plan = workflow["plan"]
        progress      = workflow["progress"]

        # ── Derive revised plan, efficiency gain, and confidence ─────────────
        if issue.issue_type == "suboptimal_plan":
            # LLM already provided the alternative plan and gain during detection;
            # reuse them to avoid a redundant second LLM call.
            revised_plan    = WorkflowPlan.from_payload(
                issue.evidence.get("alternative_plan") or [],
                default_goal=workflow.get("goal", ""),
            )
            efficiency_gain = float(issue.evidence.get("efficiency_gain", 0.0))
            # Confidence is proportional to reported gain: higher gain → higher confidence.
            confidence      = min(0.95, 0.6 + efficiency_gain * 0.5)
        else:
            result = await self._generate_revised_plan(original_plan, issue, progress)
            if result is None:
                logger.warning(f"Could not generate revised plan for {workflow_id}")
                return
            revised_plan    = result["plan"]
            efficiency_gain = result["efficiency_gain"]
            confidence      = result["confidence"]

        if not revised_plan.steps:
            logger.warning(f"Revised plan is empty for {workflow_id}, skipping replan")
            return

        reasoning = (
            f"Issue detected: {issue.description}. "
            f"Replan estimated to improve efficiency by {efficiency_gain*100:.1f}% "
            f"(confidence {confidence*100:.0f}%)."
        )
        decision = ReplanDecision(
            original_plan=original_plan,
            revised_plan=revised_plan,
            reasoning=reasoning,
            efficiency_gain=efficiency_gain,
            risk_mitigation=[
                "Pause current step",
                "Update task dependencies",
                "Resume with new plan",
                "Monitor for conflicts",
            ],
            confidence_score=confidence,
            replanned_at=datetime.now().isoformat(),
        )

        # ── Apply only when both thresholds are met ───────────────────────────
        if efficiency_gain > 0.15 and confidence > 0.75:
            logger.info(f"✅ Accepting replan for {workflow_id} "
                        f"(↑{efficiency_gain*100:.1f}% efficiency, {confidence*100:.0f}% confidence)")

            await self.pubsub.publish(
                topic=f"workflow-{workflow_id}-replan",
                message={
                    "action":            "replan",
                    "original_plan":     original_plan.to_dict(),
                    "revised_plan":      revised_plan.to_dict(),
                    "reasoning":         reasoning,
                    "efficiency_gain":   efficiency_gain,
                    "approved_by_critic": True,
                },
            )

            self.decision_history.append(decision)
            workflow["plan"] = revised_plan
            workflow["status"] = "replanned"

            from backend.database import save_critic_decision
            save_critic_decision(
                workflow_id=workflow_id,
                reasoning=reasoning,
                efficiency_gain=efficiency_gain,
                confidence_score=confidence,
                original_plan=original_plan.to_dict(),
                revised_plan=revised_plan.to_dict(),
                accepted=True,
            )
        else:
            logger.info(f"Rejected replan for {workflow_id} "
                        f"(gain={efficiency_gain*100:.1f}%, confidence={confidence*100:.0f}%)")
            await self.pubsub.publish(
                topic=f"workflow-{workflow_id}-audit",
                message={
                    "action": "issue_detected",
                    "issue": {
                        "type":        issue.issue_type,
                        "description": issue.description,
                        "risk_level":  issue.risk_level.value,
                    },
                    "recommendation": "Human review recommended",
                },
            )

            from backend.database import save_critic_decision
            save_critic_decision(
                workflow_id=workflow_id,
                reasoning=reasoning,
                efficiency_gain=efficiency_gain,
                confidence_score=confidence,
                original_plan=original_plan.to_dict(),
                revised_plan=revised_plan.to_dict(),
                accepted=False,
            )

    async def _generate_revised_plan(
        self,
        original_plan: WorkflowPlan,
        issue: WorkflowIssue,
        progress: List[Dict],
    ) -> Optional[Dict]:
        """
        Ask the LLM for a revised plan that fixes the issue.
        Returns a dict with keys: plan (list), efficiency_gain (float), confidence (float).
        Returns None when the LLM call fails.
        """
        original_text = json.dumps(original_plan.to_dict(), indent=2)
        progress_text = json.dumps(progress[-3:], indent=2) if progress else "No progress yet"

        prompt = f"""
        Original Execution Plan:
        {original_text}

        Detected Issue: {issue.issue_type} — {issue.description}

        Recent Progress:
        {progress_text}

        Generate a revised plan that addresses the issue while preserving the original goal.
        Respond with JSON only, no markdown:
        {{
            "revised_plan": [...],
            "explanation": "...",
            "efficiency_gain": 0.0,
            "confidence": 0.0
        }}

        efficiency_gain: fraction 0.0–1.0 (e.g. 0.25 means 25% improvement vs original).
        confidence: fraction 0.0–1.0 reflecting how certain you are the revision helps.
        """

        try:
            response = await self.llm_service.call(prompt)
            data      = parse_llm_json(response)
            return {
                "plan":            WorkflowPlan.from_payload(
                    data.get("revised_plan", []),
                    default_goal=original_plan.goal,
                ),
                "efficiency_gain": float(data.get("efficiency_gain", 0.0)),
                "confidence":      float(data.get("confidence", 0.0)),
            }
        except Exception as e:
            logger.error(f"Error generating revised plan: {e}")
            return None
    
    def get_decision_history(self) -> List[ReplanDecision]:
        """Return in-memory decisions, falling back to DB when the list is empty (post-restart)."""
        if self.decision_history:
            return self.decision_history

        try:
            from backend.database import get_critic_decisions
            rows = get_critic_decisions(limit=100)
            return [
                ReplanDecision(
                    original_plan=WorkflowPlan.from_payload(
                        json.loads(r.original_plan_json) if r.original_plan_json else []
                    ),
                    revised_plan=WorkflowPlan.from_payload(
                        json.loads(r.revised_plan_json) if r.revised_plan_json else []
                    ),
                    reasoning=r.reasoning,
                    efficiency_gain=r.efficiency_gain,
                    risk_mitigation=[],
                    confidence_score=r.confidence_score,
                    replanned_at=r.replanned_at.isoformat(),
                )
                for r in rows
            ]
        except Exception as e:
            logger.warning(f"Could not load decision history from DB: {e}")
            return []

    def get_workflow_audit_report(self, workflow_id: str) -> Dict[str, Any]:
        """Audit report for a workflow — includes persisted decisions from the DB."""
        workflow = self.current_workflows.get(workflow_id, {})

        try:
            from backend.database import get_critic_decisions
            db_decisions = get_critic_decisions(workflow_id=workflow_id)
            replans_count = len(db_decisions)
        except Exception:
            replans_count = len([d for d in self.decision_history if d])

        return {
            "workflow_id":           workflow_id,
            "status":                workflow.get("status"),
            "start_time":            workflow.get("start_time"),
            "total_issues_detected": len(workflow.get("issues", [])),
            "issues": [
                {
                    "type":        issue.issue_type,
                    "risk_level":  issue.risk_level.value,
                    "description": issue.description,
                    "detected_at": issue.detection_time,
                }
                for issue in workflow.get("issues", [])
            ],
            "replans_executed": replans_count,
        }
