"""Indexing service: chunk -> embed -> upsert to vector store."""

from __future__ import annotations

import logging
from uuid import UUID

from ..models import ChunkRecord, Document
from .chunking_service import chunk_document
from .embedding_service import embed_texts
from .vector_store_service import init_vector_store, upsert_chunks

logger = logging.getLogger(__name__)


async def index_document(document: Document) -> int:
    """Index a document into vector store (idempotent via upsert)."""
    await init_vector_store()

    chunks = chunk_document(document)
    if not chunks:
        return 0

    embeddings = embed_texts([c.content for c in chunks])
    records = [
        ChunkRecord(
            document_id=document.id,
            session_id=document.session_id,
            chunk_id=c.chunk_id,
            content=c.content,
            embedding=embeddings[i],
            metadata={"start": c.start, "end": c.end},
        )
        for i, c in enumerate(chunks)
    ]

    inserted = await upsert_chunks(records)
    logger.info(f"[INDEX] Indexed document {document.id}: {inserted} chunks")
    return inserted

