"""Cross-encoder reranking for retrieved chunks (sentence-transformers)."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from types import SimpleNamespace

import numpy as np

from ..config import get_rerank_batch_size, get_rerank_model
from ..models import RetrievedChunk

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_cross_encoder():
    import torch
    import huggingface_hub
    from sentence_transformers import CrossEncoder

    # RERANKER_MODEL takes precedence over RERANK_MODEL (backward compat)
    name = os.getenv("RERANKER_MODEL") or get_rerank_model()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("[RERANK] Loading CrossEncoder: %s (device=%s)", name, device)
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    huggingface_hub.model_info = lambda *args, **kwargs: SimpleNamespace(tags=[])
    return CrossEncoder(
        name,
        device=device,
        local_files_only=True,
        trust_remote_code=False,
    )


def rerank(query: str, texts: list[str]) -> list[float]:
    """Score query-text pairs and return raw CrossEncoder logits.

    Simple API for testing and direct use.  Returns one float per text in the
    same order as *texts*; higher means more relevant.  Returns zeros on error.
    """
    if not texts or not (query or "").strip():
        return [0.0] * len(texts)
    try:
        model = _get_cross_encoder()
    except Exception as e:
        logger.warning("[RERANK] CrossEncoder load failed: %s", e)
        return [0.0] * len(texts)

    pairs = [(query, t) for t in texts]
    batch = get_rerank_batch_size()
    try:
        raw = model.predict(pairs, batch_size=batch, show_progress_bar=False)
        return np.asarray(raw, dtype=np.float64).reshape(-1).tolist()
    except Exception as e:
        logger.warning("[RERANK] predict failed: %s", e)
        return [0.0] * len(texts)


def rerank_retrieved_chunks(query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Rescore and reorder chunks by query–passage relevance. No-op if disabled or empty."""
    if not chunks or not (query or "").strip():
        return chunks
    try:
        model = _get_cross_encoder()
    except Exception as e:
        logger.warning("[RERANK] CrossEncoder load failed, skipping rerank: %s", e)
        return chunks

    pairs = [(query, c.content) for c in chunks]
    batch = get_rerank_batch_size()
    try:
        raw = model.predict(pairs, batch_size=batch, show_progress_bar=False)
    except Exception as e:
        logger.warning("[RERANK] predict failed, skipping rerank: %s", e)
        return chunks

    arr = np.asarray(raw, dtype=np.float64).reshape(-1)
    lo, hi = float(arr.min()), float(arr.max())
    span = hi - lo if hi > lo else 1.0
    norm = (arr - lo) / span

    reranked: list[RetrievedChunk] = []
    for c, s in zip(chunks, norm.tolist()):
        meta = {**c.metadata, "vector_score": c.score, "rerank": True}
        reranked.append(c.model_copy(update={"score": float(s), "metadata": meta}))
    reranked.sort(key=lambda x: x.score, reverse=True)
    logger.debug("[RERANK] reranked %d chunks", len(reranked))
    return reranked
