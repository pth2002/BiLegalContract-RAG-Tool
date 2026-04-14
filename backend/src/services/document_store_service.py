"""Lightweight persistent document store backed by a JSON file."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import UUID
 
from ..config import get_document_store_path
from ..models import Document

logger = logging.getLogger(__name__)


class DocumentStore:
    """Persist uploaded documents and analyses across process restarts."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_document_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._documents: dict[UUID, Document] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if not self.path.exists():
            self._documents = {}
            self._loaded = True
            return

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            docs: dict[UUID, Document] = {}
            for item in raw.get("documents", []):
                document = Document.model_validate(item)
                docs[document.id] = document
            self._documents = docs
            logger.info("[DOC_STORE] Loaded %s documents from %s", len(docs), self.path)
        except Exception as exc:
            logger.exception("[DOC_STORE] Failed to load %s: %s", self.path, exc)
            self._documents = {}
        finally:
            self._loaded = True

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"documents": [doc.model_dump(mode="json") for doc in self._documents.values()]}
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(self.path)

    def all(self) -> list[Document]:
        self._ensure_loaded()
        return list(self._documents.values())

    def get(self, document_id: UUID) -> Document | None:
        self._ensure_loaded()
        return self._documents.get(document_id)

    def upsert(self, document: Document) -> Document:
        self._ensure_loaded()
        self._documents[document.id] = document
        self._save()
        return document

    def delete(self, document_id: UUID) -> bool:
        self._ensure_loaded()
        removed = self._documents.pop(document_id, None)
        if removed is None:
            return False
        self._save()
        return True


_STORE: DocumentStore | None = None


def get_document_store() -> DocumentStore:
    global _STORE
    if _STORE is None:
        _STORE = DocumentStore()
    return _STORE


def reset_document_store_for_tests(path: Path | None = None) -> DocumentStore:
    """Reset singleton store; intended for tests."""
    global _STORE
    _STORE = DocumentStore(path=path)
    return _STORE
