"""Working memory for a single agent run (episodic persistence optional later)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentMemory:
    """Tracks attempts, failures, and notes for bounded replanning and anti-loop."""

    attempted_queries: list[str] = field(default_factory=list)
    failed_action_signatures: list[str] = field(default_factory=list)
    rejected_outputs: list[str] = field(default_factory=list)
    critique_notes: list[str] = field(default_factory=list)
    accepted_evidence_chunk_ids: set[str] = field(default_factory=set)
    last_actions: list[tuple[str, str]] = field(default_factory=list)  # (tool_name, input_fingerprint)
    # 逐步调试历史（动作、反思摘要等），供 Decider 上下文与 Debug
    step_history: list[dict[str, Any]] = field(default_factory=list)

    def add_step(self, record: dict[str, Any], max_keep: int = 64) -> None:
        self.step_history.append(record)
        if len(self.step_history) > max_keep:
            self.step_history = self.step_history[-max_keep:]

    def fingerprint_input(self, tool_name: str, action_input: dict[str, Any]) -> str:
        import json

        try:
            return f"{tool_name}:{json.dumps(action_input, sort_keys=True, ensure_ascii=False)}"
        except Exception:
            return f"{tool_name}:<unserializable>"

    def record_action(self, tool_name: str, action_input: dict[str, Any]) -> None:
        self.last_actions.append((tool_name, self.fingerprint_input(tool_name, action_input)))
        if len(self.last_actions) > 32:
            self.last_actions = self.last_actions[-32:]

    def identical_streak(self, tool_name: str, fp: str) -> int:
        streak = 0
        for n, f in reversed(self.last_actions):
            if n == tool_name and f == fp:
                streak += 1
            else:
                break
        return streak


# 文档中的 Memory 命名兼容
Memory = AgentMemory
