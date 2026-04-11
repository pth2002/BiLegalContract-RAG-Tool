"""
Perspective prompt service for contract analysis.
Defines different analysis prompts for Party A and Party B perspectives.
"""

from typing import Dict
from enum import Enum


class PerspectiveType(str, Enum):
    """Perspective types for contract analysis."""
    PARTY_A = "party_a"  # 甲方视角 - typically the client/service recipient
    PARTY_B = "party_b"  # 乙方视角 - typically the vendor/service provider


# Party A perspective (甲方视角)
# Typically the party receiving services/goods, concerned with:
# - Service quality and deliverables
# - Payment protection
# - Termination rights
# - Liability caps favorable to them
PARTY_A_PROMPT = """你是一位专业合同审查律师，专注于保护甲方（委托方/客户）的利益。

你的任务是分析以下合同条款，从甲方的视角识别潜在风险，并提供修改建议。

分析维度：
1. 履约风险 - 乙方能否按时、按质完成服务/交付成果
2. 付款风险 - 付款条件是否对甲方有利，是否有预付款风险
3. 终止权 - 甲方是否有权在乙方违约时终止合同
4. 责任限制 - 赔偿条款是否充分保护甲方利益
5. 知识产权 - 成果归属是否明确
6. 争议解决 - 管辖地是否对甲方便利

输出格式（JSON）：
```json
{
  "risks": [
    {
      "id": "R001",
      "clause_title": "条款标题",
      "severity": "高/中/低",
      "risk_category": "经济利益/交付风险/操作陷阱",
      "original_text": "原文摘录",
      "risk_description": "风险分析说明",
      "suggested_revision": "修改建议条款"
    }
  ]
}
```

合同内容：
{contract_text}
"""
#上面那个{contract_text}是占位符
# Party B perspective (乙方视角)
# Typically the party providing services/goods, concerned with:
# - Payment security
# - Scope clarity
# - Limitation of liability
# - IP rights
# - Termination protection
PARTY_B_PROMPT = """你是一位专业合同审查律师，专注于保护乙方（受托方/供应商）的利益。

你的任务是分析以下合同条款，从乙方的视角识别潜在风险，并提供修改建议。

分析维度：
1. 付款保障 - 付款条件是否明确，账期是否合理
2. 范围界定 - 服务范围是否清晰，有无无限责任风险
3. 知识产权 - 成果使用范围是否受限
4. 终止保护 - 甲方单方终止的赔偿机制
5. 责任限制 - 是否需要设置赔偿上限
6. 验收标准 - 验收流程是否公平合理

输出格式（JSON）：
```json
{
  "risks": [
    {
      "id": "R001",
      "clause_title": "条款标题",
      "severity": "高/中/低",
      "risk_category": "经济利益/交付风险/操作陷阱",
      "original_text": "原文摘录",
      "risk_description": "风险分析说明",
      "suggested_revision": "修改建议条款"
    }
  ]
}
```

合同内容：
{contract_text}
"""

# Perspective descriptions for frontend display
PERSPECTIVE_INFO: Dict[str, Dict] = {
    "party_a": {
        "name": "甲方视角",
        "description": "关注履约质量、付款节奏控制、终止权、赔偿上限",
        "focusAreas": ["履约风险", "付款风险", "终止权", "责任限制"]
    },
    "party_b": {
        "name": "乙方视角",
        "description": "关注收款保障、范围界定、知识产权、单方终止保护",
        "focusAreas": ["付款保障", "范围界定", "知识产权", "终止保护"]
    }
}


def get_perspective_prompt(perspective: PerspectiveType) -> str:
    """
    Get the system prompt for the specified perspective.

    Args:
        perspective: The perspective type (party_a or party_b)

    Returns:
        The formatted system prompt for contract analysis
    """
    prompts = {
        PerspectiveType.PARTY_A: PARTY_A_PROMPT,
        PerspectiveType.PARTY_B: PARTY_B_PROMPT,
    }
    return prompts.get(perspective, PARTY_A_PROMPT)


def get_perspective_info(perspective: str) -> Dict:
    """
    Get display information for the specified perspective.

    Args:
        perspective: The perspective identifier (party_a or party_b)

    Returns:
        Dictionary with name, description, and focus areas
    """
    return PERSPECTIVE_INFO.get(perspective, PERSPECTIVE_INFO["party_a"])
