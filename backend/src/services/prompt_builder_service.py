"""Prompt builder service for grounded RAG analysis."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True) 
class RetrievedContext:
    """A single retrieved context chunk for RAG prompting."""

    chunk_id: str
    content: str
    score: float | None = None


def _inject_contract_text(template: str, contract_text: str) -> str:
    """Replace only the explicit contract_text token and keep literal JSON braces intact."""

    return template.replace("{contract_text}", contract_text)


def build_analysis_user_prompt(
    *,
    system_prompt_template: str,
    contract_text: str,
    retrieved_contexts: list[RetrievedContext] | None = None,
) -> str:
    """Build a grounded user prompt for analysis."""

    contexts = retrieved_contexts or []
    system_prompt = _inject_contract_text(system_prompt_template, contract_text)

    if not contexts:
        return system_prompt

    context_blocks = []
    for context in contexts:
        score_line = f"\nscore={context.score:.4f}" if context.score is not None else ""
        context_blocks.append(f"[{context.chunk_id}]{score_line}\n{context.content}".strip())

    rag_context = "\n\n---\n\n".join(context_blocks)

    return (
        "以下是从合同中检索到的高相关证据片段。请优先基于这些片段识别风险，并尽量让 original_text 与这些片段直接对齐。\n\n"
        f"{rag_context}\n\n"
        "====================\n\n"
        + system_prompt
    )
