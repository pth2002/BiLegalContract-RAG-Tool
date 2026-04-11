"""LLM 门控：替代硬阈值（如 chunk 数量）——由模型判断检索是否足够继续。"""

from __future__ import annotations

import json
import logging

from ..config import get_llm_num_ctx, get_llm_num_predict, get_llm_reasoning, get_llm_temperature, get_ollama_model
from ..services.ollama_service import get_ollama_client
from .agent_state import AgentRuntimeState

logger = logging.getLogger(__name__)


def _chunks_summary(state: AgentRuntimeState, max_items: int = 12) -> str:
    lines = []
    for c in state.retrieved_chunks[:max_items]:
        lines.append(f"- id={c.chunk_id} score={getattr(c, 'score', 0):.4f} text={c.content[:220].replace(chr(10), ' ')}")
    if not lines:
        return "(无检索块)"
    return "\n".join(lines)


async def llm_judge_retrieval_sufficient(state: AgentRuntimeState) -> dict:
    """
    返回:
      sufficient: bool — True 则视为可继续（等价于原 policy 通过）
      verdict: "proceed" | "retrieve_more"
      reason: str
    """
    client = get_ollama_client()
    model = get_ollama_model()
    sys_msg = (
        "你是合同检索质量评审员。只输出一个 JSON，不要其它文字。\n"
        "键：sufficient(布尔), verdict(\"proceed\"或\"retrieve_more\"), reason(短字符串)。\n"
        "若当前检索片段已足以支撑「按用户视角做违约/付款/终止等风险分析」，则 sufficient=true。"
    )
    user_msg = (
        f"用户视角：{state.request.perspective.value}\n"
        f"当前检索结果：\n{_chunks_summary(state)}\n\n"
        "你认为信息是否足够？\n"
        "- yes → verdict=proceed, sufficient=true\n"
        "- no → verdict=retrieve_more, sufficient=false\n"
    )
    try:
        response = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg},
            ],
            stream=False,
            options={
                "temperature": min(get_llm_temperature(), 0.2),
                "num_ctx": get_llm_num_ctx(),
                "num_predict": min(get_llm_num_predict(), 384),
                "reasoning": get_llm_reasoning(),
            },
        )
        raw = response["message"]["content"].strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no json")
        data = json.loads(raw[start : end + 1])
        suf = bool(data.get("sufficient"))
        verdict = str(data.get("verdict", "proceed" if suf else "retrieve_more")).lower()
        if verdict not in ("proceed", "retrieve_more"):
            verdict = "proceed" if suf else "retrieve_more"
        reason = str(data.get("reason", ""))
        return {
            "sufficient": suf,
            "verdict": verdict,
            "reason": reason,
        }
    except Exception as e:
        logger.warning("[LLM_GATE] retrieval judge failed: %s → conservative retrieve_more", e)
        return {"sufficient": False, "verdict": "retrieve_more", "reason": f"llm_gate_error:{e}"}
