"""Analysis orchestration service."""

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from typing import AsyncGenerator, Optional
from uuid import UUID

from json_repair import repair_json

from ..models import (
    AnalysisRequest,
    AnalysisResult,
    Document,
    PerspectiveType,
    RiskCard,
)
from .ollama_service import stream_analysis
from .prompt_service import get_perspective_prompt
from .prompt_builder_service import build_analysis_user_prompt
from .prompt_builder_service import RetrievedContext
from .indexing_service import index_document
from .retrieval_service import retrieve_contexts_merged
from .vector_store_service import has_indexed, init_vector_store


# Configure logging
logger = logging.getLogger(__name__)


class AnalysisError(Exception):
    """Exception raised during analysis."""

    pass


def generate_risk_id(index: int) -> str:
    """Generate a risk card ID."""
    return f"risk_{index + 1:03d}"


#这里_这个下划线的意思是这是内部函数，不希望被外部调用
def _clean_json_content(content: str) -> str:
    """Clean JSON content by removing markdown wrappers and extra text."""
    cleaned = content.strip()

    # Remove markdown code block wrappers
    cleaned = cleaned.replace("```json", "").replace("```JSON", "").replace("```", "").strip()

    # Remove any text before the first '[' or after the last ']'
    start_idx = cleaned.find("[")
    if start_idx != -1:
        # Find matching closing bracket
        bracket_count = 0
        end_idx = -1
        for i in range(start_idx, len(cleaned)):
            if cleaned[i] == "[":
                bracket_count += 1
            elif cleaned[i] == "]":
                bracket_count -= 1
                if bracket_count == 0:
                    end_idx = i + 1
                    break
        if end_idx > start_idx:
            cleaned = cleaned[start_idx:end_idx]

    return cleaned


def parse_risk_json(content: str) -> list[dict]:
    """Parse risk JSON from LLM response with auto-repair capability.

    Uses json_repair to handle malformed JSON from LLM outputs.

    Args:
        content: Raw LLM response content

    Returns:
        List of risk dictionaries
    """
    risks = []
    logger.debug(f"[ANALYZER] Parsing JSON from content ({len(content)} chars)")

    if not content:
        logger.warning("[ANALYZER] Empty content received")
        return []

    # Clean the content first
    cleaned = _clean_json_content(content)

    # Try standard JSON parsing first (fast path for valid JSON)
    try:
        risks = json.loads(cleaned)
        logger.debug(f"[ANALYZER] Standard JSON parse success: {len(risks)} risks")
        return risks
    except json.JSONDecodeError as e:
        logger.warning(f"[ANALYZER] Standard JSON parse failed: {e}")

    # Use json_repair for auto-repair of malformed JSON
    try:
        repaired = repair_json(cleaned, ensure_ascii=False)
        if isinstance(repaired, str):
            repaired_data = json.loads(repaired)
        elif isinstance(repaired, (list, dict)):
            repaired_data = repaired
        else:
            raise ValueError(f"Unexpected repair result type: {type(repaired)}")

        if isinstance(repaired_data, list):
            risks = repaired_data
        elif isinstance(repaired_data, dict):
            risks = [repaired_data] if "clause_title" in repaired_data else []
        logger.debug(f"[ANALYZER] json_repair success: {len(risks)} risks")
        return risks
    except Exception as e:
        logger.error(f"[ANALYZER] json_repair failed: {e}")

    # Final fallback: regex extraction of individual risk objects
    logger.debug("[ANALYZER] Trying regex extraction fallback...")
    pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(pattern, content, re.DOTALL)
    logger.debug(f"[ANALYZER] Found {len(matches)} potential risk objects")

    for match in matches:
        try:
            risk = json.loads(match)
            if isinstance(risk, dict) and "clause_title" in risk and "severity" in risk:
                risks.append(risk)
        except (json.JSONDecodeError, TypeError):
            continue

    logger.debug(f"[ANALYZER] Total risks extracted: {len(risks)}")
    return risks


def _map_severity(value: str) -> str:
    """Map LLM severity to valid enum values."""
    normalized = value.lower().strip()

    valid_values = {"高", "中", "低"}

    if normalized in valid_values:
        return normalized

    # Fuzzy match
    if normalized in ["高风险", "high", "h"]:
        return "高"
    if normalized in ["中风险", "medium", "m", "中等"]:
        return "中"
    if normalized in ["低风险", "low", "l"]:
        return "低"

    logger.warning(f"[ANALYZER] Unknown severity '{value}', defaulting to '中'")
    return "中"


def create_risk_card(risk_dict: dict, document_id: UUID, index: int) -> RiskCard:
    """Create a RiskCard from dictionary.

    Uses LLM's risk_category directly, only maps severity for compatibility.
    Always generates compliant ID.
    """
    # Always use generated ID to ensure pattern compliance
    risk_id = generate_risk_id(index)

    # Map severity, but use risk_category directly
    severity = _map_severity(risk_dict.get("severity", "中"))

    return RiskCard(
        id=risk_id,
        clause_title=risk_dict.get("clause_title", "未知条款"),
        risk_category=risk_dict.get("risk_category", "其他风险"),
        original_text=risk_dict.get("original_text", ""),
        risk_description=risk_dict.get("risk_description", ""),
        suggested_revision=risk_dict.get("suggested_revision", ""),
        severity=severity,
        document_id=document_id,
    )


async def analyze_document(
    request: AnalysisRequest,
    document: Document,
    progress_callback: Optional[callable] = None,
) -> AnalysisResult:
    """Analyze a document for contract risks.

    Collects all LLM output first, then parses JSON once at the end.
    """
    start_time = time.time()

    perspective = request.perspective
    logger.info(f"[ANALYZER] Starting analysis for document {document.id}, perspective: {perspective.value}")
    logger.debug(f"[ANALYZER] Document: {document.filename}, {len(document.text_content)} chars")

    # Build context-aware prompt with perspective
    # Phase-0: prompt assembly is isolated so RAG can later inject retrieved contexts
    system_prompt_template = get_perspective_prompt(perspective)
    await init_vector_store()

    # Index-on-demand (lazy) to keep upload fast (Plan phase-3 option B).
    if not await has_indexed(document.id):
        if progress_callback:
            progress_callback(message="正在为 RAG 建立索引（切块+向量化）...", progress=15)
        await index_document(document)

    # Retrieve contexts for RAG
    if progress_callback:
        progress_callback(message="正在检索相关条款片段（RAG）...", progress=25)

    retrieved = await retrieve_contexts_merged(
        document_id=document.id,
        session_id=document.session_id,
        perspective=perspective,
        options=request.options,
        document=document,
    )
    retrieved_contexts = [
        RetrievedContext(chunk_id=c.chunk_id, content=c.content, score=c.score) for c in retrieved
    ]

    user_prompt = build_analysis_user_prompt(
        system_prompt_template=system_prompt_template,
        contract_text=document.text_content,
        retrieved_contexts=retrieved_contexts,
    )

    # Collect all content from stream first (do NOT parse incrementally!)
    content_buffer = ""
    chunk_count = 0

    logger.debug("[ANALYZER] Starting Ollama stream...")

    async for chunk in stream_analysis(user_prompt, system_prompt_template):
        content_buffer += chunk
        chunk_count += 1
        logger.debug(f"[ANALYZER] Received chunk {chunk_count}, total chars: {len(content_buffer)}")

    logger.info(f"[ANALYZER] Stream complete: {chunk_count} chunks, {len(content_buffer)} chars total")

    # Report progress - content collected, now parsing
    if progress_callback:
        progress_callback(
            message="正在解析分析结果...",
            progress=85,
        )

    # Parse JSON only once after all content is collected
    risk_dicts = parse_risk_json(content_buffer)

    # Create risk cards from parsed data
    risks = []
    for i, risk_dict in enumerate(risk_dicts):
        risk_card = create_risk_card(risk_dict, document.id, i)
        risks.append(risk_card)
        logger.debug(f"[ANALYZER] Created risk card {risk_card.id}: {risk_card.clause_title}")

    # Generate summary
    high_count = sum(1 for r in risks if r.severity.value == "高")
    medium_count = sum(1 for r in risks if r.severity.value == "中")
    low_count = sum(1 for r in risks if r.severity.value == "低")

    summary = (
        f"分析完成。共发现 {len(risks)} 个风险点，"
        f"其中高风险 {high_count} 个，中风险 {medium_count} 个，低风险 {low_count} 个。"
    )

    duration_ms = int((time.time() - start_time) * 1000)

    logger.info(f"[ANALYZER] Analysis complete: {len(risks)} risks in {duration_ms}ms")

    return AnalysisResult(
        document_id=document.id,
        perspective=perspective,
        risks=risks,
        summary=summary,
        analyzed_at=datetime.utcnow(),
        duration_ms=duration_ms,
    )
