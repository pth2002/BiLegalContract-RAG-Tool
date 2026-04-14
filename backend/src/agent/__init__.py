"""
文档中的 `agent/` 命名空间入口；实现位于同级包 `agents/`。

推荐：`from agents.agent_runtime import AgentRuntime`
亦可：`from agent import AgentRuntime`（本包转发）。
"""

from ..agents.agent_runtime import AgentRuntime
from ..agents.agent_state import AgentRuntimeState, AgentState, build_agent_state_view
from ..agents.fallback_decider import decide_fallback
from ..agents.tool_executor import execute as execute_tool
from ..agents.tool_registry import list_tool_names, run_tool
from ..agents.memory import AgentMemory, Memory
from ..agents.reflection import ReflectionResult, reflect_after_tool

__all__ = [
    "AgentRuntime",
    "AgentRuntimeState",
    "AgentState",
    "build_agent_state_view",
    "decide_fallback",
    "execute_tool",
    "list_tool_names",
    "run_tool",
    "AgentMemory",
    "Memory",
    "ReflectionResult",
    "reflect_after_tool",
]
 
asdasd
