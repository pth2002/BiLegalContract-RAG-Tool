"""Analysis models for the contract review tool."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .enums import PerspectiveType
from .risk import RiskCard


class AnalysisRequest(BaseModel):
    """Request to start contract analysis."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "550e8400-e29b-41d4-a716-446655440000",
                "perspective": "party_a",
                "options": {"focus_areas": ["违约责任", "付款条款"]},
            }
        }
    )

    document_id: UUID = Field(..., description="Document to analyze")
    perspective: PerspectiveType = Field(..., description="Analysis perspective")
    options: Optional[dict] = Field(default=None, description="Additional analysis options")


class AnalysisResult(BaseModel):
    """Complete result of contract analysis."""

    model_config = ConfigDict()

    document_id: UUID = Field(..., description="Reference document")
    perspective: PerspectiveType = Field(..., description="Analysis perspective used")
    risks: list[RiskCard] = Field(..., description="All identified risks")
    summary: str = Field(..., description="Overall assessment summary")
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Completion timestamp")
    duration_ms: int = Field(..., ge=0, description="Analysis duration")


class PerspectiveInfo(BaseModel):
    """Information about an analysis perspective."""

    model_config = ConfigDict()

    id: PerspectiveType = Field(..., description="Perspective identifier")
    name: str = Field(..., description="Display name")
    description: str = Field(..., description="Perspective description")
    focus_areas: list[str] = Field(..., description="Key areas to scan")


class PerspectivesResponse(BaseModel):
    """Response containing all available perspectives."""

    model_config = ConfigDict()

    perspectives: list[PerspectiveInfo]
