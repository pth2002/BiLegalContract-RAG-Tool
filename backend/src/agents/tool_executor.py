"""工具执行器：统一入口、异常兜底、结构化日志（供 Agent Runtime 调用）。"""

from __future__ import annotations
 
import logging

from .action_models import ActionDecision, ToolExecutionResult
from .agent_state import AgentRuntimeState
from .executor import execute_decision as _execute_decision_impl
from .policy import AgentPolicy

logger = logging.getLogger(__name__)


async def execute(
    decision: ActionDecision,
    state: AgentRuntimeState,
    policy: AgentPolicy,
    *,
    step_index: int | None = None,
) -> ToolExecutionResult:
    """
    执行已校验的决策；与 `executor.execute_decision` 等价，并输出调试日志。
    """
    prefix = f"[STEP {step_index}] " if step_index is not None else ""
    logger.info(
        "%stool=%s conf=%.2f reason=%s",
        prefix,
        decision.action_name,
        decision.confidence,
        (decision.reason or "")[:200],
    )
    result = await _execute_decision_impl(decision, state, policy)
    logger.info(
        "%sexec tool=%s ok=%s err=%s",
        prefix,
        result.tool_name,
        result.ok,
        (result.error or "")[:120],
    )
    return result
