"""Offline retrieval metrics: Recall@K / Hit@K against labeled relevant chunk_ids."""

from __future__ import annotations

import logging
from typing import Any
from ..models import Document, PerspectiveType, RetrievedChunk
from .chunking_service import chunk_document 

logger = logging.getLogger(__name__)


def recall_at_k(retrieved_ids_ordered: list[str], relevant_ids: set[str], k: int) -> float:
    """Fraction of relevant chunks that appear in the top-k retrieval positions.

    |retrieved ∩ relevant| / |relevant|, using the first k positions of the ranked list.
    If there are no relevant labels, returns 1.0 (vacuous success).
    """
    if not relevant_ids:
        return 1.0
    top_k_set = set(retrieved_ids_ordered[:k])
    hits = len(top_k_set & relevant_ids)
    return hits / len(relevant_ids)


def hit_rate_at_k(retrieved_ids_ordered: list[str], relevant_ids: set[str], k: int) -> float:
    """1.0 if at least one relevant chunk is in top-k, else 0.0."""
    if not relevant_ids:
        return 1.0
    top_k_set = set(retrieved_ids_ordered[:k])
    return 1.0 if (top_k_set & relevant_ids) else 0.0


def mrr(retrieved_ids_ordered: list[str], relevant_ids: set[str]) -> float:
    """Mean Reciprocal Rank: 1/rank of first relevant chunk."""
    if not relevant_ids:
        return 1.0
    for i, chunk_id in enumerate(retrieved_ids_ordered, start=1):
        if chunk_id in relevant_ids:
            return 1.0 / i
    return 0.0


def chunk_ids_for_document(document: Document) -> list[str]:
    """Ordered chunk_ids produced by the same chunking as indexing."""
    return [c.chunk_id for c in chunk_document(document)]


async def evaluate_retrieval_case(
    *,
    document: Document,
    perspective: PerspectiveType,
    options: dict[str, Any] | None,
    relevant_chunk_ids: set[str],
    ks: list[int],
    final_top_k: int | None = None,
    reindex: bool = True,
) -> dict[str, Any]:
    """Index document (optional), run merged retrieval, compute Recall@K / Hit@K per k."""
    ks_sorted = sorted({int(k) for k in ks if int(k) > 0})
    if not ks_sorted:
        raise ValueError("ks must contain at least one positive integer")

    all_ids = set(chunk_ids_for_document(document))
    unknown = relevant_chunk_ids - all_ids
    if unknown:
        logger.warning(
            "[RAG_EVAL] Gold chunk_ids not found after chunking (check labels / chunking config): %s",
            sorted(unknown),
        )

    from .indexing_service import index_document
    from .retrieval_service import retrieve_contexts_merged
    from .vector_store_service import init_vector_store

    await init_vector_store()
    if reindex:
        await index_document(document)

    fk = final_top_k if final_top_k is not None else max(ks_sorted)
    retrieved: list[RetrievedChunk] = await retrieve_contexts_merged(
        document_id=document.id,
        session_id=document.session_id,
        perspective=perspective,
        options=options,
        final_top_k=fk,
        document=document,
    )
    ordered_ids = [c.chunk_id for c in retrieved]

    per_k: dict[str, dict[str, float]] = {}
    for k in ks_sorted:
        per_k[str(k)] = {
            "recall": round(recall_at_k(ordered_ids, relevant_chunk_ids, k), 6),
            "hit": hit_rate_at_k(ordered_ids, relevant_chunk_ids, k),
        }

    return {
        "document_id": str(document.id),
        "session_id": document.session_id,
        "perspective": perspective.value,
        "relevant_count": len(relevant_chunk_ids),
        "retrieved_count": len(ordered_ids),
        "retrieved_ids": ordered_ids,
        "per_k": per_k,
    }
