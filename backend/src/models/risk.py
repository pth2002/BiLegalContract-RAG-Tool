"""Risk card models for the contract review tool."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID

from .enums import Severity

 
class EvidenceRef(BaseModel):
    """Grounding evidence for one risk."""

    model_config = ConfigDict()

    chunk_id: str
    quote: str = ""
    score: float = 0.0


class RiskCard(BaseModel):
    """Represents a single risk identified by AI analysis."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "risk_001",
                "clause_title": "违约责任条款",
                "risk_category": "经济利益",
                "original_text": "甲方逾期付款的，按日万分之五支付违约金",
                "risk_description": "违约金比例较高，建议协商降低",
                "suggested_revision": "建议将违约金比例调整为万分之一",
                "severity": "high",
                "document_id": "550e8400-e29b-41d4-a716-446655440000",
                "citations": [{"chunk_id": "chunk_0003", "quote": "甲方逾期付款", "score": 0.88}],
                "grounding_score": 0.88,
            }
        }
    )

    id: str = Field(pattern=r"risk_\d{3}", description="Unique risk identifier")
    clause_title: str = Field(..., description="Title of the contract clause")
    risk_category: str = Field(..., description="Category of the risk (flexible, LLM-defined)")
    original_text: str = Field(..., description="Original clause text excerpt")
    risk_description: str = Field(..., description="AI analysis of the risk")
    suggested_revision: str = Field(..., description="Proposed text modification")
    severity: Severity = Field(..., description="Risk severity level")
    document_id: UUID = Field(..., description="Reference to Document")
    citations: list[EvidenceRef] = Field(default_factory=list, description="Grounding evidence chunks")
    grounding_score: float | None = Field(default=None, description="Evidence grounding score")


class RiskRefinementRequest(BaseModel):
    """Request to refine a risk suggestion."""

    model_config = ConfigDict()

    instruction: str = Field(..., min_length=1, max_length=500, description="Natural language instruction")
    original_risk_id: str = Field(..., description="Reference to original risk card")


class RiskRefinementResponse(BaseModel):
    """Response after refining a risk suggestion."""

    model_config = ConfigDict()

    original: dict = Field(..., description="Original risk suggestion")
    refined: dict = Field(..., description="Refined risk suggestion")
    changes: dict = Field(..., description="Changes made")


class AnalysisEvent(BaseModel):
    """SSE event for streaming analysis."""

    model_config = ConfigDict()

    event_type: str = Field(..., description="Event type: status, risk, progress, done")
    data: dict = Field(..., description="Event payload")


class StatusEvent(BaseModel):
    """Status update event during analysis."""

    model_config = ConfigDict()

    message: str = Field(..., description="Status message")
    progress: int = Field(..., ge=0, le=100, description="Progress percentage")


class DoneEvent(BaseModel):
    """Analysis completion event."""

    model_config = ConfigDict()

    summary: str = Field(..., description="Overall analysis summary")
    total_risks: int = Field(..., ge=0, description="Total risks found")
    duration_ms: int = Field(..., ge=0, description="Analysis duration in milliseconds")
