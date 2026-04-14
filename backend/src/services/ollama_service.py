"""Ollama service for local LLM inference."""

import logging
import re
from typing import AsyncGenerator, Union

import ollama 

from ..models import PerspectiveType
from ..config import (
    get_ollama_host,
    get_ollama_model,
    get_llm_temperature,
    get_llm_num_ctx,
    get_llm_num_predict,
    get_llm_reasoning,
)


# Configure logging
logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Exception raised when Ollama operations fail."""

    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class OllamaNotRunningError(OllamaError):
    """Exception raised when Ollama is not running."""

    def __init__(self):
        super().__init__(
            "Ollama service is not running",
            {
                "hint": "Please start Ollama with: ollama run qwen3:8b",
                "connection_url": get_ollama_host(),
            },
        )


def check_ollama_connection() -> bool:
    """Check if Ollama is running and accessible."""
    try:
        host = get_ollama_host()
        logger.debug(f"Checking Ollama connection at {host}")
        client = ollama.Client(host=host)
        client.list()
        logger.info("Ollama connection successful")
        return True
    except Exception as e:
        logger.warning(f"Ollama connection failed: {e}")
        return False


def get_ollama_client() -> ollama.Client:
    """Get Ollama client instance."""
    if not check_ollama_connection():
        raise OllamaNotRunningError()
    return ollama.Client(host=get_ollama_host())


def strip_think_tags(content: str) -> str:
    """Strip Qwen3 think/thinking tags from content."""
    # Remove <think>...</think> and variations
    patterns = [
        r"\<think\>(.*?)\<\/think\>",
        r"\<thinking\>(.*?)\<\/thinking\>",
    ]

    result = content
    for pattern in patterns:
        result = re.sub(pattern, "", result, flags=re.DOTALL | re.IGNORECASE)

    # Clean up multiple whitespace
    result = re.sub(r"\s+", " ", result).strip()
    return result


def get_default_prompt(perspective: PerspectiveType) -> str:
    """Get the default analysis prompt for a perspective."""
    if perspective == PerspectiveType.PARTY_A:
        return """作为甲方律师，请审查合同。你需要：
1. 仔细阅读合同文本，识别潜在的商业风险点
2. 评估每个风险的等级（高/中/低）
3. 给出具体的修改建议

重点从收付款节点、违约金比例、履约担保等寻找：
1. 经济利益受损（如罚金过高、账期过长）
2. 交付风险（如验收标准模糊）
3. 操作陷阱（如自动续约、单方终止权）

输出必须是JSON数组，不要有其他内容。"""
    else:
        return """作为乙方律师，请审查合同。你需要：
1. 仔细阅读合同文本，识别对我方不利的条款
2. 评估每个风险对我方的严重程度（高/中/低）
3. 给出对我方有利的修改建议

重点关注：
1. 责任边界和免责条款
2. 付款条件和账期
3. 续约和终止条款
4. 单方终止权和处罚条款

"""


async def stream_analysis(
    document_text: str,
    prompt: Union[PerspectiveType, str],
    model: str = None,
    strict_json: bool = False,
) -> AsyncGenerator[str, None]:
    """Stream analysis results from Ollama."""
    if model is None:
        model = get_ollama_model()

    client = get_ollama_client()

    # Get model configuration
    temperature = get_llm_temperature()
    num_ctx = get_llm_num_ctx()
    num_predict = get_llm_num_predict()
    reasoning = get_llm_reasoning()

    logger.info(f"[OLLAMA] Starting analysis: model={model}, temp={temperature}, ctx={num_ctx}, reasoning={reasoning}")

    if isinstance(prompt, str):
        system_prompt = prompt
    else:
        system_prompt = get_default_prompt(prompt)

    # Backward-compatible behavior:
    # - If caller passes a perspective/short system prompt, we construct the legacy prompt wrapper.
    # - If caller already built a full user prompt (phase-0+), it can pass it as document_text and
    #   provide any string as `prompt` (kept for signature compatibility).
    if "{contract_text}" in system_prompt or "合同内容：" in system_prompt:
        full_prompt = f"""{system_prompt}

请分析以下合同文本，只输出JSON数组，不要有任何其他内容：

{document_text}

只输出JSON数组格式，示例：
[{{"id":"risk_001","clause_title":"条款标题","risk_category":"经济利益/交付风险/操作陷阱","original_text":"具体条款原文片段","risk_description":"风险描述分析","suggested_revision":"修改建议","severity":"高/中/低"}}]
"""
    else:
        # Assume `document_text` is already a complete user prompt string.
        full_prompt = document_text
        if strict_json:
            full_prompt = (
                full_prompt
                + "\n\n【严格模式】只输出 JSON 数组。每个元素必须包含字段："
                "clause_title, risk_category, original_text, risk_description, suggested_revision, severity。"
                "不要 markdown，不要解释，不要多余文字。"
            )

    try:
        logger.debug("[OLLAMA] Sending request...")
        system_content = (
            "You are a legal contract reviewer. Output ONLY valid JSON array, no markdown, no thinking tags."
        )
        if strict_json:
            system_content += (
                " Each array element MUST be a JSON object with keys: "
                "clause_title, risk_category, original_text, risk_description, suggested_revision, severity."
            )
        response = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": full_prompt},
            ],
            stream=True,
            options={
                "temperature": temperature,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
                "reasoning": reasoning,
            },
        )

        content_buffer = ""
        chunk_count = 0

        for chunk in response:
            chunk_count += 1
            raw_content = chunk.get("message", {}).get("content", "")
            clean_content = strip_think_tags(raw_content)
            content_buffer += clean_content

            if clean_content:
                yield clean_content

        logger.info(f"[OLLAMA] Response complete: {chunk_count} chunks, {len(content_buffer)} chars")

    except Exception as e:
        logger.error(f"[OLLAMA] Error: {e}")
        raise OllamaError(
            f"Failed to get analysis from Ollama: {str(e)}",
            {"model": model},
        )


async def generate_suggestion_refinement(
    original_suggestion: str,
    instruction: str,
    model: str = None,
) -> str:
    """Refine a suggestion based on user instruction."""
    if model is None:
        model = get_ollama_model()

    client = get_ollama_client()
    temperature = get_llm_temperature()
    num_ctx = get_llm_num_ctx()
    num_predict = get_llm_num_predict()
    reasoning = get_llm_reasoning()

    logger.info(f"[OLLAMA] Generating refinement with {model}")

    prompt = f"""请根据用户的指示修改以下合同条款建议。

原始建议：{original_suggestion}

用户指示：{instruction}

请输出修改后的建议，只输出修改后的文本，不要有其他内容。"""

    try:
        response = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": "You are a legal contract reviewer assistant."},
                {"role": "user", "content": prompt},
            ],
            stream=False,
            options={
                "temperature": temperature,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
                "reasoning": reasoning,
            },
        )

        raw_content = response["message"]["content"]
        refined = strip_think_tags(raw_content)

        logger.info(f"[OLLAMA] Refinement complete: {len(refined)} chars")
        return refined

    except Exception as e:
        logger.error(f"[OLLAMA] Refinement error: {e}")
        raise OllamaError(f"Failed to refine suggestion: {str(e)}", {})
