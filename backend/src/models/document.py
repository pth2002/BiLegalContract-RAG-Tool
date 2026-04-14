"""Document models for the contract review tool."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4 

from pydantic import BaseModel, ConfigDict, Field

from .analysis import PerspectiveType
from .enums import FileType
from .risk import RiskCard


class DocumentBlock(BaseModel):
    """Structure-aware content block extracted from a document."""

    model_config = ConfigDict()

    block_id: str
    page_number: int = Field(..., ge=1)
    block_type: str = Field(default="text")
    text: str = Field(default="")
    char_count: int = Field(default=0, ge=0)
    source: str = Field(default="parser")
    bbox: tuple[float, float, float, float] | None = None


class DocumentPageSummary(BaseModel):
    """Page-level parsing summary used for diagnostics and adaptive policies."""

    model_config = ConfigDict()

    page_number: int = Field(..., ge=1)
    char_count: int = Field(default=0, ge=0)
    block_count: int = Field(default=0, ge=0)
    is_mostly_empty: bool = False
    suspected_toc: bool = False
    suspected_header_footer_noise: bool = False


class DocumentProfile(BaseModel):
    """Lightweight document profile used for future adaptive retrieval policies."""

    model_config = ConfigDict()

    language: str = Field(default="unknown")
    length_class: str = Field(default="short")
    layout_complexity: str = Field(default="low")


class DocumentParseSummary(BaseModel):
    """High-level parsing diagnostics inspired by structure-aware parsers like DeepDoc."""

    model_config = ConfigDict()

    source_type: str = Field(default="text")
    char_count: int = Field(default=0, ge=0)
    parse_quality_score: float = Field(default=1.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)


class ParsedDocumentResult(BaseModel):
    """Structured parser output before persistence."""

    model_config = ConfigDict()

    text_content: str
    count: int
    file_type: FileType
    page_summaries: list[DocumentPageSummary] = Field(default_factory=list)
    content_blocks: list[DocumentBlock] = Field(default_factory=list)
    parse_summary: DocumentParseSummary | None = None
    document_profile: DocumentProfile | None = None


class DocumentAnalysis(BaseModel):
    """Analysis results for a document."""

    model_config = ConfigDict()

    perspective: PerspectiveType
    risks: list[RiskCard]
    summary: str
    analyzed_at: datetime
    duration_ms: int
    trace_steps: list[dict] = Field(default_factory=list)
    decision_records: list[dict] = Field(default_factory=list)
    evidence_summary: dict = Field(default_factory=dict)


class Document(BaseModel):
    """Represents an uploaded contract document for analysis."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "filename": "contract_2024.pdf",
                "file_type": "pdf",
                "file_size": 1048576,
                "page_count": 12,
                "text_content": "Contract text...",
                "page_summaries": [],
                "content_blocks": [],
                "parse_summary": {
                    "source_type": "pdf_text",
                    "char_count": 10240,
                    "parse_quality_score": 0.92,
                    "warnings": [],
                    "flags": [],
                },
                "document_profile": {
                    "language": "zh",
                    "length_class": "medium",
                    "layout_complexity": "medium",
                },
                "uploaded_at": "2026-02-10T10:30:00Z",
                "session_id": "sess_abc123",
                "analyses": {},
            }
        }
    )

    id: UUID = Field(default_factory=uuid4, description="Unique document identifier")
    filename: str = Field(..., description="Original filename with extension")
    file_type: FileType = Field(..., description="Document file type")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    page_count: int = Field(..., ge=1, description="Number of pages (PDF) or logical blocks (DOCX)")
    text_content: str = Field(..., description="Extracted plain text content")
    page_summaries: list[DocumentPageSummary] = Field(default_factory=list, description="Page-level parse summaries")
    content_blocks: list[DocumentBlock] = Field(default_factory=list, description="Structure-aware content blocks")
    parse_summary: DocumentParseSummary | None = Field(default=None, description="Parser diagnostics summary")
    document_profile: DocumentProfile | None = Field(default=None, description="Lightweight document profile")
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Upload timestamp")
    session_id: str = Field(..., description="Browser session identifier")
    analyses: dict[str, DocumentAnalysis] = Field(default_factory=dict, description="Analysis results by perspective")


class DocumentUploadResponse(BaseModel):
    """Response after document upload."""

    model_config = ConfigDict()

    document: Document
    message: str = "Document uploaded successfully"


class DocumentMetadata(BaseModel):
    """Document metadata without full text content."""

    model_config = ConfigDict()

    id: UUID
    filename: str
    file_type: FileType
    file_size: int
    page_count: int
    uploaded_at: datetime
    session_id: str
