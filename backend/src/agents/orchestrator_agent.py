"""Mature autonomous orchestrator: goals, evaluators, policy, trace, retrieval + generation loops."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Callable, Optional

from json_repair import repair_json

from ..config import (
    get_agent_max_loop_steps,
    get_llm_num_ctx,
    get_llm_num_predict,
    get_llm_reasoning,
    get_llm_temperature,
    get_ollama_model,
    get_retriever_top_k,
)
from ..models import AnalysisRequest, AnalysisResult, Document, RetrievedChunk, RiskCard
from ..services.indexing_service import index_document
from ..services.evidence_service import attach_evidence_to_risks
from ..services.ollama_service import get_ollama_client, stream_analysis
from ..services.prompt_builder_service import RetrievedContext, build_analysis_user_prompt
from ..services.prompt_service import get_perspective_prompt
from ..services.retrieval_service import build_retrieval_queries, retrieve_contexts, retrieve_contexts_merged
from ..services.vector_store_service import has_indexed, init_vector_store

from .evaluators import evaluate_final_deliverable, evaluate_generation, evaluate_retrieval
from .goals import AgentGoalState, SubgoalStatus
from .policy import AgentPolicy
from .trace import AgentTrace, TraceStep

logger = logging.getLogger(__name__)

ProgressFn = Optional[Callable[..., None]]


def _build_rule_based_risks(document: Document, request: AnalysisRequest, retrieved: list[RetrievedChunk]) -> list[dict[str, Any]]:
    text = document.text_content or ""
    perspective = "甲方" if request.perspective.value == "party_a" else "乙方"
    sources = [chunk.content for chunk in retrieved] or [text]

    rules = [
        ("付款条款风险", ["付款", "支付", "价款", "账期", "发票", "逾期付款"], "付款条款", "medium"),
        ("违约责任风险", ["违约", "违约金", "赔偿", "损失", "责任承担"], "违约责任", "high"),
        ("解除终止风险", ["解除", "终止", "单方", "提前终止", "自动续约"], "终止解除", "high"),
        ("验收交付风险", ["验收", "交付", "交货", "成果", "测试", "确认"], "验收交付", "medium"),
        ("知识产权风险", ["知识产权", "著作权", "专利", "商标", "成果归属"], "知识产权", "medium"),
        ("保密义务风险", ["保密", "商业秘密", "披露", "信息安全", "数据"], "保密义务", "medium"),
    ]

    generated: list[dict[str, Any]] = []
    for title, keywords, category, severity in rules:
        excerpt = ""
        for source in sources:
            if any(keyword in source for keyword in keywords):
                excerpt = source[:220]
                break
        if not excerpt:
            continue
        generated.append(
            {
                "clause_title": title,
                "risk_category": category,
                "original_text": excerpt,
                "risk_description": f"{title}可能对{perspective}不利，建议结合业务背景重点复核该条款的触发条件、责任边界和履约后果。",
                "suggested_revision": "建议补充更明确的条件、责任边界、例外情形和对等保护机制，避免条款过宽或表述模糊。",
                "severity": severity,
            }
        )

    if not generated and text.strip():
        generated.append(
            {
                "clause_title": "合同综合风险提示",
                "risk_category": "其他风险",
                "original_text": (sources[0] if sources else text)[:220],
                "risk_description": f"当前模型未稳定产出结构化风险，但从合同文本看仍建议从{perspective}视角继续核查付款、违约、终止和交付条款。",
                "suggested_revision": "建议补充付款条件、违约责任边界、解除终止条件和验收标准，并做人工复核。",
                "severity": "medium",
            }
        )

    return generated[:5]


def _clean_json_content(content: str) -> str:
    cleaned = content.strip()
    cleaned = cleaned.replace("```json", "").replace("```JSON", "").replace("```", "").strip()
    start_idx = cleaned.find("[")
    if start_idx != -1:
        bracket_count = 0
        end_idx = -1
        for i in range(start_idx, len(cleaned)):
            if cleaned[i] == "[":
                bracket_count += 1
            elif cleaned[i] == "]":
                bracket_count -= 1
                if bracket_count == 0:
                    end_idx = i + 1
                    break
        if end_idx > start_idx:
            cleaned = cleaned[start_idx:end_idx]
    return cleaned


def _parse_risk_json(content: str) -> list[dict]:
    if not content:
        return []
    cleaned = _clean_json_content(content)
    try:
        risks = json.loads(cleaned)
        if isinstance(risks, list):
            return risks
    except Exception:
        pass

    try:
        repaired = repair_json(cleaned, ensure_ascii=False)
        repaired_data = json.loads(repaired) if isinstance(repaired, str) else repaired
        if isinstance(repaired_data, list):
            return repaired_data
        if isinstance(repaired_data, dict):
            return [repaired_data] if "clause_title" in repaired_data else []
    except Exception:
        pass

    pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(pattern, content, re.DOTALL)
    risks: list[dict] = []
    for match in matches:
        try:
            risk = json.loads(match)
            if isinstance(risk, dict) and "clause_title" in risk and "severity" in risk:
                risks.append(risk)
        except Exception:
            continue
    return risks


def _map_severity(value: str) -> str:
    normalized = (value or "").lower().strip()
    if normalized in {"高", "中", "低"}:
        return normalized
    if normalized in ["高风险", "high", "h"]:
        return "高"
    if normalized in ["中风险", "medium", "m", "中等"]:
        return "中"
    if normalized in ["低风险", "low", "l"]:
        return "低"
    return "中"


def _create_risk_card(risk_dict: dict, document_id, index: int) -> RiskCard:
    return RiskCard(
        id=f"risk_{index + 1:03d}",
        clause_title=risk_dict.get("clause_title", "未知条款"),
        risk_category=risk_dict.get("risk_category", "其他风险"),
        original_text=risk_dict.get("original_text", ""),
        risk_description=risk_dict.get("risk_description", ""),
        suggested_revision=risk_dict.get("suggested_revision", ""),
        severity=_map_severity(risk_dict.get("severity", "中")),
        document_id=document_id,
    )


class OrchestratorAgent:
    def __init__(self) -> None:
        self.last_trace: AgentTrace | None = None
        self.last_goals: AgentGoalState | None = None
        self.last_plan: Any | None = None

    def _emit(
        self,
        *,
        progress_callback: ProgressFn,
        message: str,
        progress: int,
        trace: AgentTrace,
        step: TraceStep,
    ) -> None:
        trace.append(step)
        if progress_callback:
            try:
                progress_callback(
                    message,
                    progress,
                    {"type": "agent_trace", "step": step.to_dict()},
                )
            except TypeError:
                progress_callback(message, progress)

    async def _tool_refine_query_llm(
        self,
        *,
        state: dict[str, Any],
        request: AnalysisRequest,
    ) -> str:
        retrieved: list[RetrievedChunk] = state.get("retrieved", [])
        snippets = "\n".join(
            [f"- {c.chunk_id} score={c.score:.4f}: {c.content[:160]}" for c in retrieved[:5]]
        )
        queries = state.get("last_queries") or build_retrieval_queries(request.perspective, request.options)

        client = get_ollama_client()
        model = get_ollama_model()
        response = client.chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "你是检索 query 优化器。输出严格 JSON：{\"query\":\"...\"}，不要其他文本。",
                },
                {
                    "role": "user",
                    "content": (
                        f"当前视角: {request.perspective.value}\n"
                        f"当前查询: {json.dumps(queries, ensure_ascii=False)}\n"
                        f"当前检索片段(可能不够好):\n{snippets}\n\n"
                        "请生成一条更聚焦、更具体、适合合同条款检索的新 query。"
                    ),
                },
            ],
            stream=False,
            options={
                "temperature": min(get_llm_temperature(), 0.2),
                "num_ctx": get_llm_num_ctx(),
                "num_predict": min(get_llm_num_predict(), 256),
                "reasoning": get_llm_reasoning(),
            },
        )
        content = response["message"]["content"].strip()
        start = content.find("{")
        end = content.rfind("}")
        query = None
        if start != -1 and end != -1 and end > start:
            try:
                query = json.loads(content[start : end + 1]).get("query")
            except Exception:
                query = None
        if not query:
            query = f"合同审查 {request.perspective.value} 视角：违约责任、付款条件、终止条款、赔偿上限。"
        return query

    async def run(
        self,
        *,
        request: AnalysisRequest,
        document: Document,
        progress_callback: ProgressFn = None,
    ) -> AnalysisResult:
        try:
            from .agent_runtime import AgentRuntime

            runtime = AgentRuntime()
            result = await runtime.run(
                request=request,
                document=document,
                progress_callback=progress_callback,
            )
            self.last_trace = runtime.last_trace
            self.last_plan = runtime.last_plan
            self.last_goals = None
            return result
        except Exception:
            logger.exception("[ORCHESTRATOR] AgentRuntime failed, falling back to legacy pipeline")

        start_time = time.time()
        await init_vector_store()

        policy = AgentPolicy.from_config()
        goals = AgentGoalState()
        trace = AgentTrace()
        state: dict[str, Any] = {
            "top_k_boost": 0,
            "query_override": None,
            "retrieval_strategy": "merged",
        }
        warnings: list[str] = []
        global_step = 0
        max_steps = get_agent_max_loop_steps()
        degraded = False
        retrieval_passed = False
        generation_passed = False

        def prog(pct: int, msg: str) -> int:
            return min(95, max(5, pct))

        # --- Goal: explicit ---
        self._emit(
            progress_callback=progress_callback,
            message="Agent：初始化目标与策略层",
            progress=prog(5, ""),
            trace=trace,
            step=TraceStep(
                phase="init",
                action="goal_init",
                reason="明确总目标与子目标，进入自治闭环",
                outputs_summary=goals.to_dict(),
                verdict="ok",
                policy_hint="policy_loaded",
            ),
        )

        # --- Index ---
        global_step += 1
        if not await has_indexed(document.id):
            await index_document(document)
        state["indexed"] = True
        self._emit(
            progress_callback=progress_callback,
            message="Agent：索引就绪",
            progress=prog(12, ""),
            trace=trace,
            step=TraceStep(
                phase="index",
                action="ensure_index",
                reason="向量库需有 chunk 才能检索",
                outputs_summary={"indexed": True},
                verdict="ok",
            ),
        )

        # --- Retrieval loop ---
        goals.mark("sg1", SubgoalStatus.IN_PROGRESS)
        rr = 0
        while rr < policy.max_retrieval_rounds and global_step < max_steps:
            global_step += 1
            rr += 1

            final_k = min(20, get_retriever_top_k() + state.get("top_k_boost", 0))
            if state.get("query_override"):
                retrieved = await retrieve_contexts(
                    document_id=document.id,
                    session_id=document.session_id,
                    query=state["query_override"],
                    top_k=final_k,
                )
                state["last_queries"] = [state["query_override"]]
            else:
                retrieved = await retrieve_contexts_merged(
                    document_id=document.id,
                    session_id=document.session_id,
                    perspective=request.perspective,
                    options=request.options,
                    final_top_k=final_k,
                    document_text=document.text_content,
                    document=document,
                )
                state["last_queries"] = build_retrieval_queries(request.perspective, request.options)

            state["retrieved"] = retrieved
            state["retrieval_round"] = rr

            rv = evaluate_retrieval(
                chunks=retrieved,
                perspective=request.perspective,
                options=request.options,
                policy_min_chunks_ok=policy.min_chunks_ok,
                policy_min_chunks_relaxed=policy.min_chunks_relaxed,
                policy_min_avg=policy.min_avg_score_ok,
                policy_min_max=policy.min_max_score_ok,
                policy_min_focus_ratio=policy.min_focus_coverage_ratio,
            )

            self._emit(
                progress_callback=progress_callback,
                message=f"Agent：检索评估 -> {rv.quality} ({'通过' if rv.passed else '未通过'})",
                progress=prog(15 + rr * 8, ""),
                trace=trace,
                step=TraceStep(
                    phase="retrieval",
                    action="evaluate_retrieval",
                    reason="质量门：数量/分数/focus 覆盖",
                    inputs_summary={"round": rr, "strategy": state.get("retrieval_strategy")},
                    outputs_summary=rv.metrics,
                    verdict=rv.quality,
                    policy_hint=rv.suggested_action,
                ),
            )

            if rv.passed:
                retrieval_passed = True
                goals.mark("sg1", SubgoalStatus.DONE, notes=f"quality={rv.quality}")
                break

            # Policy: refine / widen / switch strategy
            if state.get("refine_round", 0) < policy.max_refine_rounds and rv.suggested_action in (
                "refine_query",
                "widen_retrieval",
            ):
                if rv.suggested_action == "widen_retrieval":
                    state["top_k_boost"] = state.get("top_k_boost", 0) + 4
                    state["query_override"] = None
                    state["retrieval_strategy"] = "merged_widen"
                    warnings.append("检索质量不足：已扩大 top_k 并回到 merged 检索")
                else:
                    q = await self._tool_refine_query_llm(state=state, request=request)
                    state["query_override"] = q
                    state["refine_round"] = state.get("refine_round", 0) + 1
                    state["retrieval_strategy"] = "override_query"
                    warnings.append("检索质量不足：已重写 query 再检索")

                self._emit(
                    progress_callback=progress_callback,
                    message="Agent：按策略调整检索后重试",
                    progress=prog(20 + rr * 6, ""),
                    trace=trace,
                    step=TraceStep(
                        phase="retrieval",
                        action="replan_retrieval",
                        reason="评估未通过，按策略重规划",
                        outputs_summary={
                            "top_k_boost": state.get("top_k_boost"),
                            "query_override": bool(state.get("query_override")),
                        },
                        verdict="retry",
                    ),
                )
                continue

            warnings.append("检索质量仍不理想：将进入生成阶段（结果可能不完整）")
            degraded = True
            goals.mark("sg1", SubgoalStatus.FAILED, notes="retrieval_below_threshold")
            break

        if not retrieval_passed and not degraded:
            degraded = True
            warnings.append("已达到最大检索轮次仍未满足检索质量门，将继续生成但结果可能不完整")
            goals.mark("sg1", SubgoalStatus.FAILED, notes="retrieval_exhausted")

        # --- Build prompt ---
        global_step += 1
        system_prompt_template = get_perspective_prompt(request.perspective)
        retrieved = state.get("retrieved", [])
        retrieved_contexts = [
            RetrievedContext(chunk_id=c.chunk_id, content=c.content, score=c.score) for c in retrieved
        ]
        user_prompt = build_analysis_user_prompt(
            system_prompt_template=system_prompt_template,
            contract_text=document.text_content,
            retrieved_contexts=retrieved_contexts,
        )
        state["system_prompt_template"] = system_prompt_template
        state["user_prompt"] = user_prompt

        self._emit(
            progress_callback=progress_callback,
            message="Agent：已构建分析 prompt",
            progress=prog(55, ""),
            trace=trace,
            step=TraceStep(
                phase="prompt",
                action="build_prompt",
                reason="将检索上下文与合同全文交给 LLM",
                outputs_summary={"contexts_used": len(retrieved_contexts)},
                verdict="ok",
            ),
        )

        # --- Generation loop ---
        goals.mark("sg2", SubgoalStatus.IN_PROGRESS)
        risks: list[RiskCard] = []
        llm_raw = ""
        # 首次 + 重试：max_generation_retries 表示“额外重试次数”
        max_attempts = policy.max_generation_retries + 1
        for attempt in range(1, max_attempts + 1):
            if global_step >= max_steps:
                break
            global_step += 1
            strict = attempt > 1

            content_buffer = ""
            async for chunk in stream_analysis(
                state["user_prompt"],
                state["system_prompt_template"],
                strict_json=strict,
            ):
                content_buffer += chunk
            llm_raw = content_buffer
            state["llm_output"] = llm_raw

            parsed = _parse_risk_json(llm_raw)
            if not parsed:
                parsed = _build_rule_based_risks(document, request, retrieved)
            gv = evaluate_generation(
                raw_text=llm_raw,
                parsed_risks=parsed,
                policy_min_risks=policy.min_risks_accept,
                policy_min_complete_ratio=policy.min_complete_risks_ratio,
            )

            self._emit(
                progress_callback=progress_callback,
                message=f"Agent：生成评估 (第{attempt}/{max_attempts}次) -> {'通过' if gv.passed else '未通过'}",
                progress=prog(65 + attempt * 8, ""),
                trace=trace,
                step=TraceStep(
                    phase="generation",
                    action="evaluate_generation",
                    reason="质量门：JSON/条数/字段完整率",
                    outputs_summary={
                        "json_parse_ok": gv.json_parse_ok,
                        "risk_count": gv.risk_count,
                        "complete_ratio": gv.complete_ratio,
                        "strict_mode": strict,
                    },
                    verdict="pass" if gv.passed else "fail",
                    policy_hint=gv.suggested_action,
                ),
            )

            if gv.passed:
                generation_passed = True
                risks = [_create_risk_card(d, document.id, i) for i, d in enumerate(parsed)]
                attach_evidence_to_risks(risks, retrieved)
                goals.mark("sg2", SubgoalStatus.DONE)
                goals.mark("sg3", SubgoalStatus.DONE)
                break

            if gv.suggested_action == "retry_strict" and attempt < max_attempts:
                warnings.append(f"生成质量不足，将使用严格 JSON 模式重试（第{attempt}次已完成）")
                continue

            degraded = True
            risks = [_create_risk_card(d, document.id, i) for i, d in enumerate(parsed)]
            attach_evidence_to_risks(risks, retrieved)
            warnings.extend(gv.reasons)
            goals.mark("sg2", SubgoalStatus.FAILED, notes="generation_below_threshold")
            break

        if not generation_passed and not degraded:
            degraded = True
            warnings.append("生成未通过质量门且未触发降级分支，强制降级交付")
            if state.get("llm_output"):
                parsed = _parse_risk_json(state["llm_output"])
                if not parsed:
                    parsed = _build_rule_based_risks(document, request, retrieved)
                risks = [_create_risk_card(d, document.id, i) for i, d in enumerate(parsed)]
                attach_evidence_to_risks(risks, retrieved)

        # --- Assemble result ---
        duration_ms = int((time.time() - start_time) * 1000)
        high_count = sum(1 for r in risks if r.severity.value == "高")
        medium_count = sum(1 for r in risks if r.severity.value == "中")
        low_count = sum(1 for r in risks if r.severity.value == "低")

        if degraded or not generation_passed:
            summary = (
                "【注意】本次分析未达到理想质量门槛，以下为尽力输出或空结果。"
                f" 风险条数：{len(risks)}。"
                + ("；" + " ".join(warnings) if warnings else "")
                + " 建议人工复核合同原文与检索上下文是否充足。"
            )
            goals.mark("sg3", SubgoalStatus.FAILED, notes="degraded_deliverable")
        else:
            summary = (
                f"分析完成。共发现 {len(risks)} 个风险点，"
                f"其中高风险 {high_count} 个，中风险 {medium_count} 个，低风险 {low_count} 个。"
            )

        final_eval = evaluate_final_deliverable(
            generation_passed=generation_passed,
            degraded=degraded,
            warnings=warnings,
        )

        self._emit(
            progress_callback=progress_callback,
            message="Agent：交付前最终评估",
            progress=prog(92, ""),
            trace=trace,
            step=TraceStep(
                phase="finish",
                action="final_eval",
                reason="是否可交付 / 是否降级",
                outputs_summary=final_eval,
                verdict="degraded" if degraded else "ok",
            ),
        )

        result = AnalysisResult(
            document_id=document.id,
            perspective=request.perspective,
            risks=risks,
            summary=summary,
            analyzed_at=datetime.utcnow(),
            duration_ms=duration_ms,
        )

        # Attach trace for observability (not part of pydantic model — store on agent instance if needed)
        # Consumers can read last trace via OrchestratorAgent.last_trace if we set it:
        self.last_trace = trace
        self.last_goals = goals

        return result
