"""Critique layer: combine rule-based evaluators with runtime verdicts + v5 strategy.""" 

from __future__ import annotations

import json
import logging

from ..config import (
    get_agent_v5_step_fail_replan_threshold,
    get_llm_num_ctx,
    get_llm_num_predict,
    get_llm_reasoning,
    get_llm_temperature,
    get_ollama_model,
)
from ..services.ollama_service import get_ollama_client
from .action_models import CriticNextHint, CriticVerdict, ToolExecutionResult
from .agent_state import AgentRuntimeState
from .evaluators import evaluate_generation, evaluate_retrieval
from .llm_gates import llm_judge_retrieval_sufficient
from .policy import AgentPolicy
from .planner import current_plan_step
from .risk_parsing import parse_risk_json

logger = logging.getLogger(__name__)


def _should_request_replan(state: AgentRuntimeState) -> bool:
    """Escalate to explicit replan when the current step is about to hit fail threshold."""
    if not state.plan:
        return False
    step = current_plan_step(state.plan, state.current_step_index)
    if not step:
        return False
    threshold = max(1, get_agent_v5_step_fail_replan_threshold())
    return (step.attempts + 1) >= threshold


def critique_after_tool(
    *,
    state: AgentRuntimeState,
    policy: AgentPolicy,
    tool_name: str,
    execution: ToolExecutionResult,
) -> CriticVerdict:
    """Evaluate one tool execution; drive retry / replan / degrade hints."""
    rule_summary: dict = {"tool": tool_name, "ok": execution.ok}

    if not execution.ok:
        hint = CriticNextHint.REPLAN if _should_request_replan(state) else CriticNextHint.RETRY
        return CriticVerdict(
            acceptable=False,
            plan_step_complete=False,
            next_hint=hint,
            critique_notes=execution.error or "tool_error",
            rule_verdict_summary=rule_summary,
        )

    # --- Retrieval family ---
    if tool_name in ("retrieve_context", "widen_retrieval"):
        rv = evaluate_retrieval(
            chunks=state.retrieved_chunks,
            perspective=state.request.perspective,
            options=state.request.options,
            policy_min_chunks_ok=policy.min_chunks_ok,
            policy_min_chunks_relaxed=policy.min_chunks_relaxed,
            policy_min_avg=policy.min_avg_score_ok,
            policy_min_max=policy.min_max_score_ok,
            policy_min_focus_ratio=policy.min_focus_coverage_ratio,
        )
        rule_summary["retrieval"] = rv.metrics
        if rv.passed:
            return CriticVerdict(
                acceptable=True,
                plan_step_complete=True,
                next_hint=CriticNextHint.PROCEED,
                critique_notes=f"retrieval_{rv.quality}",
                rule_verdict_summary=rule_summary,
            )
        hint = CriticNextHint.REPLAN if _should_request_replan(state) else CriticNextHint.RETRY
        if rv.suggested_action == "widen_retrieval" and state.budget.refine_calls < policy.max_refine_rounds:
            hint = CriticNextHint.REPLAN if _should_request_replan(state) else CriticNextHint.RETRY
        return CriticVerdict(
            acceptable=False,
            plan_step_complete=False,
            next_hint=hint,
            critique_notes=f"retrieval_poor:{rv.suggested_action}",
            rule_verdict_summary=rule_summary,
        )

    if tool_name == "refine_query":
        return CriticVerdict(
            acceptable=True,
            plan_step_complete=False,
            next_hint=CriticNextHint.PROCEED,
            critique_notes="query_refined",
            rule_verdict_summary=rule_summary,
        )

    if tool_name == "ensure_index":
        return CriticVerdict(
            acceptable=True,
            plan_step_complete=True,
            next_hint=CriticNextHint.PROCEED,
            critique_notes="indexed",
            rule_verdict_summary=rule_summary,
        )

    # --- Generation ---
    if tool_name in ("analyze_risks", "retry_generation_strict"):
        parsed = parse_risk_json(state.last_llm_raw)
        if not parsed and state.accepted_risks:
            parsed = [risk.model_dump(mode="json") for risk in state.accepted_risks]
        gv = evaluate_generation(
            raw_text=state.last_llm_raw,
            parsed_risks=parsed,
            policy_min_risks=policy.min_risks_accept,
            policy_min_complete_ratio=policy.min_complete_risks_ratio,
        )
        rule_summary["generation"] = {
            "risk_count": gv.risk_count,
            "complete_ratio": gv.complete_ratio,
            "json_ok": gv.json_parse_ok,
        }
        if gv.passed:
            return CriticVerdict(
                acceptable=True,
                plan_step_complete=True,
                next_hint=CriticNextHint.PROCEED,
                critique_notes="generation_ok",
                rule_verdict_summary=rule_summary,
            )
        if gv.suggested_action == "retry_strict":
            hint = CriticNextHint.REPLAN if _should_request_replan(state) else CriticNextHint.RETRY
            return CriticVerdict(
                acceptable=False,
                plan_step_complete=False,
                next_hint=hint,
                critique_notes="need_strict_retry",
                rule_verdict_summary=rule_summary,
            )
        return CriticVerdict(
            acceptable=False,
            plan_step_complete=False,
            next_hint=CriticNextHint.DEGRADE,
            critique_notes="generation_degrade",
            rule_verdict_summary=rule_summary,
        )

    if tool_name == "verify_evidence":
        grounded = execution.payload.get("grounding_ratio", 0)
        passed = state.evidence_verification_passed is True
        hint = CriticNextHint.PROCEED if passed else (
            CriticNextHint.REPLAN if _should_request_replan(state) else CriticNextHint.RETRY
        )
        return CriticVerdict(
            acceptable=passed,
            plan_step_complete=passed,
            next_hint=hint,
            critique_notes=f"evidence_grounding:{grounded}",
            evidence_grounded=passed,
            rule_verdict_summary=rule_summary,
        )

    if tool_name == "finish":
        return CriticVerdict(
            acceptable=True,
            plan_step_complete=True,
            next_hint=CriticNextHint.STOP,
            critique_notes="finished",
            rule_verdict_summary=rule_summary,
        )

    if tool_name == "degrade_output":
        return CriticVerdict(
            acceptable=True,
            plan_step_complete=True,
            next_hint=CriticNextHint.STOP,
            critique_notes="degraded",
            rule_verdict_summary=rule_summary,
        )

    # extract_clauses, summarize_partial
    return CriticVerdict(
        acceptable=True,
        plan_step_complete=False,
        next_hint=CriticNextHint.PROCEED,
        critique_notes=f"aux_{tool_name}",
        rule_verdict_summary=rule_summary,
    )


async def _llm_strategy_suggestion(state: AgentRuntimeState, tool_name: str, verdict: CriticVerdict) -> str:
    """让 LLM 基于当前结果输出策略改进建议。"""
    if verdict.acceptable and verdict.next_hint in (CriticNextHint.STOP, CriticNextHint.PROCEED):
        return ""
    client = get_ollama_client()
    model = get_ollama_model()
    sys_msg = (
        "你是合同审查策略顾问。输出一个 JSON：{\"strategy\":\"...\",\"confidence\":0.x}\n"
        "strategy 用一句话说明下一步应如何改进（如扩大检索、换维度分析、加强证据等）。"
    )
    user_msg = (
        f"工具={tool_name}，评判={verdict.critique_notes}\n"
        f"当前风险数={len(state.accepted_risks)}，检索片段数={len(state.retrieved_chunks)}\n"
        f"当前目标：{state.current_goal or state.primary_goal}\n"
        "请给出策略改进建议。"
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
                "temperature": min(get_llm_temperature(), 0.3),
                "num_ctx": get_llm_num_ctx(),
                "num_predict": min(get_llm_num_predict(), 256),
                "reasoning": get_llm_reasoning(),
            },
        )
        raw = response["message"]["content"].strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            data = json.loads(raw[start : end + 1])
            return str(data.get("strategy", ""))[:500]
    except Exception as e:
        logger.debug("[CRITIC_STRATEGY] %s", e)
    return ""


async def critique_after_tool_async(
    *,
    state: AgentRuntimeState,
    policy: AgentPolicy,
    tool_name: str,
    execution: ToolExecutionResult,
) -> CriticVerdict:
    """
    异步评判：由 LLM 判断「信息是否足够」，弱化固定 chunk 阈值。附带 strategy_suggestion。
    """
    if not execution.ok:
        base = critique_after_tool(
            state=state, policy=policy, tool_name=tool_name, execution=execution
        )
        base.strategy_suggestion = await _llm_strategy_suggestion(state, tool_name, base)
        return base

    if tool_name in ("retrieve_context", "widen_retrieval"):
        judge = await llm_judge_retrieval_sufficient(state)
        rule_summary: dict = {"tool": tool_name, "ok": execution.ok, "llm_retrieval_gate": judge}
        if judge.get("sufficient"):
            verdict = CriticVerdict(
                acceptable=True,
                plan_step_complete=True,
                next_hint=CriticNextHint.PROCEED,
                critique_notes=f"llm_retrieval_ok:{judge.get('reason', '')}",
                rule_verdict_summary=rule_summary,
                llm_critique=str(judge.get("reason", "")),
            )
        else:
            hint = CriticNextHint.REPLAN if _should_request_replan(state) else CriticNextHint.RETRY
            verdict = CriticVerdict(
                acceptable=False,
                plan_step_complete=False,
                next_hint=hint,
                critique_notes=f"llm_retrieval_need_more:{judge.get('reason', '')}",
                rule_verdict_summary=rule_summary,
                llm_critique=str(judge.get("reason", "")),
            )
        verdict.strategy_suggestion = await _llm_strategy_suggestion(state, tool_name, verdict)
        return verdict

    base = critique_after_tool(
        state=state, policy=policy, tool_name=tool_name, execution=execution
    )
    base.strategy_suggestion = await _llm_strategy_suggestion(state, tool_name, base)
    return base
