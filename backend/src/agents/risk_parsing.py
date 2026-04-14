"""Shared risk JSON parsing and RiskCard construction for agent runtime."""

from __future__ import annotations 

import json
import re
from typing import Any
from uuid import UUID

from json_repair import repair_json

from ..models import RiskCard
from ..models.enums import Severity


def clean_json_array_content(content: str) -> str:
    cleaned = content.strip()
    cleaned = cleaned.replace("```json", "").replace("```JSON", "").replace("```", "").strip()
    start_idx = cleaned.find("[")
    if start_idx != -1:
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


def parse_risk_json(content: str) -> list[dict[str, Any]]:
    if not content:
        return []
    cleaned = clean_json_array_content(content)
    try:
        risks = json.loads(cleaned)
        if isinstance(risks, list):
            return risks
    except Exception:
        pass

    try:
        repaired = repair_json(cleaned, ensure_ascii=False)
        repaired_data = json.loads(repaired) if isinstance(repaired, str) else repaired
        if isinstance(repaired_data, list):
            return repaired_data
        if isinstance(repaired_data, dict):
            return [repaired_data] if "clause_title" in repaired_data else []
    except Exception:
        pass

    pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(pattern, content, re.DOTALL)
    risks: list[dict] = []
    for match in matches:
        try:
            risk = json.loads(match)
            if isinstance(risk, dict) and "clause_title" in risk and "severity" in risk:
                risks.append(risk)
        except Exception:
            continue
    return risks


def map_severity(value: str) -> str:
    normalized = (value or "").lower().strip()
    if normalized in {"高", "中", "低"}:
        return normalized
    if normalized in ["高风险", "high", "h"]:
        return "高"
    if normalized in ["中风险", "medium", "m", "中等"]:
        return "中"
    if normalized in ["低风险", "low", "l"]:
        return "低"
    return "中"


def create_risk_card(risk_dict: dict, document_id: UUID, index: int) -> RiskCard:
    sev = map_severity(risk_dict.get("severity", "中"))
    severity_enum = Severity.HIGH if sev == "高" else Severity.LOW if sev == "低" else Severity.MEDIUM
    return RiskCard(
        id=f"risk_{index + 1:03d}",
        clause_title=risk_dict.get("clause_title", "未知条款"),
        risk_category=risk_dict.get("risk_category", "其他风险"),
        original_text=risk_dict.get("original_text", ""),
        risk_description=risk_dict.get("risk_description", ""),
        suggested_revision=risk_dict.get("suggested_revision", ""),
        severity=severity_enum,
        document_id=document_id,
    )
