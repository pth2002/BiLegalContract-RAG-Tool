"""长期向量记忆：pgvector + PostgreSQL 实现。内存 fallback 保留用于无数据库时。"""

from __future__ import annotations
 
import json
import logging
import math
import os
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

# ── pgvector 依赖（可选；缺失时退化到内存模式）──
try:
    import asyncpg
    from pgvector.asyncpg import register_vector
    _PGVECTOR_AVAILABLE = True
except ImportError:
    _PGVECTOR_AVAILABLE = False
    logger.warning("[VectorMemory] pgvector/asyncpg not installed, using in-memory fallback")

# ── 统一 embedding 服务（可选；缺失时回退到字符串匹配）──
try:
    from ..services.embedding_service import embed_texts as _embed_texts
    from ..config import get_vector_dim as _get_vector_dim
    _EMBED_AVAILABLE = True
except Exception:
    _EMBED_AVAILABLE = False
    logger.warning("[VectorMemory] embedding_service unavailable, using string-match fallback")


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    if len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


def _get_embedding(text: str) -> list[float] | None:
    """调用 embed_texts 获取向量；失败时返回 None。"""
    if not _EMBED_AVAILABLE:
        return None
    try:
        vecs = _embed_texts([text])
        return vecs[0] if vecs else None
    except Exception as e:
        logger.warning("[VectorMemory] embed failed: %s", e)
        return None


@dataclass
class VectorMemoryEntry:
    text: str
    kind: str
    meta: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = field(default=None, repr=False)


class _InMemoryStore:
    def __init__(self) -> None:
        self._entries: list[VectorMemoryEntry] = []

    def _add(self, text: str, kind: str, **meta: Any) -> None:
        emb = _get_embedding(text)
        self._entries.append(VectorMemoryEntry(text=text[:4000], kind=kind, meta=meta, embedding=emb))

    def _search(self, query: str, top_k: int, kind_filter: str | None = None) -> list[dict[str, Any]]:
        q = (query or "").strip()
        candidates = [e for e in self._entries[-200:] if not kind_filter or e.kind == kind_filter]

        # 尝试真实向量余弦相似度搜索
        query_emb = _get_embedding(q) if q else None
        if query_emb is not None:
            scored: list[tuple[float, VectorMemoryEntry]] = []
            for e in candidates:
                score = _cosine_similarity(query_emb, e.embedding) if e.embedding is not None else 0.0
                scored.append((score, e))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [{"kind": e.kind, "text": e.text[:500], "meta": e.meta} for _, e in scored[:top_k]]

        # 回退：字符串匹配
        logger.warning("[VectorMemory] falling back to string-match search")
        hits: list[dict[str, Any]] = []
        for e in reversed(candidates):
            if q[:80] in e.text or any(tok in e.text for tok in q.split() if len(tok) > 3):
                hits.append({"kind": e.kind, "text": e.text[:500], "meta": e.meta})
                if len(hits) >= top_k:
                    break
        return hits

    def add_contract_context(self, document_id: UUID, snippet: str, **meta: Any) -> None:
        self._add(snippet, "contract_snippet", document_id=str(document_id), **meta)

    def add_risk_pattern(self, description: str, **meta: Any) -> None:
        self._add(description, "risk_pattern", **meta)

    def set_user_preferences(self, user_id: Optional[str], prefs: dict[str, Any]) -> None:
        if prefs:
            self._add(str(prefs), "user_pref", user_id=user_id or "anonymous")

    def add_experience(self, *, query: str, good_strategy: str = "", bad_strategy: str = "", **meta: Any) -> None:
        blob = json.dumps({"query": query[:500], "good_strategy": good_strategy[:500], "bad_strategy": bad_strategy[:500]}, ensure_ascii=False)
        self._add(blob, "experience", query=query[:200], **meta)

    def add_strategy(self, *, context: str, strategy: str, source: str = "critic", confidence: float = 0.5) -> None:
        if not strategy.strip():
            return
        blob = json.dumps({"context": context[:400], "strategy": strategy[:500], "source": source, "confidence": round(confidence, 3)}, ensure_ascii=False)
        self._add(blob, "strategy", context=context[:200], source=source)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        return self._search(query, top_k)

    def search_strategies(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        return self._search(query, top_k, kind_filter="strategy")


class _PgVectorStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: Any = None
        self._dim: int = _get_vector_dim() if _EMBED_AVAILABLE else 1024

    @property
    def TABLE_DDL(self) -> str:
        return """
    CREATE TABLE IF NOT EXISTS vector_memory (
        id          BIGSERIAL PRIMARY KEY,
        kind        TEXT        NOT NULL,
        text        TEXT        NOT NULL,
        meta        JSONB       NOT NULL DEFAULT '{{}}',
        embedding   vector({dim}),
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS vm_kind_idx ON vector_memory (kind);
    CREATE INDEX IF NOT EXISTS vm_emb_idx  ON vector_memory
        USING ivfflat (embedding vector_cosine_ops) WITH (lists = 32);
    """.format(dim=self._dim)

    async def _get_pool(self):
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=4)
            async with self._pool.acquire() as conn:
                await register_vector(conn)
                await conn.execute(self.TABLE_DDL)
        return self._pool

    async def _add(self, text: str, kind: str, **meta: Any) -> None:
        emb = _get_embedding(text) or [0.0] * self._dim
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await register_vector(conn)
            await conn.execute(
                "INSERT INTO vector_memory (kind, text, meta, embedding) VALUES ($1,$2,$3,$4)",
                kind, text[:4000], json.dumps(meta), emb,
            )

    async def _search(self, query: str, top_k: int, kind_filter: str | None = None) -> list[dict[str, Any]]:
        emb = _get_embedding(query) or [0.0] * self._dim
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await register_vector(conn)
            if kind_filter:
                rows = await conn.fetch(
                    "SELECT kind, text, meta FROM vector_memory WHERE kind=$1 ORDER BY embedding <=> $2 LIMIT $3",
                    kind_filter, emb, top_k,
                )
            else:
                rows = await conn.fetch(
                    "SELECT kind, text, meta FROM vector_memory ORDER BY embedding <=> $1 LIMIT $2",
                    emb, top_k,
                )
        return [{"kind": r["kind"], "text": r["text"][:500], "meta": json.loads(r["meta"])} for r in rows]

    def _run_async(self, coro):
        import asyncio, concurrent.futures
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    return ex.submit(asyncio.run, coro).result(timeout=5)
            return loop.run_until_complete(coro)
        except Exception as e:
            logger.warning("[VectorMemory] async run failed: %s", e)
            return None

    def add_contract_context(self, document_id: UUID, snippet: str, **meta: Any) -> None:
        import asyncio
        asyncio.get_event_loop().create_task(self._add(snippet, "contract_snippet", document_id=str(document_id), **meta))

    def add_risk_pattern(self, description: str, **meta: Any) -> None:
        import asyncio
        asyncio.get_event_loop().create_task(self._add(description, "risk_pattern", **meta))

    def set_user_preferences(self, user_id: Optional[str], prefs: dict[str, Any]) -> None:
        if prefs:
            import asyncio
            asyncio.get_event_loop().create_task(self._add(str(prefs), "user_pref", user_id=user_id or "anonymous"))

    def add_experience(self, *, query: str, good_strategy: str = "", bad_strategy: str = "", **meta: Any) -> None:
        blob = json.dumps({"query": query[:500], "good_strategy": good_strategy[:500], "bad_strategy": bad_strategy[:500]}, ensure_ascii=False)
        import asyncio
        asyncio.get_event_loop().create_task(self._add(blob, "experience", query=query[:200], **meta))

    def add_strategy(self, *, context: str, strategy: str, source: str = "critic", confidence: float = 0.5) -> None:
        if not strategy.strip():
            return
        blob = json.dumps({"context": context[:400], "strategy": strategy[:500], "source": source, "confidence": round(confidence, 3)}, ensure_ascii=False)
        import asyncio
        asyncio.get_event_loop().create_task(self._add(blob, "strategy", context=context[:200], source=source))

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        return self._run_async(self._search(query, top_k)) or []

    def search_strategies(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        return self._run_async(self._search(query, top_k, kind_filter="strategy")) or []


def create_vector_memory_store() -> "_InMemoryStore | _PgVectorStore":
    dsn = os.environ.get("VECTOR_MEMORY_DSN", "")
    if dsn and _PGVECTOR_AVAILABLE:
        logger.info("[VectorMemory] using pgvector store: %s", dsn.split("@")[-1])
        return _PgVectorStore(dsn)
    if dsn and not _PGVECTOR_AVAILABLE:
        logger.warning("[VectorMemory] VECTOR_MEMORY_DSN set but pgvector not installed; falling back to in-memory")
    else:
        logger.info("[VectorMemory] no VECTOR_MEMORY_DSN set; using in-memory store")
    return _InMemoryStore()


VectorMemoryStore = _InMemoryStore  # backward compat
