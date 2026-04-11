"""Main agent runtime: decision → execute → critique → replan → finish/degrade."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Callable, Optional

from ..config import (
    get_agent_max_loop_steps,
    get_agent_v5_step_fail_replan_threshold,
)
from ..models import AnalysisRequest, AnalysisResult, Document
from ..services.indexing_service import index_document
from ..services.vector_store_service import has_indexed, init_vector_store
from .action_models import ActionDecision, AgentPlan, CriticNextHint, PlanStepStatus
from .agent_state import AgentRuntimeState, BudgetUsage, build_agent_state_view
from .critic import critique_after_tool_async
from .decider import decide_next_action
from .fallback_decider import decide_fallback
from .evaluators import evaluate_final_deliverable
from .memory import AgentMemory
from .reflection import reflect_after_tool_async
from .planner import build_initial_plan, current_plan_step, generate_plan_from_state
from .policy import AgentPolicy
from .fix_plan import apply_fix_plan_to_state
from .goal_injection import advance_sub_goal, decompose_sub_goals, inject_dynamic_goal
from .guardrails import apply_runtime_guardrails, sanitize_decision_inputs
from .replanner import maybe_replan, maybe_replan_async
from .tool_executor import execute as execute_tool
from .tool_registry import list_tool_names, run_tool
from .trace import AgentTrace, TraceStep
from .vector_memory import create_vector_memory_store

logger = logging.getLogger(__name__)

_ALLOWED_TOOLS = frozenset(list_tool_names())

ProgressFn = Optional[Callable[..., None]]


def _emit_progress(cb: ProgressFn, msg: str, pct: int, extra: dict | None = None) -> None:
    if not cb:
        return
    try:
        cb(msg, pct, extra)
    except TypeError:
        cb(msg, pct)


def _build_analysis_result(state: AgentRuntimeState, start_time: float) -> AnalysisResult:
    risks = state.accepted_risks
    high = sum(1 for r in risks if r.severity.value == "高")
    medium = sum(1 for r in risks if r.severity.value == "中")
    low = sum(1 for r in risks if r.severity.value == "低")
    if state.final_summary:
        summary = state.final_summary
    elif state.degraded:
        summary = (
            "【降级交付】未能完全满足自动验收标准。"
            + (" " + "；".join(state.warnings) if state.warnings else "")
            + " 建议人工复核合同全文。"
        )
    else:
        summary = (
            f"分析完成。共发现 {len(risks)} 个风险点，"
            f"其中高风险 {high} 个，中风险 {medium} 个，低风险 {low} 个。"
        )
    duration_ms = int((time.time() - start_time) * 1000)
    return AnalysisResult(
        document_id=state.document.id,
        perspective=state.request.perspective,
        risks=risks,
        summary=summary,
        analyzed_at=datetime.utcnow(),
        duration_ms=duration_ms,
    )


class AgentRuntime:
    """Policy-constrained autonomous loop with LLM decider."""

    def __init__(self) -> None:
        self.last_trace: AgentTrace | None = None
        self.last_plan: AgentPlan | None = None

    async def run(
        self,
        *,
        request: AnalysisRequest,
        document: Document,
        progress_callback: ProgressFn = None,
    ) -> AnalysisResult:
        start_time = time.time()
        await init_vector_store()
        if not await has_indexed(document.id):
            logger.info("[RUNTIME] Document %s not indexed — indexing now", document.id)
            await index_document(document)

        policy = AgentPolicy.from_config()
        state = AgentRuntimeState(
            request=request,
            document=document,
            primary_goal="结构化合同风险审查（可交付风险卡）",
            plan=None,
            working_memory=AgentMemory(),
            budget=BudgetUsage(),
        )
        state.primary_goal = await inject_dynamic_goal(request, document)
        await decompose_sub_goals(state)
        logger.info("[RUNTIME] sub_goals=%s", state.sub_goals[:6])
        state.plan = await generate_plan_from_state(state)
        plan = state.plan
        vm = create_vector_memory_store()
        state.meta["vector_memory"] = vm
        vm.add_contract_context(document.id, (document.text_content or "")[:3000], note="runtime_head")
        trace = AgentTrace()
        history: list[dict[str, Any]] = []
        max_iter = min(policy.max_loop_iterations, get_agent_max_loop_steps())

        _emit_progress(progress_callback, "Agent Runtime：初始化计划与预算", 8, None)
        trace.append(
            TraceStep(
                phase="runtime",
                action="init",
                reason="启动自治 runtime",
                outputs_summary={"plan_version": plan.version, "steps": [s.id for s in plan.steps]},
            )
        )

        iteration = 0
        while iteration < max_iter and not state.finished:
            iteration += 1
            state.budget.loop_iterations += 1

            if state.budget.loop_iterations > policy.max_loop_iterations:
                state.warnings.append("达到最大循环步数，强制降级结束")
                state.degraded = True
                await run_tool("degrade_output", state, policy, {"reason": "max_loop_iterations"})
                break

            forced = state.meta.pop("preferred_next_tool", None)
            forced_this_loop = bool(forced) and forced in _ALLOWED_TOOLS
            if forced_this_loop:
                decision = ActionDecision(
                    action_name=forced,
                    action_input={},
                    reason="self_correction_or_policy",
                    expected_result="refine",
                    confidence=0.92,
                    thought="(policy/self-correction 强制工具)",
                )
                logger.info("[STEP %d] forced_tool=%s (self-correction)", iteration, forced)
            else:
                try:
                    decision = await decide_next_action(state=state, policy=policy, plan=plan, recent_history=history)
                except Exception:
                    logger.exception("[RUNTIME] LLM decider failed, using fallback")
                    decision = await decide_fallback(state=state, policy=policy)

            if forced_this_loop:
                decision = sanitize_decision_inputs(decision)
            else:
                decision, guard_notes = apply_runtime_guardrails(decision, policy, state)
                for note in guard_notes:
                    state.warnings.append(note)

            if decision.thought:
                state.thought_history.append(
                    {
                        "iteration": iteration,
                        "thought": decision.thought,
                        "action": decision.action_name,
                    }
                )

            state.runtime_confidence = float(decision.confidence)
            view = build_agent_state_view(
                state, step_count=iteration, history=history, confidence=state.runtime_confidence
            )
            _chain_n = 1 + (min(len(decision.tool_chain), 3) if decision.tool_chain else 0)
            logger.info(
                "[STEP %d] action=%s chain=%d conf=%.2f chunks=%d risks=%s",
                iteration,
                decision.action_name,
                _chain_n,
                view.confidence,
                len(view.retrieved_chunks),
                len(state.accepted_risks),
            )

            if not forced_this_loop:
                fp = state.working_memory.fingerprint_input(decision.action_name, decision.action_input)
                streak = state.working_memory.identical_streak(decision.action_name, fp)
                if streak >= policy.max_identical_action_repeats:
                    state.warnings.append(f"检测到重复失败动作 {decision.action_name}，触发重规划")
                    plan = await maybe_replan_async(state=state, plan=plan, policy=policy, reason="identical_action_loop")
                    state.plan = plan
                    continue

            # v3：多工具链 — 顺序执行，取最后一步作为 critique / reflection 依据
            to_run: list[ActionDecision] = [decision]
            if decision.tool_chain:
                for item in decision.tool_chain[:3]:
                    tn = item.get("tool")
                    tinp = item.get("input") if isinstance(item.get("input"), dict) else {}
                    if tn and tn in _ALLOWED_TOOLS:
                        to_run.append(
                            ActionDecision(
                                action_name=tn,
                                action_input=tinp,
                                reason=decision.reason,
                                expected_result="",
                                confidence=decision.confidence,
                            )
                        )

            exec_result = None
            last_tool_name = decision.action_name
            for ad in to_run:
                state.working_memory.record_action(ad.action_name, ad.action_input or {})
                exec_result = await execute_tool(ad, state, policy, step_index=iteration)
                last_tool_name = ad.action_name
                obs = f"iter={iteration} action={ad.action_name} ok={exec_result.ok}"
                state.observation_history.append(obs)
                state.observations.append(obs)
                history.append(
                    {
                        "tool": ad.action_name,
                        "ok": exec_result.ok,
                        "reason": ad.reason[:120],
                    }
                )

            if exec_result is None:
                continue

            verdict = await critique_after_tool_async(
                state=state,
                policy=policy,
                tool_name=last_tool_name,
                execution=exec_result,
            )

            refl = await reflect_after_tool_async(state=state, policy=policy, last_tool=last_tool_name)
            if getattr(refl, "fix_plan", ""):
                state.meta["last_fix_plan"] = str(refl.fix_plan)[:1500]
            state.runtime_confidence = refl.score
            state.working_memory.add_step(
                {
                    "iteration": iteration,
                    "tool": decision.action_name,
                    "reflection_score": refl.score,
                    "reflection_missing": refl.missing,
                    "reflection_hint": refl.hint,
                    "reflection_feedback": (refl.feedback or "")[:300],
                    "should_refine": getattr(refl, "should_refine", False),
                }
            )
            logger.info(
                "[STEP %d] reflection score=%.2f missing=%s hint=%s",
                iteration,
                refl.score,
                refl.missing[:3],
                refl.hint,
            )

            fix_applied = False
            if (
                (refl.fix_plan or "").strip()
                and (bool(getattr(refl, "should_refine", False)) or getattr(refl, "is_correct", None) is False)
            ):
                fix_applied = apply_fix_plan_to_state(state, str(refl.fix_plan))
                if fix_applied:
                    state.meta["preferred_next_tool"] = "retrieve_context"
                    state.warnings.append("v4：已应用 fix_plan，下一轮优先按新 query 检索")
                    logger.info("[STEP %d] fix_plan applied → retrieve_context", iteration)

            if refl.score < 0.5:
                prev = state.primary_goal[:200]
                state.primary_goal = (
                    f"【演化目标】优先提高风险覆盖率、证据链完整性（原目标摘要：{prev}）"
                )[:800]
                state.warnings.append("v4：目标演化 — 当前反思分数偏低，收紧交付策略")

            vm = state.meta.get("vector_memory")
            if vm is not None and hasattr(vm, "add_experience"):
                st = current_plan_step(plan, state.current_step_index)
                vm.add_experience(
                    query=f"{state.request.perspective.value} {(st.goal if st else 'run')}",
                    good_strategy=decision.action_name if exec_result.ok else "",
                    bad_strategy="" if exec_result.ok else last_tool_name,
                    reflection_score=refl.score,
                    tool=last_tool_name,
                )

            # Strategy Learning：critic 策略建议写入 memory + state
            if verdict.strategy_suggestion:
                state.latest_strategy = verdict.strategy_suggestion
                if vm is not None and hasattr(vm, "add_strategy"):
                    vm.add_strategy(
                        context=f"{last_tool_name} | {verdict.critique_notes}",
                        strategy=verdict.strategy_suggestion,
                        source="critic",
                        confidence=state.runtime_confidence,
                    )
                logger.info("[STEP %d] v5 strategy: %s", iteration, verdict.strategy_suggestion[:100])

            # 自校正：生成类工具后，分数过低 / 应 refine / 自评否定 → 下一轮强制 strict 重生成（有上限）
            if not fix_applied and last_tool_name in ("analyze_risks", "retry_generation_strict"):
                low = refl.score < policy.reflection_score_threshold
                want = bool(getattr(refl, "should_refine", False))
                bad = getattr(refl, "is_correct", None) is False
                if (low or want or bad) and not state.finished:
                    sc = int(state.meta.get("self_correction_rounds", 0))
                    if sc < policy.self_correction_max:
                        state.meta["self_correction_rounds"] = sc + 1
                        state.meta["preferred_next_tool"] = "retry_generation_strict"
                        state.warnings.append(
                            f"自校正：反思 score={refl.score:.2f}，下一轮强制 refine（{sc + 1}/{policy.self_correction_max}）"
                        )
                        logger.info("[STEP %d] self_correction scheduled → retry_generation_strict", iteration)

            trace.append_decision_record(
                iteration=iteration,
                decision=decision.model_dump(mode="json"),
                execution=exec_result.model_dump(mode="json"),
                critique=verdict.model_dump(mode="json"),
            )
            trace.append(
                TraceStep(
                    phase="runtime",
                    action=decision.action_name,
                    reason=decision.reason,
                    inputs_summary={
                        "action_input": decision.action_input,
                        "alt_plan": decision.alt_plan,
                        "thought": (decision.thought or "")[:500],
                    },
                    outputs_summary={
                        "exec_ok": exec_result.ok,
                        "payload_keys": list(exec_result.payload.keys()),
                        "last_tool": last_tool_name,
                        "tool_chain_len": len(to_run),
                    },
                    verdict=verdict.critique_notes,
                    policy_hint=verdict.next_hint.value,
                )
            )

            _emit_progress(
                progress_callback,
                f"Agent：{decision.action_name}→{last_tool_name} → {verdict.next_hint.value}",
                min(95, 10 + iteration * 4),
                {"type": "agent_trace", "step": trace.steps[-1].to_dict(), "iteration": iteration},
            )

            # Advance plan step on completion signals
            adv_step = current_plan_step(plan, state.current_step_index)
            if adv_step and verdict.plan_step_complete:
                adv_step.status = PlanStepStatus.DONE
                if state.current_step_index < len(plan.steps) - 1:
                    state.current_step_index += 1
                    plan.steps[state.current_step_index].status = PlanStepStatus.IN_PROGRESS
                # v5 Goal System：步骤完成时推进子目标
                if state.sub_goals:
                    has_more = advance_sub_goal(state)
                    if has_more:
                        logger.info("[STEP %d] v5 sub_goal advanced → %s", iteration, state.current_goal)
                    else:
                        logger.info("[STEP %d] v5 all sub_goals completed", iteration)

            # v5：单步连续失败计数 → 自动重规划
            step = current_plan_step(plan, state.current_step_index)
            if step and not verdict.acceptable:
                step.attempts += 1
                fail_threshold = get_agent_v5_step_fail_replan_threshold()
                if step.attempts >= fail_threshold:
                    state.warnings.append(f"步骤 {step.id} 连续失败 {step.attempts} 次，LLM 重规划")
                    step.status = PlanStepStatus.FAILED
                    plan = await maybe_replan_async(state=state, plan=plan, policy=policy, reason=f"step_{step.id}_failed_{step.attempts}")
                    state.plan = plan
                    continue

            if verdict.next_hint == CriticNextHint.REPLAN:
                plan = await maybe_replan_async(state=state, plan=plan, policy=policy, reason=verdict.critique_notes)
                state.plan = plan
                continue

            if verdict.next_hint == CriticNextHint.DEGRADE:
                await run_tool("degrade_output", state, policy, {"reason": verdict.critique_notes})
                break

            if verdict.next_hint == CriticNextHint.STOP:
                break

            # Auto-finish path: generation ok + evidence ok
            if (
                state.accepted_risks
                and state.evidence_verification_passed is True
                and decision.action_name == "verify_evidence"
            ):
                await run_tool("finish", state, policy, {})
                break

        if not state.finished:
            state.degraded = True
            state.warnings.append("运行时未正常结束，降级封装结果")
            state.finished = True

        # Final deliverable summary meta
        eval_final = evaluate_final_deliverable(
            generation_passed=bool(state.accepted_risks) and not state.degraded,
            degraded=state.degraded,
            warnings=state.warnings,
        )
        trace.append(
            TraceStep(
                phase="runtime",
                action="finalize",
                reason="组装 AnalysisResult",
                outputs_summary=eval_final,
                verdict="degraded" if state.degraded else "ok",
            )
        )

        self.last_trace = trace
        self.last_plan = plan

        return _build_analysis_result(state, start_time)
