"""Knowledge / RAG related models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

 
class ChunkRecord(BaseModel):
    """A stored chunk (for indexing)."""

    model_config = ConfigDict()

    document_id: UUID
    session_id: str
    chunk_id: str
    content: str
    embedding: list[float]
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RetrievedChunk(BaseModel):
    """A chunk returned by the retriever."""

    model_config = ConfigDict()

    chunk_id: str
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    retrieval_methods: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, float] = Field(default_factory=dict)

