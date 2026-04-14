"""v4：将 reflection.fix_plan 落地为 state（检索 query 覆盖等），驱动下一轮真实修复。""" 

from __future__ import annotations

import logging
import re

from .agent_state import AgentRuntimeState

logger = logging.getLogger(__name__)


def apply_fix_plan_to_state(state: AgentRuntimeState, fix_plan: str) -> bool:
    """
    从自然语言 fix_plan 中提取主题词，写入 query_override / meta。
    返回是否成功应用（可用于下一轮优先 retrieve / refine_query）。
    """
    fp = (fix_plan or "").strip()
    if not fp:
        return False
    terms: list[str] = []
    if re.search(r"终止|解除|通知|续签", fp):
        terms.append("合同终止 解除条件 通知期限")
    if re.search(r"付款|支付|价款|结算|发票", fp):
        terms.append("付款条件 价款支付 结算 发票")
    if re.search(r"违约|赔偿|责任|滞纳|罚金", fp):
        terms.append("违约责任 赔偿上限 违约金")
    if re.search(r"保密|知识产权|竞业", fp):
        terms.append("保密 知识产权 竞业限制")
    if re.search(r"争议|仲裁|诉讼|管辖", fp):
        terms.append("争议解决 仲裁 管辖 法律适用")
    if not terms:
        # 取 fix_plan 前 80 字作为检索补充
        terms.append(fp[:80].replace("\n", " "))

    q = f"{' '.join(terms)} {state.request.perspective.value} 合同审查"
    state.query_override = q[:600]
    state.meta["fix_plan_applied"] = True
    state.meta["fix_plan_snippet"] = fp[:500]
    logger.info("[FIX_PLAN] applied query_override len=%d", len(state.query_override or ""))
    return True
