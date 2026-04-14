"""Typed models for plan, decisions, execution, and critique.""" 

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class PlanStepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"


class PlanStep(BaseModel):
    id: str
    title: str
    goal: str
    preferred_tools: list[str] = Field(default_factory=list)
    # v4：若非空，与 preferred_tools 一并用于「当前步允许工具」约束（通常由 generate_plan_from_state 填充）
    allowed_tools: list[str] = Field(default_factory=list)
    success_criteria: str = ""
    max_attempts: int = 3
    status: PlanStepStatus = PlanStepStatus.PENDING
    attempts: int = 0


class AgentPlan(BaseModel):
    steps: list[PlanStep] = Field(default_factory=list)
    version: int = 1
    notes: str = ""


class ActionDecision(BaseModel):
    action_name: str
    action_input: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    expected_result: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    # v3：备选说明 / 多工具一步（由 runtime 顺序执行）
    alt_plan: str = ""
    tool_chain: list[dict[str, Any]] = Field(default_factory=list)
    # v4 ReAct：显式思考
    thought: str = ""


class ToolExecutionResult(BaseModel):
    ok: bool
    tool_name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class CriticNextHint(str, Enum):
    PROCEED = "proceed"
    RETRY = "retry"
    REPLAN = "replan"
    STOP = "stop"
    DEGRADE = "degrade"


class CriticVerdict(BaseModel):
    acceptable: bool
    plan_step_complete: bool = False
    next_hint: CriticNextHint = CriticNextHint.PROCEED
    critique_notes: str = ""
    evidence_grounded: Optional[bool] = None
    rule_verdict_summary: dict[str, Any] = Field(default_factory=dict)
    # v3：LLM 门控 / 自评时可写入
    llm_critique: str = ""
    # v5 Strategy Learning：critic 输出的策略改进建议
    strategy_suggestion: str = ""
