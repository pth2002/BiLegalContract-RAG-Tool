"""API routes for the contract review tool.""" 

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from ..models import (
    AnalysisRequest,
    Document,
    DocumentAnalysis,
    DocumentMetadata,
    DocumentUploadResponse,
    ExportFormat,
    PerspectiveInfo,
    PerspectiveType,
    PerspectivesResponse,
    RiskRefinementRequest,
    RiskRefinementResponse,
)
from ..services import (
    DocumentParseError,
    FileValidationError,
    OllamaError,
    check_ollama_connection,
    event_generator,
    generate_docx_report,
    generate_markdown_report,
    generate_suggestion_refinement,
    parse_document,
    parse_document_result,
)
from ..services.document_store_service import get_document_store

logger = logging.getLogger(__name__)

router = APIRouter()

PERSPECTIVES = {
    PerspectiveType.PARTY_A: PerspectiveInfo(
        id=PerspectiveType.PARTY_A,
        name="甲方视角",
        description="从甲方利益出发审查合同",
        focus_areas=["对方违约风险", "赔偿条款", "权益保护", "履约担保"],
    ),
    PerspectiveType.PARTY_B: PerspectiveInfo(
        id=PerspectiveType.PARTY_B,
        name="乙方视角",
        description="从乙方利益出发审查合同",
        focus_areas=["责任边界", "免责条款", "付款条件", "终止条款"],
    ),
}


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = Query(...),
):
    """Upload a contract document for analysis."""
    try:
        file_content = await file.read()
        parsed = parse_document_result(file_content, file.filename)

        document = Document(
            id=uuid.uuid4(),
            filename=file.filename,
            file_type=parsed.file_type,
            file_size=len(file_content),
            page_count=parsed.count,
            text_content=parsed.text_content,
            page_summaries=parsed.page_summaries,
            content_blocks=parsed.content_blocks,
            parse_summary=parsed.parse_summary,
            document_profile=parsed.document_profile,
            session_id=session_id,
        )
        get_document_store().upsert(document)

        return DocumentUploadResponse(document=document, message="Document uploaded successfully")
    except FileValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
        ) from exc
    except DocumentParseError as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "PARSE_FAILED", "message": str(exc)}},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "UPLOAD_FAILED", "message": str(exc)}},
        ) from exc


@router.get("/documents/{document_id}")
async def get_document(document_id: UUID):
    """Retrieve document metadata."""
    document = get_document_store().get(document_id)
    if not document:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "DOCUMENT_NOT_FOUND", "message": "Document not found"}},
        )
    return {"document": document}


@router.get("/documents")
async def list_documents(session_id: str | None = Query(default=None)):
    """List persisted documents, optionally filtered by session."""
    documents = get_document_store().all()
    if session_id:
        documents = [document for document in documents if document.session_id == session_id]
    items = [
        DocumentMetadata(
            id=document.id,
            filename=document.filename,
            file_type=document.file_type,
            file_size=document.file_size,
            page_count=document.page_count,
            uploaded_at=document.uploaded_at,
            session_id=document.session_id,
        )
        for document in sorted(documents, key=lambda item: item.uploaded_at, reverse=True)
    ]
    return {"documents": items}


@router.delete("/documents/{document_id}")
async def delete_document(document_id: UUID):
    """Delete document and associated analysis results."""
    if not get_document_store().get(document_id):
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "DOCUMENT_NOT_FOUND", "message": "Document not found"}},
        )

    try:
        from ..services.vector_store_service import delete_chunks_for_document

        removed = await delete_chunks_for_document(document_id)
        if removed:
            logger.info("[API] Deleted %s rag_chunks for document %s", removed, document_id)
    except Exception as exc:
        logger.warning(
            "[API] Failed to delete rag_chunks for document %s (continuing): %s",
            document_id,
            exc,
        )

    get_document_store().delete(document_id)
    return None


@router.get("/perspectives", response_model=PerspectivesResponse)
async def get_perspectives():
    """List available analysis perspectives."""
    return PerspectivesResponse(perspectives=list(PERSPECTIVES.values()))


@router.post("/analyze/stream")
async def analyze_stream(request: AnalysisRequest):
    """Start contract analysis with streaming risk cards via SSE."""
    document = get_document_store().get(request.document_id)
    if not document:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "DOCUMENT_NOT_FOUND", "message": "Document not found"}},
        )

    if not check_ollama_connection():
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "OLLAMA_NOT_RUNNING",
                    "message": "Ollama service is not running",
                    "hint": "Please start Ollama with: ollama run qwen3:8b",
                }
            },
        )

    analysis_result: dict = {}

    async def generate():
        nonlocal analysis_result
        async for event in event_generator(request, document):
            if event.startswith("event: done"):
                try:
                    data_start = event.find("data: ") + 6
                    data_end = event.rfind("\n\n")
                    analysis_result = json.loads(event[data_start:data_end])
                except Exception:
                    analysis_result = {}
            yield event

        if analysis_result:
            perspective_key = request.perspective.value
            stored_document = get_document_store().get(request.document_id)
            if stored_document:
                stored_document.analyses[perspective_key] = DocumentAnalysis(
                    perspective=request.perspective,
                    risks=analysis_result.get("risks", []),
                    summary=analysis_result.get("summary", ""),
                    analyzed_at=datetime.utcnow(),
                    duration_ms=analysis_result.get("duration_ms", 0),
                    trace_steps=analysis_result.get("trace_steps", []),
                    decision_records=analysis_result.get("decision_records", []),
                    evidence_summary=analysis_result.get("evidence_summary", {}),
                )
                get_document_store().upsert(stored_document)

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/risks/{risk_id}/refine", response_model=RiskRefinementResponse)
async def refine_risk(risk_id: str, request: RiskRefinementRequest):
    """Refine a risk suggestion with natural language instructions."""
    found_risk = None

    for document in get_document_store().all():
        for analysis in document.analyses.values():
            for risk in analysis.risks:
                if risk.id == risk_id:
                    found_risk = risk
                    break
            if found_risk:
                break
        if found_risk:
            break

    if not found_risk:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "RISK_NOT_FOUND", "message": "Risk not found"}},
        )

    try:
        refined_text = await generate_suggestion_refinement(
            original_suggestion=found_risk.suggested_revision,
            instruction=request.instruction,
        )
        return RiskRefinementResponse(
            original={"id": found_risk.id, "suggested_revision": found_risk.suggested_revision},
            refined={"id": f"{found_risk.id}_refined", "suggested_revision": refined_text},
            changes={"added": [], "removed": []},
        )
    except OllamaError as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "REFINE_FAILED", "message": str(exc)}},
        ) from exc


@router.post("/export")
async def export_report(
    document_id: UUID = Query(...),
    perspective: PerspectiveType = Query(...),
    format: ExportFormat = Query(...),
    include_risks: bool = Query(True),
    include_summary: bool = Query(True),
):
    """Export analysis report in the specified format."""
    document = get_document_store().get(document_id)
    if not document:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "DOCUMENT_NOT_FOUND", "message": "Document not found"}},
        )

    perspective_key = perspective.value
    if perspective_key not in document.analyses:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "ANALYSIS_NOT_FOUND",
                    "message": f"No analysis found for perspective: {perspective}",
                }
            },
        )

    analysis = document.analyses[perspective_key]
    from urllib.parse import quote

    if format == ExportFormat.MARKDOWN:
        markdown_content = generate_markdown_report(
            document=document,
            analysis=analysis,
            include_risks=include_risks,
            include_summary=include_summary,
        )
        filename = f"合同审查报告_{document.filename}_{perspective.value}_{datetime.now().strftime('%Y%m%d')}.md"
        encoded_filename = quote(filename, safe="")
        return JSONResponse(
            content=markdown_content,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                "Content-Type": "text/markdown; charset=utf-8",
            },
        )

    if format == ExportFormat.DOCX:
        docx_buffer = generate_docx_report(
            document=document,
            analysis=analysis,
            include_risks=include_risks,
            include_summary=include_summary,
        )
        filename = f"合同审查报告_{document.filename}_{perspective.value}_{datetime.now().strftime('%Y%m%d')}.docx"
        encoded_filename = quote(filename, safe="")
        return StreamingResponse(
            docx_buffer,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
        )

    raise HTTPException(
        status_code=400,
        detail={"error": {"code": "UNSUPPORTED_FORMAT", "message": f"Format {format} is not supported"}},
    )


@router.get("/export/template")
async def get_export_template():
    """Download Markdown template for report customization."""
    template = """# 合同智能审查报告

**生成时间**: {{TIMESTAMP}}
**审查视角**: {{PERSPECTIVE}}
**文档**: {{FILENAME}}
**耗时**: {{DURATION}}

---

## 概览

本次审查共发现 **{{RISK_COUNT}}** 个风险点，其中：
- 高风险：{{HIGH_COUNT}} 个
- 中风险：{{MEDIUM_COUNT}} 个
- 低风险：{{LOW_COUNT}} 个

---

## 风险详情

### {{SEVERITY}}

#### {{CLAUSE_TITLE}}

**原文**: > {{ORIGINAL_TEXT}}

**风险描述**: {{RISK_DESCRIPTION}}

**修改建议**: {{SUGGESTED_REVISION}}

---

## 总结

{{SUMMARY}}
"""
    return JSONResponse(
        content=template,
        headers={"Content-Disposition": "attachment; filename=report_template.md"},
    )
