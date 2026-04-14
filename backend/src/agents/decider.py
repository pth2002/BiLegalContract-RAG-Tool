"""LLM-based action selection with JSON schema validation and policy fallbacks.""" 

from __future__ import annotations

import json
import logging
from typing import Any

from json_repair import repair_json

from ..config import (
    get_llm_num_ctx,
    get_llm_num_predict,
    get_llm_reasoning,
    get_llm_temperature,
    get_ollama_model,
)
from ..services.ollama_service import get_ollama_client
from .action_models import ActionDecision, AgentPlan
from .agent_state import AgentRuntimeState
from .planner import current_plan_step
from .plan_constraints import allowed_tools_for_current_step, clamp_action_to_allowed
from .policy import AgentPolicy
from .tool_registry import get_tool_description_map, list_tool_names

logger = logging.getLogger(__name__)

ALLOWED = set(list_tool_names())


def resolve_open_tool(name: str | None, *, open_v3: bool | None = None) -> str | None:
    """将 LLM 输出的工具名映射到注册表；始终启用模糊匹配。"""
    if not name:
        return None
    n = str(name).strip()
    if n in ALLOWED:
        return n
    nl = n.lower().replace(" ", "_").replace("-", "_")
    for a in sorted(ALLOWED):
        al = a.lower()
        if al in nl or nl in al or al.replace("_", "") in nl:
            return a
    return "retrieve_context"


def _memory_block(state: AgentRuntimeState) -> str:
    vm = state.meta.get("vector_memory")
    if vm is None or not hasattr(vm, "search"):
        return "(无向量记忆)"
    try:
        step = current_plan_step(state.plan, state.current_step_index) if state.plan else None
        q = f"{state.request.perspective.value} 合同 风险"
        if step:
            q += f" {step.goal[:120]}"
        hits = vm.search(q, top_k=6)
    except Exception:
        return "(记忆检索失败)"
    if not hits:
        return "(暂无匹配历史经验)"
    lines = []
    for h in hits:
        kind = h.get("kind", "?")
        text = str(h.get("text", ""))[:220]
        lines.append(f"- [{kind}] {text}")
    return "\n".join(lines)


def _strategy_block(state: AgentRuntimeState) -> str:
    """从 vector_memory 检索策略建议，注入 decider prompt。"""
    vm = state.meta.get("vector_memory")
    if vm is None or not hasattr(vm, "search_strategies"):
        return ""
    try:
        q = f"{state.request.perspective.value} {state.current_goal or state.primary_goal}"
        hits = vm.search_strategies(q, top_k=4)
    except Exception:
        return ""
    if not hits:
        return ""
    lines = ["【策略经验】"]
    for h in hits:
        lines.append(f"  - {str(h.get('text', ''))[:250]}")
    return "\n".join(lines)


def _summarize_state(state: AgentRuntimeState) -> dict[str, Any]:
    step = state.plan.steps[state.current_step_index] if state.plan and state.current_step_index < len(state.plan.steps) else None
    return {
        "indexed": state.indexed,
        "retrieved_count": len(state.retrieved_chunks),
        "risk_count": len(state.accepted_risks),
        "has_llm_output": bool(state.last_llm_raw),
        "degraded": state.degraded,
        "warnings_count": len(state.warnings),
        "current_plan_step": step.id if step else None,
        "current_plan_title": step.title if step else None,
        "budget": {
            "loop": state.budget.loop_iterations,
            "retrieval": state.budget.retrieval_calls,
            "refine": state.budget.refine_calls,
            "llm": state.budget.llm_calls,
            "replan": state.budget.replan_rounds,
        },
    }


def _fallback_decision(state: AgentRuntimeState, plan: AgentPlan) -> ActionDecision:
    """Deterministic policy when LLM planner fails or confidence is low."""
    if not state.indexed:
        return ActionDecision(action_name="ensure_index", reason="必须先完成索引", confidence=0.95)
    if not state.retrieved_chunks:
        return ActionDecision(action_name="retrieve_context", reason="尚无检索上下文", confidence=0.9)
    if not state.last_llm_raw or not state.accepted_risks:
        return ActionDecision(action_name="analyze_risks", reason="需要生成结构化风险", confidence=0.85)
    if state.evidence_verification_passed is None:
        return ActionDecision(action_name="verify_evidence", reason="需要证据对齐", confidence=0.8)
    if state.evidence_verification_passed and not state.finished:
        return ActionDecision(action_name="finish", reason="验收通过，结束", confidence=0.85)
    return ActionDecision(action_name="degrade_output", action_input={"reason": "无法推进"}, reason="兜底降级", confidence=0.5)


def parse_action_decision(raw: str, state: AgentRuntimeState | None = None) -> ActionDecision | None:
    start, end = raw.find("{"), raw.rfind("}")
    candidate = raw[start : end + 1] if start != -1 and end > start else raw
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        try:
            repaired = repair_json(candidate, ensure_ascii=False)
            data = json.loads(repaired)
        except Exception:
            return None

    # v3：融合 Planner+Decider — 写入 meta
    if state is not None:
        if isinstance(data.get("plan"), list):
            state.meta["fused_plan"] = [str(x)[:200] for x in data["plan"][:16]]
        if data.get("current_step") is not None:
            try:
                state.meta["fused_current_step"] = int(data["current_step"])
            except (TypeError, ValueError):
                pass

    raw_name = data.get("action_name") or data.get("tool") or data.get("next_action")
    name = resolve_open_tool(str(raw_name) if raw_name else None)
    if not name:
        return None

    conf = float(data.get("confidence", 0.5))
    conf = max(0.0, min(1.0, conf))
    inp = data.get("action_input")
    if inp is None and isinstance(data.get("input"), dict):
        inp = data.get("input")
    if inp is None:
        inp = {}
    reason = str(data.get("reason") or data.get("why") or "")
    alt_plan = str(data.get("alt_plan", "") or "")[:2000]

    tool_chain: list[dict[str, Any]] = []
    chain_raw = data.get("tools") or data.get("tool_chain")
    if isinstance(chain_raw, list):
        for item in chain_raw:
            if not isinstance(item, dict):
                continue
            tn = resolve_open_tool(item.get("tool") or item.get("action_name"))
            if tn:
                tinp = item.get("input") if isinstance(item.get("input"), dict) else item.get("action_input")
                tool_chain.append({"tool": tn, "input": tinp if isinstance(tinp, dict) else {}})

    if raw_name and str(raw_name).strip() not in ALLOWED and name in ALLOWED:
        inp = {**inp, "_llm_tool_alias": str(raw_name)[:120]}

    thought = str(data.get("thought", "") or data.get("reasoning", ""))[:2000]

    return ActionDecision(
        action_name=name,
        action_input=inp if isinstance(inp, dict) else {},
        reason=reason,
        expected_result=str(data.get("expected_result", "")),
        confidence=conf,
        alt_plan=alt_plan,
        tool_chain=tool_chain,
        thought=thought,
    )


async def decide_next_action(
    *,
    state: AgentRuntimeState,
    policy: AgentPolicy,
    plan: AgentPlan,
    recent_history: list[dict[str, Any]],
) -> ActionDecision:
    """Ask LLM to choose next tool; validate and clamp to allowed set."""
    client = get_ollama_client()
    model = get_ollama_model()
    tools = get_tool_description_map()
    summary = _summarize_state(state)
    allowed = allowed_tools_for_current_step(state, plan)

    sys_msg = (
        "你是合同审查 Agent 的完全自治决策器。可跳过检索直接 analyze，可多次 refine，可输出备选方案说明。\n"
        f"注册工具名：{sorted(ALLOWED)}（也可使用近义名，系统会映射）。\n"
        "输出一个 JSON，可含：next_action 或 tool, input, why, confidence, alt_plan(备选思路字符串),\n"
        "tools: [ {\"tool\":\"...\",\"input\":{} }, ... ] 表示本步内多工具顺序（最多执行前 3 个）,\n"
        "plan: [\"步骤1\",\"步骤2\",...], current_step: 整数 — 用于动态跟踪多步分析。\n"
        "结合「历史经验」与「终局目标」做决策。"
    )
    sys_msg += (
        "\n【ReAct】必须先输出 thought（字符串）：显式推理当前状态与为何选下一动作；\n"
        "再输出 next_action/tool 等字段。"
    )
    sys_msg += (
        "\n【推理链】当你需要多步工具配合时，必须在 thought 中显式说明推理过程，"
        "例如：'当前检索信息不足关于终止条款→需要扩大检索→然后再分析'。\n"
        "tools 字段应严格反映你的推理链条。"
    )
    if allowed is not None:
        sys_msg += (
            f"\n【当前计划步约束】本步仅允许使用以下工具（必须从中选择）：{sorted(allowed)}。\n"
            "不得选择列表外工具。"
        )
    fused = state.meta.get("fused_plan")
    fused_hint = ""
    if isinstance(fused, list) and fused:
        fused_hint = f"\n融合计划轨迹（LLM）：{json.dumps(fused, ensure_ascii=False)}，current_step={state.meta.get('fused_current_step')}\n"

    cur_step = current_plan_step(plan, state.current_step_index)
    step_hint = ""
    if cur_step:
        step_hint = f"\n【当前计划步】id={cur_step.id} goal={cur_step.goal}\n"

    goal_line = f"【终局目标】{state.primary_goal}"
    if state.current_goal:
        goal_line += f"\n【当前子目标】{state.current_goal}（{state.current_goal_index + 1}/{len(state.sub_goals)}）"
    strat_block = _strategy_block(state)
    latest_strat = state.latest_strategy
    strat_hint = f"\n最近策略建议：{latest_strat}\n" if latest_strat else ""
    user_msg = (
        f"{goal_line}\n"
        f"{step_hint}"
        f"工具说明：{json.dumps(tools, ensure_ascii=False)}\n"
        f"当前计划版本 {plan.version}，步骤索引 {state.current_step_index}。\n"
        f"{fused_hint}"
        f"状态摘要：{json.dumps(summary, ensure_ascii=False)}\n"
        f"历史经验（向量记忆检索）：\n{_memory_block(state)}\n"
        f"{strat_block}\n"
        f"{strat_hint}"
        f"最近动作摘要：{json.dumps(recent_history[-5:], ensure_ascii=False)}\n"
        "选择下一步。"
    )
    try:
        response = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg},
            ],
            stream=False,
            options={
                "temperature": min(get_llm_temperature(), 0.25),
                "num_ctx": get_llm_num_ctx(),
                "num_predict": min(get_llm_num_predict(), 384),
                "reasoning": get_llm_reasoning(),
            },
        )
        raw = response["message"]["content"].strip()
        decision = parse_action_decision(raw, state)
        if decision is None:
            raise ValueError("parse failed")
        if allowed is not None and decision.action_name not in allowed:
            old = decision.action_name
            decision.action_name = clamp_action_to_allowed(decision.action_name, allowed)
            decision.reason = f"{decision.reason} [v4_clamp:{old}->{decision.action_name}]"
            logger.warning("[DECIDER] clamped action %s → %s", old, decision.action_name)
        if allowed is not None and decision.tool_chain:
            decision.tool_chain = [x for x in decision.tool_chain if x.get("tool") in allowed]
        if decision.confidence < policy.min_decider_confidence:
            logger.warning("[DECIDER] Low confidence %.2f, using fallback", decision.confidence)
            return _fallback_decision(state, plan)
        return decision
    except Exception as e:
        logger.warning("[DECIDER] LLM decision failed: %s, fallback", e)
        return _fallback_decision(state, plan)
