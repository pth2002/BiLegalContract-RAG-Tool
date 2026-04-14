"""Embedding service — SentenceTransformer backend with multi-model support and offline fallback."""

from __future__ import annotations

import hashlib
import logging
import math
import os 
import re
from collections import Counter
from functools import lru_cache
from typing import Any

from ..config import get_embedding_model, get_vector_dim

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported model registry
# ---------------------------------------------------------------------------

SUPPORTED_EMBEDDING_MODELS: dict[str, dict] = {
    "BAAI/bge-large-zh-v1.5": {"dim": 1024, "max_len": 512, "needs_prefix": False},
    "BAAI/bge-m3": {"dim": 1024, "max_len": 8192, "needs_prefix": False},
    "intfloat/multilingual-e5-large": {"dim": 1024, "max_len": 512, "needs_prefix": True},
}


# ---------------------------------------------------------------------------
# Hashing / tokenization helpers (offline fallback)
# ---------------------------------------------------------------------------

def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tokenize(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", (text or "").lower()).strip()
    if not normalized:
        return []
    words = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", normalized)
    if len(normalized) < 2:
        return words
    bigrams = [normalized[i : i + 2] for i in range(len(normalized) - 1) if normalized[i : i + 2].strip()]
    return words + bigrams


# ---------------------------------------------------------------------------
# SentenceTransformer model wrapper
# ---------------------------------------------------------------------------

class _SentenceTransformerModel:
    """SentenceTransformer embedding wrapper with e5-style prefix support."""

    def __init__(self, model_name: str) -> None:
        import torch
        from sentence_transformers import SentenceTransformer

        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

        if model_name not in SUPPORTED_EMBEDDING_MODELS:
            raise ValueError(
                f"[EMBED] Unsupported embedding model: {model_name!r}. "
                f"Supported: {list(SUPPORTED_EMBEDDING_MODELS)}"
            )

        cfg = SUPPORTED_EMBEDDING_MODELS[model_name]
        self._needs_prefix: bool = cfg["needs_prefix"]
        self._max_len: int = cfg["max_len"]
        self._device = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info("[EMBED] Loading %s (device=%s, max_len=%d)", model_name, self._device, self._max_len)

        self._model = SentenceTransformer(
            model_name,
            device=self._device,
            local_files_only=True,
        )
        self._model.max_seq_length = self._max_len

    # ------------------------------------------------------------------
    # Encoding methods
    # ------------------------------------------------------------------

    def encode(self, texts: list[str], *, normalize_embeddings: bool = True) -> list[list[float]]:
        """Encode document/passage texts (adds 'passage: ' prefix for e5 models)."""
        inputs = [f"passage: {t}" for t in texts] if self._needs_prefix else texts
        vecs = self._model.encode(
            inputs,
            normalize_embeddings=normalize_embeddings,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vecs]

    def encode_query(self, text: str, *, normalize_embeddings: bool = True) -> list[float]:
        """Encode a single query text (adds 'query: ' prefix for e5 models)."""
        inp = f"query: {text}" if self._needs_prefix else text
        vec = self._model.encode(
            inp,
            normalize_embeddings=normalize_embeddings,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vec.tolist()


# ---------------------------------------------------------------------------
# Model loader (cached)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_model_or_none() -> Any | None:
    model_name = os.getenv("EMBEDDING_MODEL") or get_embedding_model()
    logger.info("[EMBED] Loading embedding model: %s", model_name)
    try:
        return _SentenceTransformerModel(model_name)
    except Exception as exc:
        logger.warning("[EMBED] Failed to load %s, falling back to hash embedding: %s", model_name, exc)
        return None


# ---------------------------------------------------------------------------
# Offline-safe deterministic fallback
# ---------------------------------------------------------------------------

def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vec))
    if norm <= 0:
        return vec
    return [value / norm for value in vec]


def _hash_embed_text(text: str, dim: int) -> list[float]:
    """Deterministic hash-based embedding — not semantic, but stable offline."""
    vec = [0.0] * dim
    token_counts = Counter(_tokenize(text))
    if not token_counts:
        return vec
    for token, count in token_counts.items():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        weight = (1.0 + math.log1p(count)) * (1.2 if len(token) > 1 else 1.0)
        vec[bucket] += sign * weight
    return _normalize(vec)


# ---------------------------------------------------------------------------
# In-process embedding cache
# ---------------------------------------------------------------------------

_cache: dict[str, list[float]] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed document/passage texts to normalized vectors.

    Uses 'passage: ' prefix for e5-family models; no prefix for bge.
    Falls back to hash embedding when no model is available.
    """
    dim = get_vector_dim()
    model = _get_model_or_none()

    result: list[list[float]] = []
    to_compute: list[str] = []
    compute_indices: list[int] = []

    for i, text in enumerate(texts):
        key = _hash_text(text)
        cached = _cache.get(key)
        if cached is not None:
            result.append(cached)
            continue
        result.append([])
        to_compute.append(text)
        compute_indices.append(i)

    if not to_compute:
        return result

    if model is None:
        embeddings = [_hash_embed_text(text, dim) for text in to_compute]
    else:
        raw_embeddings = model.encode(to_compute, normalize_embeddings=True)
        embeddings = []
        for vec in raw_embeddings:
            if len(vec) != dim:
                raise ValueError(f"Embedding dim mismatch: expected {dim}, got {len(vec)}")
            embeddings.append(vec)

    for idx, vec in zip(compute_indices, embeddings):
        key = _hash_text(texts[idx])
        _cache[key] = vec
        result[idx] = vec

    return result


def embed_query_text(text: str) -> list[float]:
    """Embed a single query text to a normalized vector.

    Uses 'query: ' prefix for e5-family models; no prefix for bge.
    Falls back to hash embedding when no model is available.
    """
    dim = get_vector_dim()
    model = _get_model_or_none()

    key = "q:" + _hash_text(text)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    if model is None:
        vec = _hash_embed_text(text, dim)
    elif hasattr(model, "encode_query"):
        vec = model.encode_query(text)
        if len(vec) != dim:
            raise ValueError(f"Embedding dim mismatch: expected {dim}, got {len(vec)}")
    else:
        vec = model.encode([text])[0]
        if len(vec) != dim:
            raise ValueError(f"Embedding dim mismatch: expected {dim}, got {len(vec)}")

    _cache[key] = vec
    return vec
