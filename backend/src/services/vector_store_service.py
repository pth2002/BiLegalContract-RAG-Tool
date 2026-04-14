"""Vector store service with pgvector-first and local-file fallback."""

from __future__ import annotations

import json
import logging
import math
import os
import re
from pathlib import Path
from typing import Any, Iterable, Optional
from uuid import UUID 

from ..config import get_vector_dim
from ..models import ChunkRecord, RetrievedChunk

logger = logging.getLogger(__name__)

_BACKEND: str | None = None
_LOCAL_STORE_PATH = Path(__file__).resolve().parents[2] / "data" / "vector_store.json"

# Schema for all pgvector tables — sanitised to identifier-safe characters only.
_PG_SCHEMA: str = re.sub(r"[^\w]", "", os.getenv("PG_SCHEMA", "public")) or "public"


def _to_pgvector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


def _ensure_local_store_path() -> Path:
    _LOCAL_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return _LOCAL_STORE_PATH


def _load_local_rows() -> list[dict[str, Any]]:
    path = _ensure_local_store_path()
    if not path.exists():
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows = raw.get("chunks", [])
        return rows if isinstance(rows, list) else []
    except Exception as exc:
        logger.exception("[VECTOR] Failed to load local store %s: %s", path, exc)
        return []


def _save_local_rows(rows: list[dict[str, Any]]) -> None:
    path = _ensure_local_store_path()
    compact_rows = [
        {**row, "embedding": [round(x, 6) for x in row["embedding"]]}
        if "embedding" in row else row
        for row in rows
    ]
    payload = {"chunks": compact_rows}
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(path)


def _local_row_from_chunk(chunk: ChunkRecord) -> dict[str, Any]:
    return {
        "document_id": str(chunk.document_id),
        "session_id": chunk.session_id,
        "chunk_id": chunk.chunk_id,
        "content": chunk.content,
        "embedding": chunk.embedding,
        "metadata": chunk.metadata,
    }


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    if len(vec1) != len(vec2):
        return 0.0

    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


async def _init_pgvector() -> None:
    from .db_service import get_db_pool

    pool = await get_db_pool()
    dim = get_vector_dim()
    schema = _PG_SCHEMA

    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema};")
        await conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.rag_chunks (
              document_id UUID NOT NULL,
              session_id TEXT NOT NULL,
              chunk_id TEXT NOT NULL,
              content TEXT NOT NULL,
              embedding vector({dim}) NOT NULL,
              metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              PRIMARY KEY (document_id, chunk_id)
            );
            """
        )
        await conn.execute(
            f"CREATE INDEX IF NOT EXISTS rag_chunks_session_doc_idx "
            f"ON {schema}.rag_chunks (session_id, document_id);"
        )
        await conn.execute(
            f"CREATE INDEX IF NOT EXISTS rag_chunks_embedding_ivfflat_idx "
            f"ON {schema}.rag_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
        )


async def init_vector_store() -> None:
    """Prefer pgvector, but keep the app usable with a local JSON vector store."""
    global _BACKEND

    if _BACKEND == "pgvector":
        return
    if _BACKEND == "local":
        _ensure_local_store_path()
        return

    try:
        await _init_pgvector()
        _BACKEND = "pgvector"
        logger.info("[VECTOR] Vector store initialized with pgvector (schema=%s)", _PG_SCHEMA)
    except Exception as exc:
        _BACKEND = "local"
        _ensure_local_store_path()
        logger.warning("[VECTOR] pgvector unavailable, falling back to local store: %s", exc)


async def upsert_chunks(chunks: Iterable[ChunkRecord]) -> int:
    rows = list(chunks)
    if not rows:
        return 0

    dim = get_vector_dim()
    for row in rows:
        if len(row.embedding) != dim:
            raise ValueError(f"Embedding dim mismatch: expected {dim}, got {len(row.embedding)}")

    await init_vector_store()

    if _BACKEND == "local":
        existing_rows = _load_local_rows()
        index = {
            (item["document_id"], item["chunk_id"]): item
            for item in existing_rows
        }
        for row in rows:
            index[(str(row.document_id), row.chunk_id)] = _local_row_from_chunk(row)
        _save_local_rows(list(index.values()))
        return len(rows)

    from .db_service import get_db_pool

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        stmt = f"""
        INSERT INTO {_PG_SCHEMA}.rag_chunks (document_id, session_id, chunk_id, content, embedding, metadata)
        VALUES ($1, $2, $3, $4, $5::vector, $6::jsonb)
        ON CONFLICT (document_id, chunk_id) DO UPDATE SET
          session_id = EXCLUDED.session_id,
          content = EXCLUDED.content,
          embedding = EXCLUDED.embedding,
          metadata = EXCLUDED.metadata;
        """

        for row in rows:
            await conn.execute(
                stmt,
                row.document_id,
                row.session_id,
                row.chunk_id,
                row.content,
                _to_pgvector_literal(row.embedding),
                json.dumps(row.metadata, ensure_ascii=False),
            )

    return len(rows)


async def has_indexed(document_id: UUID) -> bool:
    await init_vector_store()

    if _BACKEND == "local":
        return any(item["document_id"] == str(document_id) for item in _load_local_rows())

    from .db_service import get_db_pool

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT 1 FROM {_PG_SCHEMA}.rag_chunks WHERE document_id = $1 LIMIT 1;",
            document_id,
        )
        return row is not None


async def delete_chunks_for_document(document_id: UUID) -> int:
    await init_vector_store()

    if _BACKEND == "local":
        rows = _load_local_rows()
        kept = [item for item in rows if item["document_id"] != str(document_id)]
        deleted = len(rows) - len(kept)
        if deleted:
            _save_local_rows(kept)
        return deleted

    from .db_service import get_db_pool

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            f"DELETE FROM {_PG_SCHEMA}.rag_chunks WHERE document_id = $1;",
            document_id,
        )

    try:
        return int(result.split()[-1])
    except (ValueError, IndexError):
        return 0


async def search(
    *,
    document_id: UUID,
    query_embedding: list[float],
    top_k: int,
    session_id: Optional[str] = None,
) -> list[RetrievedChunk]:
    await init_vector_store()

    dim = get_vector_dim()
    if len(query_embedding) != dim:
        raise ValueError(f"Embedding dim mismatch: expected {dim}, got {len(query_embedding)}")

    if _BACKEND == "local":
        results: list[RetrievedChunk] = []
        for item in _load_local_rows():
            if item["document_id"] != str(document_id):
                continue
            if session_id is not None and item.get("session_id") != session_id:
                continue

            score = _cosine_similarity(query_embedding, item.get("embedding", []))
            results.append(
                RetrievedChunk(
                    chunk_id=item["chunk_id"],
                    content=item["content"],
                    score=score,
                    metadata=dict(item.get("metadata") or {}),
                )
            )

        results.sort(key=lambda chunk: chunk.score, reverse=True)
        return results[:top_k]

    from .db_service import get_db_pool

    pool = await get_db_pool()
    vec = _to_pgvector_literal(query_embedding)

    where = "document_id = $1"
    params: list[Any] = [document_id]
    if session_id is not None:
        where += " AND session_id = $2"
        params.append(session_id)
        vec_param_idx = 3
        topk_param_idx = 4
    else:
        vec_param_idx = 2
        topk_param_idx = 3

    sql = (
        f"SELECT chunk_id, content, metadata, "
        f"(1 - (embedding <=> ${vec_param_idx}::vector)) AS score "
        f"FROM {_PG_SCHEMA}.rag_chunks "
        f"WHERE {where} "
        f"ORDER BY embedding <=> ${vec_param_idx}::vector "
        f"LIMIT ${topk_param_idx};"
    )

    probes = int(os.getenv("PGVECTOR_PROBES", "50"))
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(f"SET LOCAL ivfflat.probes = {probes};")
            rows = await conn.fetch(sql, *params, vec, top_k)

    return [
        RetrievedChunk(
            chunk_id=row["chunk_id"],
            content=row["content"],
            score=float(row["score"]),
            metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {}),
        )
        for row in rows
    ]
