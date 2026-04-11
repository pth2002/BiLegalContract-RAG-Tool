"""Execute validated tool calls and return standardized results."""

from __future__ import annotations

import logging
import traceback

from .action_models import ActionDecision, ToolExecutionResult
from .agent_state import AgentRuntimeState
from .policy import AgentPolicy
from .tool_registry import list_tool_names, run_tool

logger = logging.getLogger(__name__)

ALLOWED = set(list_tool_names())


async def execute_decision(
    decision: ActionDecision,
    state: AgentRuntimeState,
    policy: AgentPolicy,
) -> ToolExecutionResult:
    if decision.action_name not in ALLOWED:
        return ToolExecutionResult(
            ok=False,
            tool_name=decision.action_name,
            payload={},
            error=f"invalid_tool:{decision.action_name}",
        )
    try:
        payload = await run_tool(decision.action_name, state, policy, decision.action_input or {})
        return ToolExecutionResult(ok=True, tool_name=decision.action_name, payload=payload, error=None)
    except Exception as e:
        logger.exception("[EXECUTOR] tool failed: %s", decision.action_name)
        return ToolExecutionResult(
            ok=False,
            tool_name=decision.action_name,
            payload={},
            error=f"{e}\n{traceback.format_exc()[:500]}",
        )
