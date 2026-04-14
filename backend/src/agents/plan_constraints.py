"""v4：按计划当前步约束允许工具，将随机决策变为有路径的决策。"""
 
from __future__ import annotations

from .action_models import AgentPlan, PlanStep
from .agent_state import AgentRuntimeState
from .tool_registry import list_tool_names

_REGISTERED = frozenset(list_tool_names())


def effective_allowed_tools(step: PlanStep) -> list[str]:
    """优先 allowed_tools，否则 preferred_tools。"""
    raw = step.allowed_tools if step.allowed_tools else step.preferred_tools
    return [t for t in raw if t in _REGISTERED]


def allowed_tools_for_current_step(state: AgentRuntimeState, plan: AgentPlan | None) -> set[str] | None:
    """
    返回当前计划步允许的工具集合；若无计划或步为空则 None（表示不额外约束）。
    """
    if not plan or not plan.steps:
        return None
    idx = state.current_step_index
    if idx < 0 or idx >= len(plan.steps):
        return None
    eff = effective_allowed_tools(plan.steps[idx])
    s = set(eff) & _REGISTERED
    return s if s else None


def clamp_action_to_allowed(action_name: str, allowed: set[str]) -> str:
    """将动作限制在允许集合内（保持确定性顺序）。"""
    if action_name in allowed:
        return action_name
    priority = [
        "ensure_index",
        "retrieve_context",
        "widen_retrieval",
        "refine_query",
        "extract_clauses",
        "analyze_risks",
        "retry_generation_strict",
        "summarize_partial",
        "verify_evidence",
        "finish",
        "degrade_output",
    ]
    for p in priority:
        if p in allowed:
            return p
    return next(iter(allowed))
