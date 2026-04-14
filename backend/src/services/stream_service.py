"""SSE streaming service for real-time analysis updates."""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator

from ..models import AnalysisRequest, Document, PerspectiveType
from .ollama_service import check_ollama_connection


# Configure logging
logger = logging.getLogger(__name__)


class StreamServiceError(Exception):
    """Exception raised during streaming."""
 
    pass


class OllamaNotRunningError(StreamServiceError):
    """Exception raised when Ollama is not running."""

    def __init__(self):
        super().__init__(
            "Ollama service is not running",
            {
                "hint": "Please start Ollama with: ollama run qwen3:8b",
                "code": "OLLAMA_NOT_RUNNING",
            },
        )


def format_sse_event(event_type: str, data: dict) -> str:
    """Format data as SSE event."""
    json_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {json_data}\n\n"


async def event_generator(
    request: AnalysisRequest,
    document: Document,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for contract analysis."""
    start_time = time.time()

    logger.info(f"[STREAM] Starting analysis for document {document.id}, perspective {request.perspective.value}")

    # Check Ollama connection first
    if not check_ollama_connection():
        logger.error("[STREAM] Ollama not running")
        error_event = json.dumps({
            "error": {
                "code": "OLLAMA_NOT_RUNNING",
                "message": "Ollama service is not running",
                "hint": "Please start Ollama with: ollama run qwen3:8b",
            }
        })
        yield f"data: {error_event}\n\n"
        return

    # Create a queue for progress events (message, progress, optional extra payload)
    progress_queue: asyncio.Queue[tuple[str, int, dict | None]] = asyncio.Queue()

    # Initial status
    yield format_sse_event("status", {
        "message": "开始分析合同...",
        "progress": 0,
    })
    logger.debug("[STREAM] Sent initial status")

    # Document parsing status
    await asyncio.sleep(0.3)
    yield format_sse_event("status", {
        "message": "文档解析完成，准备开始风险扫描...",
        "progress": 10,
    })
    logger.debug("[STREAM] Sent parsing complete status")

    # Progress callback that puts events into the queue
    def progress_callback(message: str, progress: int, extra: dict | None = None):
        """Queue progress events for async processing."""
        logger.debug(f"[STREAM] Progress queued: {message} ({progress}%)")
        try:
            progress_queue.put_nowait((message, progress, extra))
        except asyncio.QueueFull:
            logger.warning("[STREAM] Progress queue full, skipping event")

    # Analyze document in background while processing progress events
    async def run_analysis():
        try:
            # Local import avoids circular import at module initialization time.
            from ..agents.orchestrator_agent import OrchestratorAgent
            agent = OrchestratorAgent()
            result = await agent.run(request=request, document=document, progress_callback=progress_callback)
            return result, agent.last_trace
        except Exception as e:
            logger.error(f"[STREAM] Analysis error: {e}")
            return None

    # Run analysis and process progress events concurrently
    try:
        logger.info("[STREAM] Starting document analysis...")
        analysis_task = asyncio.create_task(run_analysis())

        # Process progress events while analysis runs
        # Drain the queue while waiting for analysis to complete
        while True:
            try:
                # Wait for progress event with short timeout
                message, progress, extra = await asyncio.wait_for(
                    progress_queue.get(),
                    timeout=2.0  # Short timeout to check status frequently
                )
                yield format_sse_event("status", {
                    "message": message,
                    "progress": progress,
                })
                if extra and extra.get("type") == "agent_trace":
                    yield format_sse_event("agent_trace", {"step": extra.get("step")})
                logger.debug(f"[STREAM] Sent progress: {message} ({progress}%)")
            except asyncio.TimeoutError:
                # Check if analysis is done
                if analysis_task.done():
                    break
                # Continue waiting

        # Get the analysis result
        analysis_output = await analysis_task

        if analysis_output is None:
            # Error already logged
            yield format_sse_event("error", {
                "code": "ANALYSIS_FAILED",
                "message": "Analysis failed, check server logs",
            })
            return

        result, trace = analysis_output

        logger.info(f"[STREAM] Analysis complete: {len(result.risks)} risks found")

        # Stream each risk card
        for risk in result.risks:
            risk_data = {
                "id": risk.id,
                "clause_title": risk.clause_title,
                "risk_category": risk.risk_category,
                "original_text": risk.original_text,
                "risk_description": risk.risk_description,
                "suggested_revision": risk.suggested_revision,
                "severity": risk.severity,
            }
            yield format_sse_event("risk", risk_data)
            logger.debug(f"[STREAM] Sent risk {risk.id}: {risk.clause_title}")
            await asyncio.sleep(0.2)

        # Final status
        duration_ms = int((time.time() - start_time) * 1000)
        yield format_sse_event("done", {
            "summary": result.summary,
            "total_risks": len(result.risks),
            "duration_ms": duration_ms,
            "risks": [risk.model_dump(mode='json') for risk in result.risks],
            "trace_steps": trace.to_list() if trace else [],
            "decision_records": trace.decision_records if trace else [],
            "evidence_summary": {
                "grounded_count": sum(1 for risk in result.risks if risk.citations),
                "total_risks": len(result.risks),
                "grounding_ratio": round(
                    (sum(1 for risk in result.risks if risk.citations) / len(result.risks)) if result.risks else 1.0,
                    4,
                ),
            },
        })
        logger.info(f"[STREAM] Analysis complete in {duration_ms}ms")

    except asyncio.CancelledError:
        logger.info("[STREAM] Stream cancelled")
        raise
    except Exception as e:
        logger.error(f"[STREAM] Unexpected error: {e}")
        error_event = json.dumps({
            "error": {
                "code": "STREAM_ERROR",
                "message": str(e),
            }
        })
        yield f"data: {error_event}\n\n"
