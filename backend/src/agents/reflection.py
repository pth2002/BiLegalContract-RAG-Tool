"""自我评估：规则为主；可选 LLM 反思（维度覆盖、遗漏、是否应 refine）。""" 

from __future__ import annotations

import json
import logging
import re
from typing import Any

from json_repair import repair_json
from pydantic import BaseModel, Field

from ..config import get_llm_num_ctx, get_llm_num_predict, get_llm_reasoning, get_llm_temperature, get_ollama_model
from ..services.ollama_service import get_ollama_client
from .agent_state import AgentRuntimeState
from .evaluators import evaluate_generation, evaluate_retrieval
from .policy import AgentPolicy
from .risk_parsing import parse_risk_json

logger = logging.getLogger(__name__)

_JSON_RETRIES = 3


def _extract_json_payload(raw: str) -> dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("empty")

    candidates: list[str] = []
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        candidates.append(raw[start : end + 1])
    candidates.append(raw)

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            return json.loads(candidate)
        except Exception:
            pass
        try:
            repaired = repair_json(candidate, ensure_ascii=False)
            return json.loads(repaired)
        except Exception:
            pass
    raise ValueError("no json")


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes", "y", "是", "对", "correct"}:
        return True
    if text in {"false", "0", "no", "n", "否", "错", "incorrect"}:
        return False
    return default


def _coerce_float(value: Any, default: float = 0.5) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
    if not match:
        return default
    return float(match.group(0))


def _extract_keyed_text(raw: str, keys: list[str]) -> str:
    for key in keys:
        pattern = rf"{re.escape(key)}\s*[:：]\s*(.+)"
        match = re.search(pattern, raw, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _extract_missing_list(raw: str) -> list[str]:
    text = _extract_keyed_text(raw, ["missing", "遗漏", "缺失"])
    if not text:
        return []
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
    else:
        inner = text
    parts = re.split(r"[,\n，、；;]\s*", inner)
    return [p.strip(" \"'[]") for p in parts if p.strip(" \"'[]")]


def _parse_reflection_payload(raw: str) -> dict[str, Any]:
    try:
        return _extract_json_payload(raw)
    except Exception:
        score = _coerce_float(_extract_keyed_text(raw, ["score", "评分", "分数"]), 0.5)
        should_refine = _coerce_bool(_extract_keyed_text(raw, ["should_refine", "refine", "是否需要改进"]), score < 0.65)
        feedback = _extract_keyed_text(raw, ["feedback", "critique", "说明", "评价"]) or raw[:400]
        return {
            "score": score,
            "missing": _extract_missing_list(raw),
            "feedback": feedback,
            "should_refine": should_refine,
        }


def _parse_self_critic_payload(raw: str) -> dict[str, Any]:
    try:
        return _extract_json_payload(raw)
    except Exception:
        is_correct_text = _extract_keyed_text(raw, ["is_correct", "correct", "是否正确"])
        confidence_text = _extract_keyed_text(raw, ["confidence", "score", "置信度"])
        critique = _extract_keyed_text(raw, ["critique", "feedback", "说明", "评价"]) or raw[:400]
        fix_plan = _extract_keyed_text(raw, ["fix_plan", "plan", "改进计划", "修复计划"])
        return {
            "is_correct": _coerce_bool(is_correct_text, False),
            "confidence": _coerce_float(confidence_text, 0.5),
            "critique": critique,
            "fix_plan": fix_plan,
        }

# 合同审查常见维度（启发式关键词覆盖检测）
_COVERAGE_KEYWORDS = {
    "付款": ["付款", "支付", "价款", "结算", "发票"],
    "违约": ["违约", "赔偿", "责任", "罚金", "滞纳"],
    "终止": ["终止", "解除", "到期", "续签", "通知"],
}


class ReflectionResult(BaseModel):
    """反思层输出：与规范中的 score / missing 对齐。"""

    score: float = Field(ge=0.0, le=1.0, description="0~1 综合得分")
    missing: list[str] = Field(default_factory=list, description="可能缺失的主题")
    good_enough: bool = False
    hint: str = Field("", description="refine | proceed | stop 等")
    notes: str = ""
    rule_summary: dict[str, Any] = Field(default_factory=dict)
    feedback: str = Field("", description="LLM 反思说明")
    should_refine: bool = Field(False, description="是否建议再修一轮")
    # v3：自评式 Critic
    is_correct: bool | None = None
    fix_plan: str = Field("", description="改进计划，可驱动自校正")


def _coverage_from_risks(state: AgentRuntimeState, parsed: list[dict]) -> set[str]:
    covered: set[str] = set()
    if state.accepted_risks:
        text_blob = " ".join(
            [r.original_text + r.risk_description + r.clause_title for r in state.accepted_risks]
        )
    else:
        text_blob = " ".join(
            str(d.get("original_text", "")) + str(d.get("risk_description", "")) + str(d.get("clause_title", ""))
            for d in parsed
        )
    for dim, kws in _COVERAGE_KEYWORDS.items():
        if any(k in text_blob for k in kws):
            covered.add(dim)
    return covered


def reflect_after_tool(
    *,
    state: AgentRuntimeState,
    policy: AgentPolicy,
    last_tool: str,
) -> ReflectionResult:
    """
    在每次工具执行后做轻量反思（不替代 critic 的门控）。
    - 检索族：用 evaluate_retrieval
    - 生成族：用 evaluate_generation + 维度覆盖启发式
    """
    rule: dict[str, Any] = {"last_tool": last_tool}

    if last_tool in ("retrieve_context", "widen_retrieval", "refine_query"):
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
        rule["retrieval"] = rv.metrics
        score = min(1.0, max(0.0, (rv.metrics.get("avg_score", 0) or 0) * 1.2))
        if rv.passed:
            return ReflectionResult(
                score=score,
                missing=[],
                good_enough=True,
                hint="proceed",
                notes=f"retrieval_{rv.quality}",
                rule_summary=rule,
                should_refine=False,
            )
        return ReflectionResult(
            score=score * 0.6,
            missing=["检索质量不足"],
            good_enough=False,
            hint="refine",
            notes=f"retrieval_need_improve:{rv.suggested_action}",
            rule_summary=rule,
            should_refine=True,
        )

    if last_tool in ("analyze_risks", "retry_generation_strict"):
        parsed = parse_risk_json(state.last_llm_raw)
        gv = evaluate_generation(
            raw_text=state.last_llm_raw,
            parsed_risks=parsed,
            policy_min_risks=policy.min_risks_accept,
            policy_min_complete_ratio=policy.min_complete_risks_ratio,
        )
        rule["generation"] = {
            "passed": gv.passed,
            "risk_count": gv.risk_count,
            "complete_ratio": gv.complete_ratio,
        }
        covered = _coverage_from_risks(state, parsed)
        missing_dims = [d for d in _COVERAGE_KEYWORDS if d not in covered]
        base = 0.35 + 0.45 * float(gv.complete_ratio or 0) + 0.1 * min(len(state.accepted_risks), 5) / 5.0
        score = min(1.0, base) if gv.passed else min(0.65, base)
        good = gv.passed and len(missing_dims) <= 1
        return ReflectionResult(
            score=round(score, 3),
            missing=missing_dims[:5],
            good_enough=good,
            hint="stop" if good else "refine",
            notes="generation_ok" if gv.passed else "generation_weak",
            rule_summary=rule,
            should_refine=not good,
        )

    if last_tool == "verify_evidence":
        ok = state.evidence_verification_passed is True
        return ReflectionResult(
            score=0.9 if ok else 0.45,
            missing=[] if ok else ["证据对齐未通过"],
            good_enough=ok,
            hint="proceed" if ok else "refine",
            notes="evidence_verified" if ok else "evidence_failed",
            rule_summary=rule,
            should_refine=not ok,
        )

    return ReflectionResult(
        score=0.55,
        missing=[],
        good_enough=False,
        hint="proceed",
        notes=f"no_specific_reflection_for:{last_tool}",
        rule_summary=rule,
        should_refine=False,
    )


def _risks_text_for_llm(state: AgentRuntimeState) -> str:
    if state.accepted_risks:
        parts = []
        for r in state.accepted_risks[:15]:
            parts.append(
                f"- [{r.severity.value}] {r.clause_title}: {r.risk_description[:200]}"
            )
        return "\n".join(parts)
    raw = (state.last_llm_raw or "").strip()
    return raw[:6000] if raw else "(无生成内容)"


async def llm_reflect_risks(state: AgentRuntimeState, policy: AgentPolicy) -> ReflectionResult:
    """
    LLM 合同专家反思：评估付款/违约/终止维度覆盖与遗漏。
    输出 JSON：score, missing, feedback, should_refine
    """
    _ = policy
    risks_block = _risks_text_for_llm(state)
    sys_msg = (
        "你是一个合同审查专家。只输出一个 JSON 对象，不要 markdown，不要其它文字。\n"
        "键必须为：score(0~1小数), missing(字符串数组), feedback(字符串), should_refine(布尔)。"
    )
    user_msg = (
        f"当前AI生成的风险分析如下：\n{risks_block}\n\n"
        "请评估：\n"
        "1. 是否覆盖以下维度：付款风险、违约责任、合同终止\n"
        "2. 是否存在遗漏？\n"
    )
    client = get_ollama_client()
    model = get_ollama_model()
    last_err: str | None = None
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
                    "temperature": min(get_llm_temperature(), 0.2),
                    "num_ctx": get_llm_num_ctx(),
                    "num_predict": min(get_llm_num_predict(), 512),
                    "reasoning": get_llm_reasoning(),
                },
            )
            raw = response["message"]["content"].strip()
            data = _parse_reflection_payload(raw)
            score = float(data.get("score", 0.5))
            score = max(0.0, min(1.0, score))
            missing = data.get("missing") or []
            if not isinstance(missing, list):
                missing = [str(missing)]
            missing = [str(x) for x in missing][:10]
            feedback = str(data.get("feedback", ""))
            should_refine = bool(data.get("should_refine", score < 0.65))
            good = score >= 0.72 and not should_refine
            return ReflectionResult(
                score=round(score, 3),
                missing=missing,
                good_enough=good,
                hint="stop" if good else "refine",
                notes="llm_reflection",
                rule_summary={"source": "llm"},
                feedback=feedback,
                should_refine=should_refine,
            )
        except Exception as e:
            last_err = str(e)
            logger.warning("[LLM_REFLECTION] attempt %d/%d failed: %s", attempt, _JSON_RETRIES, e)
    logger.warning("[LLM_REFLECTION] fallback to rule: %s", last_err)
    return reflect_after_tool(state=state, policy=policy, last_tool="analyze_risks")


async def llm_self_critic_reflect(state: AgentRuntimeState, policy: AgentPolicy) -> ReflectionResult:
    """
    v3：「你觉得这个答案靠谱吗」——输出 is_correct, confidence, critique, fix_plan。
    """
    _ = policy
    risks_block = _risks_text_for_llm(state)
    sys_msg = (
        "你是严谨的合同审查审计员。只输出一个 JSON，不要 markdown。\n"
        "键：is_correct(布尔), confidence(0~1小数), critique(字符串), fix_plan(字符串，可空)。\n"
        "fix_plan 应给出可执行的改进方向（如补充某类条款风险、加强引用）。"
    )
    user_msg = f"请评价以下风险分析是否靠谱、为何：\n{risks_block}\n"
    client = get_ollama_client()
    model = get_ollama_model()
    last_err: str | None = None
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
                    "temperature": min(get_llm_temperature(), 0.2),
                    "num_ctx": get_llm_num_ctx(),
                    "num_predict": min(get_llm_num_predict(), 512),
                    "reasoning": get_llm_reasoning(),
                },
            )
            raw = response["message"]["content"].strip()
            data = _parse_self_critic_payload(raw)
            ok = _coerce_bool(data.get("is_correct"))
            conf = float(data.get("confidence", 0.5))
            conf = max(0.0, min(1.0, conf))
            critique = str(data.get("critique", ""))
            fix_plan = str(data.get("fix_plan", ""))
            should_refine = (not ok) or conf < 0.55
            return ReflectionResult(
                score=round(conf, 3),
                missing=[] if ok else ["self_critic"],
                good_enough=ok and conf >= 0.65,
                hint="stop" if ok and not should_refine else "refine",
                notes="llm_self_critic",
                rule_summary={"source": "llm_self_critic"},
                feedback=critique,
                should_refine=should_refine,
                is_correct=ok,
                fix_plan=fix_plan,
            )
        except Exception as e:
            last_err = str(e)
            logger.warning("[LLM_SELF_CRITIC] attempt %d failed: %s", attempt, e)
    logger.warning("[LLM_SELF_CRITIC] fallback: %s", last_err)
    return reflect_after_tool(state=state, policy=policy, last_tool="analyze_risks")


async def reflect_after_tool_async(
    *,
    state: AgentRuntimeState,
    policy: AgentPolicy,
    last_tool: str,
) -> ReflectionResult:
    """
    异步反思入口：v3 自评优先；否则 LLM 维度反思；否则规则。
    """
    if last_tool in ("analyze_risks", "retry_generation_strict") and (
        state.last_llm_raw.strip() or state.accepted_risks
    ):
        try:
            return await llm_self_critic_reflect(state, policy)
        except Exception:
            logger.warning("[REFLECTION] llm_self_critic failed, falling back to llm_reflect_risks")
        try:
            return await llm_reflect_risks(state, policy)
        except Exception:
            logger.warning("[REFLECTION] llm_reflect_risks failed, falling back to rule-based")
    return reflect_after_tool(state=state, policy=policy, last_tool=last_tool)
