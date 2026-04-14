"""Tool abstraction for Agent orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Generic, TypeVar 

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


@dataclass(frozen=True)
class Tool(Generic[InputT, OutputT]):
    name: str
    description: str
    run: Callable[[InputT], Awaitable[OutputT]]

