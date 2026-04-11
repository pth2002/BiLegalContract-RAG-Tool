"""Execution trace for observability and debugging."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TraceStep:
    """One step in the agent run."""

    phase: str
    action: str
    reason: str
    inputs_summary: dict[str, Any] = field(default_factory=dict)
    outputs_summary: dict[str, Any] = field(default_factory=dict)
    verdict: str = ""
    policy_hint: str = ""
    ts: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "action": self.action,
            "reason": self.reason,
            "inputs_summary": self.inputs_summary,
            "outputs_summary": self.outputs_summary,
            "verdict": self.verdict,
            "policy_hint": self.policy_hint,
            "ts": self.ts,
        }


@dataclass
class AgentTrace:
    steps: list[TraceStep] = field(default_factory=list)
    """High-level decision / execution / critique records (one per runtime iteration)."""
    decision_records: list[dict[str, Any]] = field(default_factory=list)

    def append(self, step: TraceStep) -> None:
        self.steps.append(step)

    def append_decision_record(
        self,
        *,
        iteration: int,
        decision: dict[str, Any],
        execution: dict[str, Any],
        critique: dict[str, Any],
    ) -> None:
        self.decision_records.append(
            {
                "iteration": iteration,
                "decision": decision,
                "execution": execution,
                "critique": critique,
            }
        )

    def to_list(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self.steps]
