"""Rule-based policy layer: budgets, guards, and next-action hints."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import (
    get_agent_max_generation_retries,
    get_agent_max_identical_action_repeats,
    get_agent_max_loop_steps,
    get_agent_max_replan_rounds,
    get_agent_max_refine_rounds,
    get_agent_max_retrieval_rounds,
    get_agent_min_decider_confidence,
    get_agent_reflection_score_threshold,
    get_agent_self_correction_max,
)


@dataclass(frozen=True)
class AgentPolicy:
    """Tunable thresholds; prefer env-driven values from config."""

    max_retrieval_rounds: int
    max_refine_rounds: int
    max_generation_retries: int
    min_chunks_ok: int
    min_chunks_relaxed: int
    min_avg_score_ok: float
    min_max_score_ok: float
    min_focus_coverage_ratio: float
    min_risks_accept: int
    min_complete_risks_ratio: float
    max_loop_iterations: int
    max_replan_rounds: int
    min_decider_confidence: float
    max_identical_action_repeats: int
    reflection_score_threshold: float
    self_correction_max: int

    @classmethod
    def from_config(cls) -> "AgentPolicy":
        return cls(
            max_retrieval_rounds=get_agent_max_retrieval_rounds(),
            max_refine_rounds=get_agent_max_refine_rounds(),
            max_generation_retries=get_agent_max_generation_retries(),
            min_chunks_ok=3,
            min_chunks_relaxed=2,
            min_avg_score_ok=0.42,
            min_max_score_ok=0.40,
            min_focus_coverage_ratio=0.25,
            min_risks_accept=1,
            min_complete_risks_ratio=0.6,
            max_loop_iterations=get_agent_max_loop_steps(),
            max_replan_rounds=get_agent_max_replan_rounds(),
            min_decider_confidence=get_agent_min_decider_confidence(),
            max_identical_action_repeats=max(get_agent_max_identical_action_repeats(), 32),
            reflection_score_threshold=get_agent_reflection_score_threshold(),
            self_correction_max=get_agent_self_correction_max(),
        )


def should_allow_finish(
    *,
    retrieval_passed: bool,
    generation_passed: bool,
    degraded: bool,
    global_step: int,
    max_steps: int,
) -> bool:
    if global_step >= max_steps:
        return True
    if degraded:
        return True
    return retrieval_passed and generation_passed
