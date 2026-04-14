"""Evaluators: quality gates for retrieval and generation (mature agent)."""
 
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models import PerspectiveType, RetrievedChunk
from ..services.retrieval_service import get_focus_areas_for_retrieval


@dataclass(frozen=True)
class RetrievalVerdict:
    passed: bool
    quality: str  # good | ok | poor
    metrics: dict[str, Any]
    suggested_action: str  # proceed | refine_query | widen_retrieval | abort_max_rounds


@dataclass(frozen=True)
class GenerationVerdict:
    passed: bool
    json_parse_ok: bool
    risk_count: int
    complete_ratio: float
    reasons: list[str]
    suggested_action: str  # proceed | retry_strict | degrade


def evaluate_retrieval(
    *,
    chunks: list[RetrievedChunk],
    perspective: PerspectiveType,
    options: dict[str, Any] | None,
    policy_min_chunks_ok: int,
    policy_min_chunks_relaxed: int,
    policy_min_avg: float,
    policy_min_max: float,
    policy_min_focus_ratio: float,
) -> RetrievalVerdict:
    count = len(chunks)
    avg_score = sum(c.score for c in chunks) / count if count else 0.0
    max_score = max((c.score for c in chunks), default=0.0)
    text_blob = "\n".join(c.content for c in chunks)
    focus_areas = get_focus_areas_for_retrieval(perspective, options)
    covered = 0
    for fa in focus_areas:
        if fa and fa in text_blob:
            covered += 1
    focus_ratio = (covered / len(focus_areas)) if focus_areas else 1.0

    metrics: dict[str, Any] = {
        "retrieved_count": count,
        "avg_score": round(avg_score, 4),
        "max_score": round(max_score, 4),
        "focus_areas": focus_areas,
        "focus_covered": covered,
        "focus_coverage_ratio": round(focus_ratio, 4),
    }

    if count >= policy_min_chunks_ok and avg_score >= policy_min_avg and focus_ratio >= policy_min_focus_ratio:
        quality = "good"
        passed = True
        action = "proceed"
    elif count >= policy_min_chunks_relaxed and max_score >= policy_min_max:
        quality = "ok"
        passed = True
        action = "proceed"
    elif count >= 3 and max_score >= 0.35:
        quality = "ok"
        passed = True
        action = "proceed"
    else:
        quality = "poor"
        passed = False
        if count < 2:
            action = "widen_retrieval"
        elif focus_ratio < policy_min_focus_ratio:
            action = "refine_query"
        else:
            action = "refine_query"

    return RetrievalVerdict(
        passed=passed,
        quality=quality,
        metrics=metrics,
        suggested_action=action,
    )


def evaluate_generation(
    *,
    raw_text: str,
    parsed_risks: list[dict],
    policy_min_risks: int,
    policy_min_complete_ratio: float,
) -> GenerationVerdict:
    reasons: list[str] = []
    json_parse_ok = bool(parsed_risks)
    if not json_parse_ok:
        reasons.append("无法解析为JSON数组或为空")

    risk_count = len(parsed_risks)
    if risk_count < policy_min_risks:
        reasons.append(f"风险条数过少({risk_count}<{policy_min_risks})")

    required = {"clause_title", "severity", "risk_description"}
    complete = 0
    for r in parsed_risks:
        if all(r.get(k) for k in required):
            complete += 1
    complete_ratio = (complete / risk_count) if risk_count else 0.0
    if complete_ratio < policy_min_complete_ratio and risk_count > 0:
        reasons.append(f"字段完整率偏低({complete_ratio:.2f}<{policy_min_complete_ratio})")

    passed = json_parse_ok and risk_count >= policy_min_risks and complete_ratio >= policy_min_complete_ratio

    if passed:
        action = "proceed"
    elif not json_parse_ok or risk_count < policy_min_risks:
        action = "retry_strict"
    else:
        action = "degrade"

    return GenerationVerdict(
        passed=passed,
        json_parse_ok=json_parse_ok,
        risk_count=risk_count,
        complete_ratio=round(complete_ratio, 4),
        reasons=reasons,
        suggested_action=action,
    )


def evaluate_final_deliverable(
    *,
    generation_passed: bool,
    degraded: bool,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "deliverable_ok": generation_passed and not degraded,
        "degraded": degraded,
        "warnings": warnings,
    }
