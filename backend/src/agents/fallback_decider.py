"""Deterministic fallback decider — used when the LLM decider fails."""

from __future__ import annotations

import logging

from .action_models import ActionDecision, AgentPlan
from .agent_state import AgentRuntimeState
from .policy import AgentPolicy

logger = logging.getLogger(__name__)


def fallback_decide(state: AgentRuntimeState) -> ActionDecision:
    """Deterministic state-driven fallback when LLM decision is unavailable."""
    if not state.indexed:
        return ActionDecision(
            action_name="ensure_index",
            action_input={},
            reason="[fallback] index_first",
            expected_result="index_ready",
            confidence=0.95,
        )
    if not state.retrieved_chunks:
        return ActionDecision(
            action_name="retrieve_context",
            action_input={},
            reason="[fallback] retrieve_first",
            expected_result="retrieve_evidence",
            confidence=0.9,
        )
    if not state.last_llm_raw or not state.accepted_risks:
        return ActionDecision(
            action_name="analyze_risks",
            action_input={},
            reason="[fallback] analyze_current_context",
            expected_result="risk_cards",
            confidence=0.85,
        )
    if state.evidence_verification_passed is None:
        return ActionDecision(
            action_name="verify_evidence",
            action_input={},
            reason="[fallback] verify_evidence",
            expected_result="evidence_check",
            confidence=0.8,
        )
    if state.evidence_verification_passed and not state.finished:
        return ActionDecision(
            action_name="finish",
            action_input={},
            reason="[fallback] finish",
            expected_result="finish",
            confidence=0.85,
        )
    return ActionDecision(
        action_name="degrade_output",
        action_input={"reason": "fallback_exhausted"},
        reason="[fallback] degrade",
        expected_result="degraded_output",
        confidence=0.5,
    )


async def decide_fallback(
    *,
    state: AgentRuntimeState,
    policy: AgentPolicy,
    **kwargs,
) -> ActionDecision:
    """Deterministic fallback when LLM decider fails."""
    try:
        return fallback_decide(state)
    except Exception:
        logger.exception("[FALLBACK_DECIDER] fallback failed")
        return ActionDecision(
            action_name="degrade_output",
            action_input={"reason": "fallback_error"},
            reason="[fallback] exception",
            confidence=0.3,
        )
