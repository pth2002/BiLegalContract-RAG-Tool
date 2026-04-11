"""Policy-constrained replanning: template fallback + v5 LLM-based replan_from_state."""

from __future__ import annotations

import json
import logging

from ..config import (
    get_llm_num_ctx,
    get_llm_num_predict,
    get_llm_reasoning,
    get_llm_temperature,
    get_ollama_model,
)
from ..services.ollama_service import get_ollama_client
from .action_models import AgentPlan, PlanStep, PlanStepStatus
from .agent_state import AgentRuntimeState
from .planner import infer_allowed_tools_from_goal
from .policy import AgentPolicy

logger = logging.getLogger(__name__)

_JSON_RETRIES = 2


def _template_replan(state: AgentRuntimeState, plan: AgentPlan, reason: str) -> AgentPlan:
    """Reset plan step progression with version bump; bounded by policy."""
    plan.version += 1
    plan.notes = (plan.notes + f" | replan_v{plan.version}:{reason}")[:2000]
    state.current_step_index = 0
    for s in plan.steps:
        s.status = PlanStepStatus.PENDING
        s.attempts = 0
    if plan.steps:
        plan.steps[0].status = PlanStepStatus.IN_PROGRESS
    return plan


async def _llm_replan(state: AgentRuntimeState, plan: AgentPlan, reason: str) -> AgentPlan:
    """
    v5：LLM 基于当前进度 + 失败历史生成全新 plan。
    失败回退到 template_replan。
    """
    client = get_ollama_client()
    model = get_ollama_model()

    done_steps = [s.id for s in plan.steps if s.status == PlanStepStatus.DONE]
    failed_steps = [s.id for s in plan.steps if s.status == PlanStepStatus.FAILED]
    recent_warnings = state.warnings[-5:]

    sys_msg = (
        "你是合同审查重规划师。当前计划执行失败/卡住，需要生成一个更优的新计划。\n"
        "只输出 JSON：{\"steps\":[{\"id\":\"r1\",\"goal\":\"...\"},...],\"strategy\":\"...\"}\n"
        "strategy 字段说明你为什么选择这个新方案（一句话）。至少 3 步。"
    )
    user_msg = (
        f"终局目标：{state.primary_goal}\n"
        f"当前子目标：{state.current_goal or '(无)'}\n"
        f"旧计划版本={plan.version}，已完成步骤={done_steps}，失败步骤={failed_steps}\n"
        f"失败原因：{reason}\n"
        f"最近警告：{recent_warnings}\n"
        f"已检索片段数：{len(state.retrieved_chunks)}，已接受风险数：{len(state.accepted_risks)}\n"
        "请生成新计划。"
    )
    for attempt in range(1, _JSON_RETRIES + 1):
        try:
            response = client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user_msg},
                ],
                stream=False,
                options={
                    "temperature": min(get_llm_temperature(), 0.35),
                    "num_ctx": get_llm_num_ctx(),
                    "num_predict": min(get_llm_num_predict(), 640),
                    "reasoning": get_llm_reasoning(),
                },
            )
            raw = response["message"]["content"].strip()
            start, end = raw.find("{"), raw.rfind("}")
            if start == -1 or end <= start:
                raise ValueError("no json")
            data = json.loads(raw[start : end + 1])
            raw_steps = data.get("steps")
            strategy = str(data.get("strategy", ""))[:500]
            if not isinstance(raw_steps, list) or len(raw_steps) < 2:
                raise ValueError("insufficient steps")

            steps: list[PlanStep] = []
            for i, item in enumerate(raw_steps[:10]):
                sid = str(item.get("id", f"r{i+1}") if isinstance(item, dict) else f"r{i+1}")[:32]
                g = str(item.get("goal", item) if isinstance(item, dict) else item)[:500]
                allowed = infer_allowed_tools_from_goal(g)
                steps.append(
                    PlanStep(
                        id=sid,
                        title=g[:120],
                        goal=g,
                        preferred_tools=list(allowed),
                        allowed_tools=list(allowed),
                        success_criteria="完成本步目标或触发降级",
                        max_attempts=4,
                        status=PlanStepStatus.IN_PROGRESS if i == 0 else PlanStepStatus.PENDING,
                    )
                )
            new_plan = AgentPlan(
                steps=steps,
                version=plan.version + 1,
                notes=f"llm_replan | reason={reason[:200]} | strategy={strategy}",
            )
            state.current_step_index = 0
            logger.info("[REPLANNER] LLM replan: %d steps, strategy=%s", len(steps), strategy[:120])
            return new_plan
        except Exception as e:
            logger.warning("[REPLANNER] LLM replan attempt %d/%d: %s", attempt, _JSON_RETRIES, e)

    logger.warning("[REPLANNER] LLM replan failed → template fallback")
    return _template_replan(state, plan, reason)


def maybe_replan(
    *,
    state: AgentRuntimeState,
    plan: AgentPlan,
    policy: AgentPolicy,
    reason: str,
) -> AgentPlan:
    """Synchronous entry: always uses template reset. See `maybe_replan_async` for LLM path."""
    if state.budget.replan_rounds >= policy.max_replan_rounds:
        logger.warning("[REPLANNER] max replan rounds reached: %s", reason)
        return plan
    state.budget.replan_rounds += 1
    state.warnings.append(f"已重规划（第{state.budget.replan_rounds}次）: {reason}")
    return _template_replan(state, plan, reason)


async def maybe_replan_async(
    *,
    state: AgentRuntimeState,
    plan: AgentPlan,
    policy: AgentPolicy,
    reason: str,
) -> AgentPlan:
    """异步重规划：LLM 基于当前状态生成全新计划，失败时降级到模板重置。"""
    if state.budget.replan_rounds >= policy.max_replan_rounds:
        logger.warning("[REPLANNER] max replan rounds reached: %s", reason)
        return plan
    state.budget.replan_rounds += 1
    state.warnings.append(f"已重规划（第{state.budget.replan_rounds}次）: {reason}")
    return await _llm_replan(state, plan, reason)
