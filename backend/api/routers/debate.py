import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException

from backend.api import state

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/actions/vibe-check", tags=["Vibe-Checking"])
async def vibe_check_action(
    executor_agent: str,
    action: Dict[str, Any],
    reasoning: str,
    context: str = "",
):
    logger.info(f"🔍 Vibe-checking action from {executor_agent}")
    audit_report = await state.security_auditor.audit_action(
        executor_agent=executor_agent,
        action=action,
        reasoning=reasoning,
        previous_context=context,
    )
    return {
        "vibe_check_id":       audit_report.action_id,
        "executor":            executor_agent,
        "approval_status":     audit_report.approval_status,
        "overall_risk":        audit_report.overall_risk.value,
        "Human review required": audit_report.human_review_required,
        "audit_findings": {
            "intent_alignment": {
                "status": audit_report.intent_alignment.severity.value,
                "reason": audit_report.intent_alignment.description,
            },
            "pii_safety": {
                "status":   audit_report.pii_safety.severity.value,
                "evidence": audit_report.pii_safety.evidence,
            },
            "conflict_resolution": {
                "status":          audit_report.conflict_resolution.severity.value,
                "conflicts_found": len(audit_report.conflict_resolution.evidence),
            },
            "risk_assessment": {
                "risk_level": audit_report.risk_assessment.severity.value,
                "worst_case": audit_report.risk_assessment.description,
            },
            "alternative_validation": {
                "better_alternatives_exist": len(audit_report.alternative_validation.evidence) > 0,
            },
        },
        "recommendation": audit_report.final_recommendation,
        "next_steps": (
            "APPROVED - Proceed"               if audit_report.approval_status == "approved"
            else "ESCALATED - Awaiting human review" if audit_report.approval_status == "escalated"
            else "CONDITIONAL - Proceed with caution" if audit_report.approval_status == "conditional"
            else "REJECTED - Do not execute"
        ),
    }


@router.post("/debate/initiate", tags=["Multi-Agent Debate"])
async def initiate_agent_debate(
    action: Dict[str, Any],
    executor_agent: str = "executor",
    reasoning: str = "",
    issue_context: str = "High-stakes decision requiring team consensus",
):
    logger.info(f"🗣️  Initiating debate about: {action.get('name', 'Unknown')}")
    debate_session = await state.debate_engine.debate_high_stakes_action(
        action=action,
        executor_agent=executor_agent,
        executor_reasoning=reasoning,
        issue_context=issue_context,
    )
    debate_summary = state.debate_engine.get_debate_summary(debate_session.debate_id)
    return {
        "debate_id":      debate_session.debate_id,
        "message":        "🗣️ Multi-agent debate completed",
        "summary":        debate_summary,
        "final_decision": (
            f"{'✅ CONSENSUS REACHED' if debate_session.consensus_reached else '⚠️ No consensus'} "
            f"(Team Confidence: {debate_session.confidence_score:.0%})"
        ),
    }


@router.get("/debate/{debate_id}", tags=["Multi-Agent Debate"])
async def get_debate_details(debate_id: str):
    debate_summary = state.debate_engine.get_debate_summary(debate_id)
    if not debate_summary:
        raise HTTPException(status_code=404, detail="Debate not found")
    return debate_summary

@router.get("/debate-history", tags=["Multi-Agent Debate"])
async def get_debate_history(limit: int = 10):
    debates = []
    for d_id, debate in reversed(list(state.debate_engine.debates.items())):
        summary = state.debate_engine.get_debate_summary(d_id)
        if summary:
            debates.append(summary)
        if len(debates) >= limit:
            break
    return {
        "recent_debates": debates,
        "total_debates_conducted": len(state.debate_engine.debates),
    }


@router.get("/vibe-check/{check_id}", tags=["Vibe-Checking"])
async def get_vibe_check_report(check_id: str):
    report = state.security_auditor.get_audit_report(check_id)
    if not report:
        raise HTTPException(status_code=404, detail="Vibe-check report not found")
    return {
        "check_id":              report.action_id,
        "executor":              report.executor_agent,
        "status":                report.approval_status,
        "overall_risk":          report.overall_risk.value,
        "audit_concerns": {
            "intent_alignment": {
                "severity":       report.intent_alignment.severity.value,
                "description":    report.intent_alignment.description,
                "recommendation": report.intent_alignment.recommendation,
            },
            "pii_safety": {
                "severity":       report.pii_safety.severity.value,
                "pii_found":      report.pii_safety.evidence,
                "recommendation": report.pii_safety.recommendation,
            },
            "conflict_resolution": {
                "severity":       report.conflict_resolution.severity.value,
                "conflicts":      report.conflict_resolution.evidence,
                "recommendation": report.conflict_resolution.recommendation,
            },
            "risk_assessment": {
                "severity":            report.risk_assessment.severity.value,
                "worst_case_scenario": report.risk_assessment.description,
                "mitigation_steps":    report.risk_assessment.evidence,
            },
            "alternative_validation": {
                "severity":          report.alternative_validation.severity.value,
                "alternatives_found":report.alternative_validation.evidence,
                "recommendation":    report.alternative_validation.recommendation,
            },
        },
        "recommendation":        report.final_recommendation,
        "human_review_required": report.human_review_required,
        "audit_duration_ms":     report.audit_duration_ms,
    }


@router.get("/audit-history", tags=["Vibe-Checking"])
async def get_audit_history(limit: int = 10):
    return {
        "recent_audits":           state.security_auditor.get_audit_history(limit),
        "total_audits_conducted":  len(state.security_auditor.audit_history),
    }
