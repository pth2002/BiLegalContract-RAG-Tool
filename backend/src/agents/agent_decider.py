"""Backward-compatibility shim — functionality moved to fallback_decider.py."""

from __future__ import annotations

# Re-export public symbols for existing callers
from .fallback_decider import decide_fallback, fallback_decide  # noqa: F401
from .action_models import ActionDecision  # noqa: F401
from .agent_state import AgentRuntimeState  # noqa: F401
from .policy import AgentPolicy  # noqa: F401

# Legacy aliases kept for any external callers
SimplifiedAction = None
SimplifiedDecision = None


async def decide_simplified_as_action_decision(
    *,
    state: AgentRuntimeState,
    policy: AgentPolicy,
    **kwargs,
) -> ActionDecision:
    """Deprecated: use fallback_decider.decide_fallback instead."""
    return await decide_fallback(state=state, policy=policy)
