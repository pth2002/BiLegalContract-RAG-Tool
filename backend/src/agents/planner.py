"""Initial plan construction: template-first, optional LLM-generated dynamic plan."""

from __future__ import annotations 

import json
import logging
from typing import Optional

from ..config import get_llm_num_ctx, get_llm_num_predict, get_llm_reasoning, get_llm_temperature, get_ollama_model
from ..models import AnalysisRequest, PerspectiveType
from ..services.ollama_service import get_ollama_client
from .action_models import AgentPlan, PlanStep, PlanStepStatus
from .agent_state import AgentRuntimeState

logger = logging.getLogger(__name__)

_JSON_RETRIES = 3


def infer_allowed_tools_from_goal(goal: str) -> list[str]:
    """由子目标文本推断本步允许工具（v4 计划约束）。"""
    g = goal or ""
    if any(x in g for x in ("结构", "理解", "通读", "全文框架", "目录")):
        return ["ensure_index", "retrieve_context", "extract_clauses"]
    if any(x in g for x in ("检索", "向量", "上下文", "条款片段", "RAG", "chunk")):
        return ["ensure_index", "retrieve_context", "widen_retrieval", "refine_query"]
    if any(x in g for x in ("风险", "分析", "JSON", "违约", "评估")):
        return ["analyze_risks", "retry_generation_strict", "summarize_partial"]
    if any(x in g for x in ("证据", "验证", "对齐", "引用", "交付", "完成")):
        return ["verify_evidence", "finish", "degrade_output"]
    return ["retrieve_context", "analyze_risks", "verify_evidence", "finish"]


async def generate_plan_from_state(state: AgentRuntimeState) -> AgentPlan:
    """
    v4：基于完整 state 生成结构化计划 { steps: [{id, goal}, ...] }，
    每步写入 preferred_tools + allowed_tools（驱动后续决策约束）。
    """
    perspective = state.request.perspective
    label = "甲方" if perspective == PerspectiveType.PARTY_A else "乙方"
    client = get_ollama_client()
    model = get_ollama_model()
    sys_msg = (
        "你是合同审查总规划师。只输出 JSON，不要 markdown。\n"
        "格式：{\"steps\":[{\"id\":\"1\",\"goal\":\"...\"},...]}，至少 3 步，建议含："
        "理解/检索/风险分析/证据验证 等阶段。goal 用简短中文。"
    )
    user_msg = (
        f"终局目标：{state.primary_goal}\n"
        f"视角：{label}（{perspective.value}）\n"
        f"合同长度（字符）：{len(state.document.text_content or '')}\n"
        "请输出 steps。"
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
            if not isinstance(raw_steps, list) or not raw_steps:
                raise ValueError("no steps")
            steps: list[PlanStep] = []
            for i, item in enumerate(raw_steps[:10]):
                if isinstance(item, dict):
                    sid = str(item.get("id") or f"s{i+1}")[:32]
                    g = str(item.get("goal") or item.get("title") or "子任务")[:500]
                else:
                    sid = f"s{i+1}"
                    g = str(item)[:500]
                allowed = infer_allowed_tools_from_goal(g)
                al = list(allowed)
                steps.append(
                    PlanStep(
                        id=sid,
                        title=g[:120],
                        goal=g,
                        preferred_tools=al,
                        allowed_tools=list(al),
                        success_criteria="完成本步目标或触发降级",
                        max_attempts=4,
                        status=PlanStepStatus.IN_PROGRESS if i == 0 else PlanStepStatus.PENDING,
                    )
                )
            plan = AgentPlan(steps=steps, version=1, notes="v4_generate_plan_from_state")
            logger.info("[PLANNER] v4 plan from state: %d steps", len(steps))
            return plan
        except Exception as e:
            logger.warning("[PLANNER] generate_plan_from_state attempt %d/%d: %s", attempt, _JSON_RETRIES, e)
    logger.warning("[PLANNER] generate_plan_from_state → template fallback")
    return build_initial_plan(state.request, refine_with_llm=False)


def build_initial_plan(request: AnalysisRequest, *, refine_with_llm: bool = False) -> AgentPlan:
    """Template-driven plan aligned with contract review subgoals."""
    perspective = request.perspective
    label = "甲方" if perspective == PerspectiveType.PARTY_A else "乙方"

    steps = [
        PlanStep(
            id="p1_context",
            title="建立可引用的检索上下文",
            goal=f"为{label}视角准备足够相关、可引用的合同条款片段（向量检索+RAG）",
            preferred_tools=[
                "ensure_index",
                "retrieve_context",
                "widen_retrieval",
                "refine_query",
            ],
            success_criteria="检索片段数量与相似度达到策略阈值，或已用尽检索预算",
            max_attempts=4,
            status=PlanStepStatus.IN_PROGRESS,
        ),
        PlanStep(
            id="p2_analyze",
            title="生成结构化风险分析",
            goal="基于检索上下文与全文输出 JSON 风险数组，字段完整、可解析",
            preferred_tools=["analyze_risks", "retry_generation_strict", "summarize_partial"],
            success_criteria="解析成功且风险条数与字段完整率满足策略，或触发降级",
            max_attempts=3,
            status=PlanStepStatus.PENDING,
        ),
        PlanStep(
            id="p3_verify",
            title="证据对齐与交付",
            goal="在可能时校验风险中的原文摘录是否被检索上下文支持，并完成交付",
            preferred_tools=["verify_evidence", "finish", "degrade_output"],
            success_criteria="验证通过或明确降级说明后结束",
            max_attempts=3,
            status=PlanStepStatus.PENDING,
        ),
    ]

    plan = AgentPlan(steps=steps, version=1, notes="template_v1")

    if refine_with_llm:
        # Hook for future LLM plan refinement — keep deterministic default for production stability
        logger.debug("[PLANNER] refine_with_llm requested but not enabled in this build")

    return plan


async def generate_llm_plan(request: AnalysisRequest) -> AgentPlan:
    """
    LLM 动态计划：输出 steps 字符串列表，映射为 PlanStep（保留统一 preferred_tools 模板）。
    """
    perspective = request.perspective
    label = "甲方" if perspective == PerspectiveType.PARTY_A else "乙方"
    client = get_ollama_client()
    model = get_ollama_model()
    sys_msg = (
        "你是合同分析规划助手。目标：分析合同风险。"
        "只输出一个 JSON 对象，键 steps（字符串数组），每个元素为一句简短分析子任务（中文）。"
        "不要 markdown，不要其它文字。"
    )
    user_msg = (
        f"视角：{label}（{perspective.value}）。\n"
        "请制定一个分析计划，例如涵盖付款条款、违约条款、终止条款等（可按需增减）。\n"
        "输出：{\"steps\":[\"...\",\"...\"]}"
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
                    "num_predict": min(get_llm_num_predict(), 512),
                    "reasoning": get_llm_reasoning(),
                },
            )
            raw = response["message"]["content"].strip()
            start, end = raw.find("{"), raw.rfind("}")
            if start == -1 or end <= start:
                raise ValueError("no json")
            data = json.loads(raw[start : end + 1])
            step_titles = data.get("steps") or data.get("plan")
            if not isinstance(step_titles, list) or not step_titles:
                raise ValueError("invalid steps")
            titles = [str(t)[:120] for t in step_titles[:8]]
            n = len(titles)
            steps: list[PlanStep] = []
            for i, title in enumerate(titles):
                tid = f"llm_p{i+1}"
                steps.append(
                    PlanStep(
                        id=tid,
                        title=title,
                        goal=f"完成子任务：{title}（{label}视角）",
                        preferred_tools=_preferred_tools_for_step(i, n),
                        success_criteria="达到策略阈值或触发降级",
                        max_attempts=3,
                        status=PlanStepStatus.IN_PROGRESS if i == 0 else PlanStepStatus.PENDING,
                    )
                )
            plan = AgentPlan(steps=steps, version=1, notes="llm_plan_v1")
            logger.info("[PLANNER] LLM plan generated %d steps", len(steps))
            return plan
        except Exception as e:
            logger.warning("[PLANNER] LLM plan attempt %d/%d failed: %s", attempt, _JSON_RETRIES, e)
    logger.warning("[PLANNER] LLM plan failed → template fallback")
    return build_initial_plan(request, refine_with_llm=False)


def _preferred_tools_for_step(index: int, total: int) -> list[str]:
    """动态计划中：首步偏检索、末步偏校验交付、中间偏分析。"""
    if total <= 1:
        return ["ensure_index", "retrieve_context", "analyze_risks", "verify_evidence", "finish"]
    if index == 0:
        return ["ensure_index", "retrieve_context", "widen_retrieval", "refine_query"]
    if index == total - 1:
        return ["verify_evidence", "finish", "degrade_output"]
    return ["analyze_risks", "retry_generation_strict", "summarize_partial"]


async def build_plan_for_request(request: AnalysisRequest) -> AgentPlan:
    """统一入口：始终使用 LLM 动态计划，失败时降级到模板。"""
    return await generate_llm_plan(request)


def current_plan_step(plan: AgentPlan, index: int) -> Optional[PlanStep]:
    if 0 <= index < len(plan.steps):
        return plan.steps[index]
    return None
