"""Evidence grounding helpers for modern RAG outputs."""

from __future__ import annotations

import re

from ..models import EvidenceRef, RetrievedChunk, RiskCard 


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _overlap_score(a: str, b: str) -> float:
    a_norm = _normalize(a)
    b_norm = _normalize(b)
    if not a_norm or not b_norm:
        return 0.0
    if a_norm in b_norm:
        return min(1.0, len(a_norm) / max(len(b_norm), 1) + 0.35)
    a_tokens = set(re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", a_norm.lower()))
    b_tokens = set(re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", b_norm.lower()))
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens)


def _best_citations(text: str, retrieved_chunks: list[RetrievedChunk], limit: int = 2) -> list[EvidenceRef]:
    scored: list[EvidenceRef] = []
    for chunk in retrieved_chunks:
        score = _overlap_score(text, chunk.content)
        if score <= 0:
            continue
        quote = chunk.content[:220]
        scored.append(EvidenceRef(chunk_id=chunk.chunk_id, quote=quote, score=round(score, 4)))
    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[:limit]


def attach_evidence_to_risks(risks: list[RiskCard], retrieved_chunks: list[RetrievedChunk]) -> dict[str, float]:
    """Enrich risks in-place with best evidence snippets and aggregate grounding stats."""

    grounded = 0
    for risk in risks:
        source_text = risk.original_text or risk.risk_description or risk.clause_title
        citations = _best_citations(source_text, retrieved_chunks)
        risk.citations = citations
        risk.grounding_score = citations[0].score if citations else 0.0
        if citations:
            grounded += 1

    total = len(risks)
    ratio = grounded / total if total else 1.0
    avg = sum((risk.grounding_score or 0.0) for risk in risks) / total if total else 1.0
    return {
        "grounded_count": grounded,
        "total_risks": total,
        "grounding_ratio": round(ratio, 4),
        "average_grounding_score": round(avg, 4),
    }
