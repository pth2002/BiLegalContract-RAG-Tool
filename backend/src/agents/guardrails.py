"""Runtime guardrails: input sanitization, budget caps, confidence floors."""

from __future__ import annotations

import logging
from typing import Any

from ..config import (
    get_agent_guard_max_tool_input_chars,
    get_agent_guard_min_confidence,
    get_agent_max_tool_calls,
)
from .action_models import ActionDecision
from .agent_state import AgentRuntimeState
from .policy import AgentPolicy

logger = logging.getLogger(__name__)

_RETRIEVAL_TOOLS = frozenset({"retrieve_context", "widen_retrieval"})
_HIGH_IMPACT = frozenset({"finish", "analyze_risks"})


def _clamp_str(s: str, max_chars: int) -> str:
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 3] + "..."


def _clamp_value(val: Any, max_chars: int, depth: int) -> Any:
    if depth <= 0:
        return val
    if isinstance(val, str):
        return _clamp_str(val, max_chars)
    if isinstance(val, dict):
        return {str(k)[:128]: _clamp_value(v, max_chars, depth - 1) for k, v in list(val.items())[:64]}
    if isinstance(val, list):
        return [_clamp_value(v, max_chars, depth - 1) for v in val[:128]]
    return val


def sanitize_decision_inputs(decision: ActionDecision, max_chars: int | None = None) -> ActionDecision:
    """Truncate oversized strings in tool inputs (prompt injection / memory blowup)."""
    lim = max_chars if max_chars is not None else get_agent_guard_max_tool_input_chars()
    return decision.model_copy(
        update={
            "action_input": _clamp_value(decision.action_input or {}, lim, 8),
            "tool_chain": [
                {
                    **item,
                    "input": _clamp_value(item.get("input") or {}, lim, 6),
                }
                if isinstance(item, dict)
                else item
                for item in (decision.tool_chain or [])[:8]
            ],
        }
    )


def apply_runtime_guardrails(
    decision: ActionDecision,
    policy: AgentPolicy,
    state: AgentRuntimeState,
) -> tuple[ActionDecision, list[str]]:
    """Return possibly overridden decision and human-readable guard notes."""
    notes: list[str] = []
    d = sanitize_decision_inputs(decision)

    if state.budget.tool_calls >= get_agent_max_tool_calls():
        logger.warning("[GUARD] max tool calls exceeded → degrade_output")
        notes.append("护栏：已达最大工具调用次数，强制降级结束")
        return (
            ActionDecision(
                action_name="degrade_output",
                action_input={"reason": "guard_max_tool_calls"},
                reason="guard_max_tool_calls",
                expected_result="degraded",
                confidence=1.0,
                thought="(护栏)",
            ),
            notes,
        )

    if d.action_name in _RETRIEVAL_TOOLS and state.budget.retrieval_calls >= policy.max_retrieval_rounds:
        if state.retrieved_chunks:
            logger.info("[GUARD] retrieval rounds exhausted → analyze_risks")
            notes.append("护栏：检索轮次已达上限，改为基于已有上下文生成分析")
            return (
                ActionDecision(
                    action_name="analyze_risks",
                    action_input={},
                    reason="guard_max_retrieval_rounds",
                    expected_result="risks",
                    confidence=max(d.confidence, 0.5),
                    thought=d.thought or "(护栏：检索预算)",
                ),
                notes,
            )
        logger.info("[GUARD] retrieval rounds exhausted, no chunks → summarize_partial")
        notes.append("护栏：检索轮次用尽且无上下文，输出部分摘要")
        return (
            ActionDecision(
                action_name="summarize_partial",
                action_input={},
                reason="guard_max_retrieval_no_chunks",
                expected_result="summary",
                confidence=0.5,
                thought=d.thought or "(护栏)",
            ),
            notes,
        )

    floor = get_agent_guard_min_confidence()
    if d.confidence < floor:
        if d.action_name == "finish" and not state.accepted_risks:
            logger.info("[GUARD] low confidence finish with no risks → analyze_risks")
            notes.append("护栏：finish 置信度过低且无已接受风险，改为继续分析")
            return (
                ActionDecision(
                    action_name="analyze_risks",
                    action_input={},
                    reason="guard_low_confidence_finish",
                    expected_result="risks",
                    confidence=0.55,
                    thought=d.thought or "(护栏)",
                ),
                notes,
            )
        if d.action_name in _HIGH_IMPACT and not state.retrieved_chunks and d.action_name != "degrade_output":
            logger.info("[GUARD] low confidence high-impact without retrieval → retrieve_context")
            notes.append("护栏：高影响动作前缺少检索上下文，强制检索")
            return (
                ActionDecision(
                    action_name="retrieve_context",
                    action_input={},
                    reason="guard_require_context",
                    expected_result="chunks",
                    confidence=0.55,
                    thought=d.thought or "(护栏)",
                ),
                notes,
            )

    return d, notes
