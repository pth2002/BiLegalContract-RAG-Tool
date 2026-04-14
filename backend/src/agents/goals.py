"""Explicit agent goals and subgoals (mature autonomous agent).""" 

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SubgoalStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Subgoal:
    id: str
    description: str
    status: SubgoalStatus = SubgoalStatus.PENDING
    notes: str = ""


@dataclass
class AgentGoalState:
    """What the agent is trying to achieve and how far along it is."""

    primary: str = "生成高质量、可解析、覆盖关键条款的合同风险分析（结构化风险卡）"
    subgoals: list[Subgoal] = field(
        default_factory=lambda: [
            Subgoal("sg1", "获得足够相关、可引用的检索上下文（RAG）"),
            Subgoal("sg2", "生成可被稳定解析为 JSON 数组的结构化输出"),
            Subgoal("sg3", "风险条目在数量与字段上达到最低可交付标准"),
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary": self.primary,
            "subgoals": [
                {"id": s.id, "description": s.description, "status": s.status.value, "notes": s.notes}
                for s in self.subgoals
            ],
        }

    def mark(self, subgoal_id: str, status: SubgoalStatus, notes: str = "") -> None:
        for s in self.subgoals:
            if s.id == subgoal_id:
                s.status = status
                s.notes = notes
                break
