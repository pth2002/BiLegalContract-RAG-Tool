"""Suggestion refinement service using Ollama for natural language processing."""

import json
import re
from typing import Optional

from ..models import RiskCard
from .ollama_service import ( 
    get_ollama_client,
    OLLAMA_HOST,
    DEFAULT_MODEL,
    OllamaError,
)


class RefineServiceError(Exception):
    """Exception raised during refinement."""

    pass


async def refine_suggestion(
    original_suggestion: str,
    instruction: str,
    model: str = DEFAULT_MODEL,
) -> str:
    """Refine a suggestion based on user instruction.

    Args:
        original_suggestion: The original suggestion text
        instruction: User's refinement instruction
        model: Ollama model to use

    Returns:
        Refined suggestion text
    """
    client = get_ollama_client()

    # Build a comprehensive prompt for suggestion refinement
    prompt = f"""请根据用户的指示修改以下合同条款建议。

原始建议：
{original_suggestion}

用户指示：
{instruction}

要求：
1. 仅修改建议内容，保持建议的专业性和法律准确性
2. 如果用户要求语气更委婉，请使用更礼貌的表达
3. 如果用户要求更严格，请强化条款的保护力度
4. 不要改变建议的核心条款内容
5. 只输出修改后的文本，不要有其他内容"""

    try:
        response = client.chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a legal contract reviewer assistant specializing in refining contract clause suggestions.",
                },
                {"role": "user", "content": prompt},
            ],
            stream=False,
        )

        refined = response["message"]["content"]

        # Clean up the response - remove any markdown formatting if present
        refined = refined.strip()
        if refined.startswith("```"):
            # Remove markdown code blocks
            lines = refined.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            refined = "\n".join(lines).strip()

        return refined

    except Exception as e:
        raise OllamaError(
            f"Failed to refine suggestion: {str(e)}",
            {"instruction": instruction},
        )


def compute_diff(original: str, refined: str) -> dict:
    """Compute simple diff between original and refined text.

    Args:
        original: Original text
        refined: Refined text

    Returns:
        Dictionary with added and removed lines
    """
    original_lines = set(original.split("\n"))
    refined_lines = set(refined.split("\n"))

    added = list(refined_lines - original_lines)
    removed = list(original_lines - refined_lines)

    return {
        "added": added,
        "removed": removed,
        "added_count": len(added),
        "removed_count": len(removed),
    }
