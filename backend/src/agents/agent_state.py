"""Runtime state for a single contract-review agent run."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from ..models import AnalysisRequest, Document, RetrievedChunk, RiskCard
from .action_models import AgentPlan
from .memory import AgentMemory


@dataclass
class AgentState:
    """
    轻量「大脑」视图：便于决策器 / 日志 / Debug（与 AgentRuntimeState 并存）。
    由 `build_agent_state_view` 从运行时状态快照生成。
    """

    user_query: str
    document_id: str
    retrieved_chunks: list
    current_answer: str
    history: list[dict[str, Any]]
    step_count: int
    confidence: float


def build_agent_state_view(
    runtime: "AgentRuntimeState",
    *,
    step_count: int,
    history: list[dict[str, Any]],
    confidence: float,
) -> AgentState:
    """从完整运行时状态构造 AgentState 快照。"""
    rq = f"{runtime.request.perspective.value}"
    if runtime.request.options:
        rq = f"{rq} | {runtime.request.options!r}"
    return AgentState(
        user_query=rq,
        document_id=str(runtime.document.id),
        retrieved_chunks=list(runtime.retrieved_chunks),
        current_answer=runtime.last_llm_raw or "",
        history=list(history),
        step_count=step_count,
        confidence=confidence,
    )


@dataclass
class BudgetUsage:
    """Strict budget counters for policy enforcement."""

    loop_iterations: int = 0
    retrieval_calls: int = 0
    refine_calls: int = 0
    llm_calls: int = 0
    replan_rounds: int = 0
    tool_calls: int = 0


@dataclass
class AgentRuntimeState:
    """
    Mutable runtime state for one analysis session.
    Tools and runtime mutate this object in-place; critic/replanner read it.
    """

    request: AnalysisRequest
    document: Document
    primary_goal: str = "生成可交付的结构化合同风险分析（风险卡）"
    plan: Optional[AgentPlan] = None
    current_step_index: int = 0
    observations: list[str] = field(default_factory=list)
    retrieved_chunks: list[RetrievedChunk] = field(default_factory=list)
    last_queries: list[str] = field(default_factory=list)
    last_llm_raw: str = ""
    generated_candidates: list[str] = field(default_factory=list)
    accepted_risks: list[RiskCard] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    degraded: bool = False
    finished: bool = False
    budget: BudgetUsage = field(default_factory=BudgetUsage)
    working_memory: AgentMemory = field(default_factory=AgentMemory)
    final_summary: Optional[str] = None
    query_override: Optional[str] = None
    top_k_boost: int = 0
    system_prompt_template: Optional[str] = None
    user_prompt: Optional[str] = None
    evidence_verification_passed: Optional[bool] = None
    indexed: bool = False
    started_at: datetime = field(default_factory=datetime.utcnow)
    meta: dict[str, Any] = field(default_factory=dict)
    # 决策/反思辅助（可由 decider、reflection 更新）
    runtime_confidence: float = 0.5
    # v4 ReAct：显式思考链 + 观测
    thought_history: list[dict[str, Any]] = field(default_factory=list)
    observation_history: list[str] = field(default_factory=list)
    # v5 Goal System：子目标拆解 + 动态切换
    sub_goals: list[str] = field(default_factory=list)
    current_goal: str = ""
    current_goal_index: int = 0
    completed_goals: list[str] = field(default_factory=list)
    # v5：策略模型（最近策略建议，供 decider 读取）
    latest_strategy: str = ""
