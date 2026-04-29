"""
Security & Strategy Auditor Agent
The "Trusted Teammate" - Reviews high-stakes actions before execution
Implements "Cross-Agent Vibe-Checking" for safe autonomous operations

This agent acts as a peer-reviewer, assessing:
1. Intent Alignment - Is this aligned with user's long-term goals?
2. PII/Safety Check - Is private information being leaked?
3. Conflict Resolution - Does this conflict with previous actions?
4. Risk Assessment - What's the downside if this goes wrong?
5. Alternative Validation - Are there safer alternatives?
"""

import json
import asyncio
from backend.services.llm_utils import parse_llm_json
from backend.api.routers.trace import emit_trace
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AuditRisk(Enum):
    """Risk levels for auditor decisions"""
    CRITICAL = "critical"          # Block execution immediately
    HIGH = "high"                  # Require human approval
    MEDIUM = "medium"              # Flag but allow with warnings
    LOW = "low"                    # Approve with monitoring
    SAFE = "safe"                  # Approve without concerns


class ConflictType(Enum):
    """Types of conflicts detected"""
    DATA_CONSISTENCY = "data_consistency"      # Contradicts previous state
    GOAL_CONFLICT = "goal_conflict"            # Contradicts stated goals
    SECURITY_CONFLICT = "security_conflict"    # Security policy violation
    POLICY_CONFLICT = "policy_conflict"        # Business rule violation


@dataclass
class AuditConcern:
    """A concern raised by the auditor"""
    concern_type: str
    severity: AuditRisk
    description: str
    evidence: List[str]
    recommendation: str
    confidence_score: float  # 0.0-1.0


@dataclass
class AuditReport:
    """Complete audit of an action"""
    action_id: str
    executor_agent: str
    executor_reasoning: str
    
    # The 5-point vibe check
    intent_alignment: AuditConcern
    pii_safety: AuditConcern
    conflict_resolution: AuditConcern
    risk_assessment: AuditConcern
    alternative_validation: AuditConcern
    
    # Overall decision
    overall_risk: AuditRisk
    approval_status: str  # "approved", "conditional", "rejected", "escalated"
    final_recommendation: str
    human_review_required: bool
    
    # Metadata
    audited_at: str
    audit_duration_ms: float


class AuditorAgent:
    """
    The Security & Strategy Auditor Agent.
    
    Acts as a "trusted teammate" that reviews high-stakes actions before execution.
    Ensures agent autonomy is balanced with safety and alignment.
    
    Key Principle:
    "Don't block good ideas, but DO block dangerous ones."
    """
    
    def __init__(self, llm_service, knowledge_graph, user_goals=None, pubsub_service=None):
        self.llm_service = llm_service
        self.knowledge_graph = knowledge_graph
        self.user_goals = user_goals or {}  # Long-term user objectives
        self.audit_history: List[AuditReport] = []
        self.previous_actions: Dict[str, Any] = {}  # Track previous actions for conflict detection
        self.pii_patterns = [
            "ssn", "social security", "credit card", "card number",
            "password", "api_key", "token", "secret",
            "email", "phone", "address", "home",
            "salary", "account number"
        ]
        self.pubsub = pubsub_service
    
    async def audit_action(self, executor_agent: str, 
                          action: Dict[str, Any],
                          reasoning: str,
                          previous_context: str = "") -> AuditReport:
        """
        Conduct a comprehensive "vibe check" on a proposed action.
        
        This is the core security gate before high-stakes operations.
        """
        import time
        start_time = time.time()
        
        action_id = action.get("id", f"action-{datetime.now().timestamp()}")
        logger.info(f"🔍 Auditor: Vibe-checking action from {executor_agent}")
        try:
            await emit_trace("auditor", "thinking", f"Vibe-checking proposed action from {executor_agent}")
        except Exception:
            pass
        
        # The 5-Point Vibe Check
        intent_alignment = await self._check_intent_alignment(
            action, reasoning, previous_context
        )
        
        pii_safety = await self._check_pii_safety(action, reasoning)
        
        conflict_resolution = await self._check_conflicts(
            action, executor_agent, previous_context
        )
        
        risk_assessment = await self._assess_risk(action, reasoning)
        
        alternative_validation = await self._validate_alternatives(
            action, reasoning
        )
        
        # Determine overall risk and approval
        overall_risk = self._aggregate_risk_levels([
            intent_alignment.severity,
            pii_safety.severity,
            conflict_resolution.severity,
            risk_assessment.severity,
            alternative_validation.severity
        ])
        
        approval_status, recommendation, requires_human = self._make_decision(
            overall_risk,
            [intent_alignment, pii_safety, conflict_resolution, 
             risk_assessment, alternative_validation]
        )
        
        # Create audit report
        duration_ms = (time.time() - start_time) * 1000
        
        report = AuditReport(
            action_id=action_id,
            executor_agent=executor_agent,
            executor_reasoning=reasoning,
            intent_alignment=intent_alignment,
            pii_safety=pii_safety,
            conflict_resolution=conflict_resolution,
            risk_assessment=risk_assessment,
            alternative_validation=alternative_validation,
            overall_risk=overall_risk,
            approval_status=approval_status,
            final_recommendation=recommendation,
            human_review_required=requires_human,
            audited_at=datetime.now().isoformat(),
            audit_duration_ms=duration_ms
        )
        
        if self.pubsub:
            await self.pubsub.publish("system-vibe-updates", {
                "source": "AuditorAgent",
                "overall_risk": report.overall_risk.value,
                "approval_status": report.approval_status,
                "timestamp": datetime.now().isoformat()
            })

        # Store in history
        self.audit_history.append(report)
        
        # Store action for future conflict detection
        self.previous_actions[action_id] = {
            "executor": executor_agent,
            "action": action,
            "timestamp": datetime.now().isoformat(),
            "approved": approval_status == "approved"
        }
        
        logger.info(f"✅ Audit Complete: {approval_status.upper()} "
                   f"(Risk: {overall_risk.value})")
        
        return report
    
    async def _check_intent_alignment(self, action: Dict, reasoning: str,
                                     context: str) -> AuditConcern:
        """
        Check if action aligns with user's long-term goals.
        
        Example:
        - User goal: "Launch product by March"
        - Action: "Spend 2 weeks on UI polish"
        - Issue: Timing conflict with launch goal
        """
        
        logger.info("📋 Checking Intent Alignment...")
        
        goals_text = json.dumps(self.user_goals)
        action_text = json.dumps(action)
        
        prompt = f"""
        User's Long-Term Goals:
        {goals_text}
        
        Proposed Action:
        {action_text}
        
        Executor's Reasoning:
        {reasoning}
        
        Context:
        {context}
        
        Assess if the proposed action aligns with the user's long-term goals.
        Respond with JSON:
        {{
            "is_aligned": true/false,
            "alignment_score": 0.85,
            "concerns": ["concern 1", "concern 2"],
            "reasoning": "...",
            "severity": "safe|low|medium|high|critical"
        }}
        """
        
        try:
            response = await self.llm_service.call(prompt)
            analysis = parse_llm_json(response)
        except Exception:
            analysis = {
                "is_aligned": True,
                "alignment_score": 0.5,
                "concerns": [],
                "severity": "medium",
                "reasoning": "Unable to assess (mock mode)",
            }
        
        severity_map = {
            "safe": AuditRisk.SAFE,
            "low": AuditRisk.LOW,
            "medium": AuditRisk.MEDIUM,
            "high": AuditRisk.HIGH,
            "critical": AuditRisk.CRITICAL
        }
        
        return AuditConcern(
            concern_type="intent_alignment",
            severity=severity_map.get(analysis.get("severity"), AuditRisk.MEDIUM),
            description=analysis.get("reasoning", "Intent check incomplete"),
            evidence=analysis.get("concerns", []),
            recommendation=f"Action {'aligns' if analysis.get('is_aligned') else 'may conflict'} "
                          f"with goals (confidence: {analysis.get('alignment_score', 0):.0%})",
            confidence_score=analysis.get("alignment_score", 0.5)
        )
    
    async def _check_pii_safety(self, action: Dict, reasoning: str) -> AuditConcern:
        """
        Check if private information (PII) is being leaked.
        
        Detects: SSN, credit cards, passwords, emails, addresses, etc.
        """
        
        logger.info("🔐 Checking PII/Safety...")
        
        # Convert action and reasoning to lowercase for pattern matching
        action_text = json.dumps(action).lower()
        reasoning_text = reasoning.lower()
        combined_text = action_text + reasoning_text
        
        found_pii = []
        for pattern in self.pii_patterns:
            if pattern in combined_text:
                found_pii.append(pattern)
        
        # Ask LLM for semantic analysis too
        prompt = f"""
        Action Data:
        {json.dumps(action)}
        
        Reasoning:
        {reasoning}
        
        Check if any personally identifiable information (PII) would be exposed or leaked.
        Look for: 
        - Financial data (credit cards, bank accounts)
        - Personal identifiers (SSN, passport numbers)
        - Health information
        - Authentication data (passwords, tokens)
        - Contact information in unsafe contexts
        
        Respond with JSON:
        {{
            "pii_detected": false,
            "pii_types": [],
            "risk_level": "safe|low|medium|high|critical",
            "exposure_risk": "no risk|low risk|medium risk|high risk|critical risk",
            "recommendation": "..."
        }}
        """
        
        try:
            response = await self.llm_service.call(prompt)
            analysis = parse_llm_json(response)
        except:
            analysis = {
                "pii_detected": len(found_pii) > 0,
                "pii_types": found_pii,
                "risk_level": "high" if found_pii else "safe",
                "exposure_risk": "high risk" if found_pii else "no risk"
            }
        
        severity_map = {
            "safe": AuditRisk.SAFE,
            "low": AuditRisk.LOW,
            "medium": AuditRisk.MEDIUM,
            "high": AuditRisk.HIGH,
            "critical": AuditRisk.CRITICAL
        }
        
        risk_level = analysis.get("risk_level", "safe")
        
        return AuditConcern(
            concern_type="pii_safety",
            severity=severity_map.get(risk_level, AuditRisk.MEDIUM),
            description=f"PII Detection: {analysis.get('exposure_risk', 'unknown')}",
            evidence=analysis.get("pii_types", found_pii),
            recommendation=analysis.get("recommendation", "Review data before execution"),
            confidence_score=0.9 if found_pii else 0.95
        )
    
    async def _check_conflicts(self, action: Dict, executor_agent: str,
                              context: str) -> AuditConcern:
        """
        Check for conflicts with previous actions.
        
        Detects:
        - Data consistency violations
        - Contradictions with previous decisions
        - Conflicting agent actions
        - State inconsistencies
        """
        
        logger.info("⚔️  Checking for Conflicts...")
        
        # Build conflict history
        previous_text = json.dumps(self.previous_actions, default=str)
        action_text = json.dumps(action)
        
        prompt = f"""
        Previous Actions (History):
        {previous_text}
        
        Current Proposed Action:
        {action_text}
        
        Context:
        {context}
        
        Check if the current action conflicts with or contradicts any previous actions.
        Look for:
        1. Data consistency violations
        2. Contradictory decisions
        3. Conflicting goals between agents
        4. State inconsistencies
        
        Respond with JSON:
        {{
            "has_conflicts": false,
            "conflict_types": [],
            "conflicting_actions": [],
            "severity": "safe|low|medium|high|critical",
            "resolution": "..."
        }}
        """
        
        try:
            response = await self.llm_service.call(prompt)
            analysis = parse_llm_json(response)
        except:
            analysis = {
                "has_conflicts": False,
                "conflict_types": [],
                "severity": "safe",
                "resolution": "No conflicts detected"
            }
        
        severity_map = {
            "safe": AuditRisk.SAFE,
            "low": AuditRisk.LOW,
            "medium": AuditRisk.MEDIUM,
            "high": AuditRisk.HIGH,
            "critical": AuditRisk.CRITICAL
        }
        
        return AuditConcern(
            concern_type="conflict_resolution",
            severity=severity_map.get(analysis.get("severity", "safe"), AuditRisk.MEDIUM),
            description=f"Conflict Check: {len(analysis.get('conflict_types', []))} issues found",
            evidence=analysis.get("conflicting_actions", []),
            recommendation=analysis.get("resolution", "Proceed carefully"),
            confidence_score=0.85
        )
    
    async def _assess_risk(self, action: Dict, reasoning: str) -> AuditConcern:
        """
        Assess the risk if this action is executed.
        
        Questions:
        - What's the worst-case scenario?
        - What's the financial impact?
        - What's the reputational impact?
        - Is there a way to undo this?
        """
        
        logger.info("⚠️  Assessing Risk...")
        
        prompt = f"""
        Proposed Action:
        {json.dumps(action)}
        
        Reasoning:
        {reasoning}
        
        Assess the risk of executing this action.
        Consider:
        1. Worst-case scenario
        2. Financial impact
        3. Reputational impact
        4. Reversibility (can it be undone?)
        5. Data loss potential
        6. Security implications
        
        Respond with JSON:
        {{
            "risk_level": "low|medium|high|critical",
            "worst_case": "...",
            "reversible": true/false,
            "mitigation_steps": ["step 1", "step 2"],
            "recommendation": "..."
        }}
        """
        
        try:
            response = await self.llm_service.call(prompt)
            analysis = parse_llm_json(response)
        except:
            analysis = {
                "risk_level": "medium",
                "worst_case": "Unknown risk",
                "reversible": True,
                "mitigation_steps": [],
                "recommendation": "Review manually before execution"
            }
        
        severity_map = {
            "low": AuditRisk.LOW,
            "medium": AuditRisk.MEDIUM,
            "high": AuditRisk.HIGH,
            "critical": AuditRisk.CRITICAL
        }
        
        return AuditConcern(
            concern_type="risk_assessment",
            severity=severity_map.get(analysis.get("risk_level", "medium"), AuditRisk.MEDIUM),
            description=analysis.get("worst_case", "Unknown risk scenario"),
            evidence=analysis.get("mitigation_steps", []),
            recommendation=analysis.get("recommendation", "Proceed with caution"),
            confidence_score=0.8
        )
    
    async def _validate_alternatives(self, action: Dict, 
                                     reasoning: str) -> AuditConcern:
        """
        Check if safer or more efficient alternatives exist.
        """
        
        logger.info("🔄 Validating Alternative Approaches...")
        
        prompt = f"""
        Proposed Action:
        {json.dumps(action)}
        
        Executor's Reasoning:
        {reasoning}
        
        Suggest safer or more efficient alternatives.
        
        Respond with JSON:
        {{
            "has_better_alternative": false,
            "alternatives": [
                {{"description": "...", "safety_improvement": "..."}}
            ],
            "recommendation": "..."
        }}
        """
        
        try:
            response = await self.llm_service.call(prompt)
            analysis = parse_llm_json(response)
        except:
            analysis = {
                "has_better_alternative": False,
                "alternatives": [],
                "recommendation": "Current approach is reasonable"
            }
        
        severity = AuditRisk.LOW if not analysis.get("has_better_alternative") else AuditRisk.MEDIUM
        
        return AuditConcern(
            concern_type="alternative_validation",
            severity=severity,
            description=f"Alternative Check: Found {len(analysis.get('alternatives', []))} options",
            evidence=[alt.get("description", "") for alt in analysis.get("alternatives", [])],
            recommendation=analysis.get("recommendation", "Proceed with current plan"),
            confidence_score=0.75
        )
    
    def _aggregate_risk_levels(self, risks: List[AuditRisk]) -> AuditRisk:
        """
        Aggregate multiple risk levels into a single overall risk.
        Takes the highest severity.
        """
        risk_hierarchy = {
            AuditRisk.CRITICAL: 5,
            AuditRisk.HIGH: 4,
            AuditRisk.MEDIUM: 3,
            AuditRisk.LOW: 2,
            AuditRisk.SAFE: 1
        }
        
        max_risk = max(risk_hierarchy.get(r, 0) for r in risks)
        
        for risk, value in risk_hierarchy.items():
            if value == max_risk:
                return risk
        
        return AuditRisk.MEDIUM
    
    def _make_decision(self, overall_risk: AuditRisk, 
                      concerns: List[AuditConcern]) -> tuple:
        """
        Make the final approval decision.
        
        Returns: (approval_status, recommendation, requires_human_review)
        """
        
        if overall_risk == AuditRisk.CRITICAL:
            return (
                "rejected",
                "❌ BLOCKED: Critical security/safety concerns. Do not execute.",
                True
            )
        
        elif overall_risk == AuditRisk.HIGH:
            return (
                "escalated",
                "⚠️  ESCALATED: High-risk action requires human approval",
                True
            )
        
        elif overall_risk == AuditRisk.MEDIUM:
            # Check if any concern has high confidence issues
            high_confidence_issues = [c for c in concerns if c.confidence_score > 0.8 
                                     and c.severity in [AuditRisk.HIGH, AuditRisk.CRITICAL]]
            
            if high_confidence_issues:
                return (
                    "conditional",
                    "⚠️  CONDITIONAL: Approve with warnings. Monitor execution.",
                    False
                )
            else:
                return (
                    "approved",
                    "✅ APPROVED: Risks are acceptable. Proceed with monitoring.",
                    False
                )
        
        elif overall_risk == AuditRisk.LOW:
            return (
                "approved",
                "✅ APPROVED: Low risk. Proceed normally.",
                False
            )
        
        else:  # SAFE
            return (
                "approved",
                "✅ APPROVED: No concerns detected. Proceed.",
                False
            )
    
    def get_audit_report(self, action_id: str) -> Optional[AuditReport]:
        """Retrieve audit report for an action"""
        for report in self.audit_history:
            if report.action_id == action_id:
                return report
        return None
    
    def get_audit_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent audit history"""
        return [
            {
                "action_id": r.action_id,
                "executor": r.executor_agent,
                "approval": r.approval_status,
                "risk_level": r.overall_risk.value,
                "timestamp": r.audited_at,
                "requires_human": r.human_review_required
            }
            for r in self.audit_history[-limit:]
        ]
