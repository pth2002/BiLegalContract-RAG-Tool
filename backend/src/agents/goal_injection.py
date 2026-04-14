"""动态目标注入 + v5 子目标拆解：让 Agent 自己定义做什么、先做什么。""" 

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from ..config import get_llm_num_ctx, get_llm_num_predict, get_llm_reasoning, get_llm_temperature, get_ollama_model
from ..models import AnalysisRequest, Document
from ..services.ollama_service import get_ollama_client

if TYPE_CHECKING:
    from .agent_state import AgentRuntimeState

logger = logging.getLogger(__name__)

DEFAULT_GOAL = "产出高质量、可复核的结构化合同风险报告（含条款引用与可执行修改建议）"
_JSON_RETRIES = 3


async def inject_dynamic_goal(request: AnalysisRequest, document: Document) -> str:
    """LLM 简述终局目标；失败则返回默认。"""
    client = get_ollama_client()
    model = get_ollama_model()
    sys_msg = (
        "你是合同审查产品经理。只输出一个 JSON：{\"final_goal\":\"...\"}，用中文一句话描述最终交付物。"
        "终局目标应强调：风险完整性、条款可引用、对当前视角（甲方/乙方）有利。"
    )
    user_msg = (
        f"分析视角：{request.perspective.value}\n"
        f"选项：{request.options}\n"
        f"合同篇幅（字符）：{len(document.text_content or '')}\n"
        "最终目标应服务于：高质量风险报告。"
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
                "temperature": min(get_llm_temperature(), 0.3),
                "num_ctx": get_llm_num_ctx(),
                "num_predict": min(get_llm_num_predict(), 256),
                "reasoning": get_llm_reasoning(),
            },
        )
        raw = response["message"]["content"].strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no json")
        data = json.loads(raw[start : end + 1])
        g = data.get("final_goal") or data.get("goal")
        if g and isinstance(g, str) and len(g.strip()) > 5:
            return g.strip()[:500]
    except Exception as e:
        logger.debug("[GOAL_INJECTION] fallback: %s", e)
    return DEFAULT_GOAL


async def decompose_sub_goals(state: "AgentRuntimeState") -> list[str]:
    """
    v5：LLM 拆解子目标。输出 {"sub_goals":["...", ...]}。
    写入 state.sub_goals / current_goal / current_goal_index。
    """
    client = get_ollama_client()
    model = get_ollama_model()
    sys_msg = (
        "你是合同审查策略师。请将终局目标拆解为 3~6 个具体子目标（中文短句），按执行顺序排列。\n"
        "只输出 JSON：{\"sub_goals\":[\"...\",\"...\"]}"
    )
    user_msg = (
        f"终局目标：{state.primary_goal}\n"
        f"视角：{state.request.perspective.value}\n"
        f"合同长度（字符）：{len(state.document.text_content or '')}\n"
        "请拆解。"
    )
    for attempt in range(1, _JSON_RETRIES + 1):
        try:
            response = client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user_msg},
                ],
                stream=False,
                options={
                    "temperature": min(get_llm_temperature(), 0.3),
                    "num_ctx": get_llm_num_ctx(),
                    "num_predict": min(get_llm_num_predict(), 512),
                    "reasoning": get_llm_reasoning(),
                },
            )
            raw = response["message"]["content"].strip()
            start, end = raw.find("{"), raw.rfind("}")
            if start == -1 or end <= start:
                raise ValueError("no json")
            data = json.loads(raw[start : end + 1])
            subs = data.get("sub_goals")
            if isinstance(subs, list) and len(subs) >= 2:
                result = [str(x)[:200] for x in subs[:8]]
                state.sub_goals = result
                state.current_goal = result[0]
                state.current_goal_index = 0
                logger.info("[GOAL] decomposed %d sub_goals", len(result))
                return result
        except Exception as e:
            logger.warning("[GOAL] decompose attempt %d/%d: %s", attempt, _JSON_RETRIES, e)
    fallback = ["分析付款条款风险", "检查违约责任", "验证终止条件"]
    state.sub_goals = fallback
    state.current_goal = fallback[0]
    state.current_goal_index = 0
    return fallback


def advance_sub_goal(state: "AgentRuntimeState") -> bool:
    """将 current_goal 推进到下一个子目标，返回是否还有剩余。"""
    if not state.sub_goals:
        return False
    state.completed_goals.append(state.current_goal)
    state.current_goal_index += 1
    if state.current_goal_index < len(state.sub_goals):
        state.current_goal = state.sub_goals[state.current_goal_index]
        return True
    state.current_goal = ""
    return False
