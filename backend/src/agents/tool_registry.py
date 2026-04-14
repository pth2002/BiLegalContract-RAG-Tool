"""Central tool registry: consistent async interface for agent runtime."""
 
from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from ..config import (
    get_llm_num_ctx,
    get_llm_num_predict,
    get_llm_reasoning,
    get_llm_temperature,
    get_ollama_model,
    get_retriever_top_k,
)
from ..services.evidence_service import attach_evidence_to_risks
from ..services.indexing_service import index_document
from ..services.ollama_service import get_ollama_client, stream_analysis
from ..services.prompt_builder_service import RetrievedContext, build_analysis_user_prompt
from ..services.prompt_service import get_perspective_prompt
from ..services.retrieval_service import build_retrieval_queries, retrieve_contexts, retrieve_contexts_merged
from ..services.vector_store_service import has_indexed, init_vector_store
from .agent_state import AgentRuntimeState
from .policy import AgentPolicy
from .risk_parsing import create_risk_card, parse_risk_json

logger = logging.getLogger(__name__)

ToolFn = Callable[[AgentRuntimeState, AgentPolicy, dict[str, Any]], Awaitable[dict[str, Any]]]

TOOL_DESCRIPTIONS: dict[str, str] = {
    "ensure_index": "Ensure the document has been indexed for vector retrieval.",
    "retrieve_context": "Run modern hybrid retrieval over contract evidence chunks.",
    "refine_query": "Use the LLM to rewrite the retrieval query when evidence is weak.",
    "widen_retrieval": "Increase retrieval breadth and try again.",
    "extract_clauses": "Return retrieved clause previews for debugging and observability.",
    "analyze_risks": "Generate structured risk cards from grounded evidence.",
    "retry_generation_strict": "Retry risk generation with stricter JSON constraints.",
    "verify_evidence": "Attach chunk citations and compute grounding metrics per risk.",
    "summarize_partial": "Summarize the current runtime state.",
    "finish": "Mark the run as complete.",
    "degrade_output": "Finish with a degraded but explicit output state.",
}


def _build_rule_based_risks(state: AgentRuntimeState) -> list[dict[str, Any]]:
    text = state.document.text_content or ""
    snippets = state.retrieved_chunks or []
    perspective = "甲方" if state.request.perspective.value == "party_a" else "乙方"

    rules = [
        {
            "name": "付款条款风险",
            "keywords": ["付款", "支付", "价款", "账期", "发票", "逾期付款"],
            "risk_category": "付款条款",
            "severity": "medium",
            "risk_description": f"付款、账期或发票安排可能对{perspective}现金流和履约节奏不利，建议重点核查付款条件、触发节点和违约后果。",
            "suggested_revision": "建议明确付款节点、付款前置条件、发票开具义务、逾期付款责任，并补充对等的暂停履行或催告机制。",
        },
        {
            "name": "违约责任风险",
            "keywords": ["违约", "违约金", "赔偿", "损失", "责任承担"],
            "risk_category": "违约责任",
            "severity": "high",
            "risk_description": f"违约责任或赔偿范围可能过宽，容易放大{perspective}的经济责任敞口。",
            "suggested_revision": "建议增加责任上限、排除间接损失，并对违约金比例、赔偿范围和触发条件作出更清晰约定。",
        },
        {
            "name": "解除终止风险",
            "keywords": ["解除", "终止", "单方", "提前终止", "自动续约"],
            "risk_category": "终止解除",
            "severity": "high",
            "risk_description": f"合同解除、终止或自动续约安排可能使{perspective}处于被动状态，需要核查单方解除权和续约条件。",
            "suggested_revision": "建议明确解除条件、通知期限、补救期、自动续约的退出机制，并避免一方享有过强的单方终止权。",
        },
        {
            "name": "验收交付风险",
            "keywords": ["验收", "交付", "交货", "成果", "测试", "确认"],
            "risk_category": "验收交付",
            "severity": "medium",
            "risk_description": f"验收标准或交付条件如果不够清晰，容易导致{perspective}在履约、结算或责任认定时处于不利位置。",
            "suggested_revision": "建议补充明确的验收标准、验收期限、默示验收规则及不通过后的整改与复验流程。",
        },
        {
            "name": "知识产权风险",
            "keywords": ["知识产权", "著作权", "专利", "商标", "成果归属"],
            "risk_category": "知识产权",
            "severity": "medium",
            "risk_description": f"知识产权归属、授权边界或侵权责任分配不明确，可能给{perspective}带来持续法律风险。",
            "suggested_revision": "建议明确成果归属、授权范围、侵权担保与第三方权利瑕疵处理机制。",
        },
        {
            "name": "保密义务风险",
            "keywords": ["保密", "商业秘密", "披露", "信息安全", "数据"],
            "risk_category": "保密义务",
            "severity": "medium",
            "risk_description": f"保密义务、例外情形或责任追究不够明确，可能影响{perspective}的信息安全和后续维权。",
            "suggested_revision": "建议补充保密范围、允许披露情形、保密期限、数据安全义务及违约责任。",
        },
    ]

    generated: list[dict[str, Any]] = []
    used_titles: set[str] = set()
    search_sources = [chunk.content for chunk in snippets] or [text]

    for rule in rules:
        matched_excerpt = ""
        for source in search_sources:
            if any(keyword in source for keyword in rule["keywords"]):
                matched_excerpt = source[:220]
                break
        if not matched_excerpt:
            continue
        if rule["name"] in used_titles:
            continue
        used_titles.add(rule["name"])
        generated.append(
            {
                "clause_title": rule["name"],
                "risk_category": rule["risk_category"],
                "original_text": matched_excerpt,
                "risk_description": rule["risk_description"],
                "suggested_revision": rule["suggested_revision"],
                "severity": rule["severity"],
            }
        )

    if not generated and text.strip():
        excerpt = (snippets[0].content if snippets else text)[:220]
        generated.append(
            {
                "clause_title": "合同条款综合风险",
                "risk_category": "其他风险",
                "original_text": excerpt,
                "risk_description": f"当前模型未能稳定提取结构化风险，但从合同文本看仍建议从{perspective}视角继续核查付款、违约、终止和交付条款。",
                "suggested_revision": "建议补充更明确的付款条件、违约责任边界、解除终止条件和验收标准，并结合业务背景做人工复核。",
                "severity": "medium",
            }
        )

    return generated[:5]


def _build_strict_extraction_prompt(state: AgentRuntimeState) -> str:
    snippets = []
    for index, chunk in enumerate(state.retrieved_chunks[:6], start=1):
        snippets.append(
            f"[证据{index}] chunk_id={chunk.chunk_id} score={chunk.score:.4f}\n{chunk.content[:1200]}"
        )

    snippet_block = "\n\n".join(snippets) if snippets else "(无可用证据片段)"
    perspective = "甲方" if state.request.perspective.value == "party_a" else "乙方"

    return (
        f"你是一名资深合同审查律师。请站在{perspective}视角，只基于给定证据片段提取风险。\n"
        "如果证据不足，不要编造；如果能识别风险，请输出 1 到 5 条。\n"
        "只输出 JSON 数组，不要 markdown，不要解释，不要额外文字。\n"
        "每个元素必须包含这些字段："
        "clause_title, risk_category, original_text, risk_description, suggested_revision, severity。\n"
        "severity 只能是：high, medium, low。\n"
        "risk_category 优先使用：付款条款、违约责任、终止解除、验收交付、知识产权、保密义务、争议解决、其他风险。\n\n"
        f"证据片段：\n{snippet_block}"
    )


def _materialize_risks(state: AgentRuntimeState, parsed: list[dict[str, Any]]) -> dict[str, Any]:
    risks = [create_risk_card(item, state.document.id, i) for i, item in enumerate(parsed)]
    evidence_summary = attach_evidence_to_risks(risks, state.retrieved_chunks)
    state.accepted_risks = risks
    state.meta["evidence_summary"] = evidence_summary
    return evidence_summary


async def _extract_risks_with_fallback(state: AgentRuntimeState, *, strict: bool) -> dict[str, Any]:
    await build_prompts(state)
    if not state.user_prompt or not state.system_prompt_template:
        return {"ok": False, "error": "no_prompt"}

    buf = ""
    async for chunk in stream_analysis(state.user_prompt, state.system_prompt_template, strict_json=strict):
        buf += chunk
    state.last_llm_raw = buf
    state.generated_candidates.append(buf)
    state.budget.llm_calls += 1
    parsed = parse_risk_json(buf)

    fallback_used = False
    fallback_chars = 0
    if not parsed and state.retrieved_chunks:
        fallback_used = True
        client = get_ollama_client()
        model = get_ollama_model()
        fallback_prompt = _build_strict_extraction_prompt(state)
        response = client.chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a legal risk extractor. Output ONLY a valid JSON array. "
                        "No markdown. No commentary."
                    ),
                },
                {"role": "user", "content": fallback_prompt},
            ],
            stream=False,
            options={
                "temperature": 0.0,
                "num_ctx": get_llm_num_ctx(),
                "num_predict": min(get_llm_num_predict(), 768),
                "reasoning": False,
            },
        )
        fallback_raw = response["message"]["content"].strip()
        fallback_chars = len(fallback_raw)
        state.generated_candidates.append(fallback_raw)
        state.last_llm_raw = fallback_raw or state.last_llm_raw
        state.budget.llm_calls += 1
        parsed = parse_risk_json(fallback_raw)
        if not parsed:
            state.warnings.append("strict_extraction_fallback_returned_empty")
            parsed = _build_rule_based_risks(state)
            if parsed:
                state.warnings.append("rule_based_risk_fallback_used")
    elif not parsed:
        parsed = _build_rule_based_risks(state)
        if parsed:
            state.warnings.append("rule_based_risk_fallback_used")

    if parsed:
        state.last_llm_raw = json.dumps(parsed, ensure_ascii=False)

    state.budget.tool_calls += 1
    evidence_summary = _materialize_risks(state, parsed)
    return {
        "llm_chars": len(buf),
        "parsed_count": len(parsed),
        "risk_cards": len(state.accepted_risks),
        "strict": strict,
        "fallback_used": fallback_used,
        "fallback_chars": fallback_chars,
        "evidence_summary": evidence_summary,
    }


async def _ensure_index(state: AgentRuntimeState, policy: AgentPolicy, inp: dict[str, Any]) -> dict[str, Any]:
    await init_vector_store()
    if not await has_indexed(state.document.id):
        await index_document(state.document)
    state.indexed = True
    state.budget.tool_calls += 1
    return {"indexed": True, "document_id": str(state.document.id)}


async def _retrieve_context(state: AgentRuntimeState, policy: AgentPolicy, inp: dict[str, Any]) -> dict[str, Any]:
    final_k = min(20, get_retriever_top_k() + state.top_k_boost)
    if state.query_override:
        chunks = await retrieve_contexts(
            document_id=state.document.id,
            session_id=state.document.session_id,
            query=state.query_override,
            top_k=final_k,
        )
        state.last_queries = [state.query_override]
    else:
        chunks = await retrieve_contexts_merged(
            document_id=state.document.id,
            session_id=state.document.session_id,
            perspective=state.request.perspective,
            options=state.request.options,
            final_top_k=final_k,
            document_text=state.document.text_content,
            document=state.document,
        )
        state.last_queries = build_retrieval_queries(state.request.perspective, state.request.options)
    state.retrieved_chunks = chunks
    state.budget.retrieval_calls += 1
    state.budget.tool_calls += 1
    if state.query_override:
        state.working_memory.attempted_queries.append(state.query_override)
    return {
        "retrieved_count": len(chunks),
        "top_k": final_k,
        "methods": sorted({method for chunk in chunks for method in chunk.retrieval_methods}),
    }


async def _refine_query(state: AgentRuntimeState, policy: AgentPolicy, inp: dict[str, Any]) -> dict[str, Any]:
    if state.budget.refine_calls >= policy.max_refine_rounds:
        return {"skipped": True, "reason": "max_refine_rounds"}

    retrieved = state.retrieved_chunks
    snippets = "\n".join(
        f"- {chunk.chunk_id} methods={chunk.retrieval_methods} score={chunk.score:.4f}: {chunk.content[:180]}"
        for chunk in retrieved[:5]
    )
    queries = state.last_queries or build_retrieval_queries(state.request.perspective, state.request.options)
    client = get_ollama_client()
    model = get_ollama_model()
    response = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": 'Output strict JSON: {"query":"..."} only.'},
            {
                "role": "user",
                "content": (
                    f"Perspective: {state.request.perspective.value}\n"
                    f"Current queries: {json.dumps(queries, ensure_ascii=False)}\n"
                    f"Evidence snippets:\n{snippets}\n"
                    "Please propose a sharper retrieval query for contract risk review."
                ),
            },
        ],
        stream=False,
        options={
            "temperature": min(get_llm_temperature(), 0.2),
            "num_ctx": get_llm_num_ctx(),
            "num_predict": min(get_llm_num_predict(), 256),
            "reasoning": get_llm_reasoning(),
        },
    )
    content = response["message"]["content"].strip()
    start, end = content.find("{"), content.rfind("}")
    query = None
    if start != -1 and end > start:
        try:
            query = json.loads(content[start : end + 1]).get("query")
        except Exception:
            query = None
    if not query:
        query = f"合同 {state.request.perspective.value} 违约责任 付款 终止 赔偿 风险"
    state.query_override = query
    state.budget.refine_calls += 1
    state.budget.tool_calls += 1
    return {"query_override": query}


async def _widen_retrieval(state: AgentRuntimeState, policy: AgentPolicy, inp: dict[str, Any]) -> dict[str, Any]:
    state.top_k_boost += int(inp.get("delta", 4))
    state.query_override = None
    return await _retrieve_context(state, policy, {})


async def _extract_clauses(state: AgentRuntimeState, policy: AgentPolicy, inp: dict[str, Any]) -> dict[str, Any]:
    clauses = [
        {
            "chunk_id": chunk.chunk_id,
            "score": chunk.score,
            "methods": chunk.retrieval_methods,
            "preview": chunk.content[:200],
        }
        for chunk in state.retrieved_chunks[:12]
    ]
    state.budget.tool_calls += 1
    return {"clauses": clauses, "count": len(clauses)}


async def build_prompts(state: AgentRuntimeState) -> None:
    system_prompt_template = get_perspective_prompt(state.request.perspective)
    contexts = [
        RetrievedContext(chunk_id=chunk.chunk_id, content=chunk.content, score=chunk.score)
        for chunk in state.retrieved_chunks
    ]
    user_prompt = build_analysis_user_prompt(
        system_prompt_template=system_prompt_template,
        contract_text=state.document.text_content,
        retrieved_contexts=contexts if contexts else None,
    )
    state.system_prompt_template = system_prompt_template
    state.user_prompt = user_prompt


async def _analyze_risks(state: AgentRuntimeState, policy: AgentPolicy, inp: dict[str, Any]) -> dict[str, Any]:
    return await _extract_risks_with_fallback(state, strict=False)


async def _retry_generation_strict(state: AgentRuntimeState, policy: AgentPolicy, inp: dict[str, Any]) -> dict[str, Any]:
    return await _extract_risks_with_fallback(state, strict=True)


async def _verify_evidence(state: AgentRuntimeState, policy: AgentPolicy, inp: dict[str, Any]) -> dict[str, Any]:
    summary = attach_evidence_to_risks(state.accepted_risks, state.retrieved_chunks)
    state.evidence_verification_passed = summary["grounding_ratio"] >= 0.3 or summary["total_risks"] == 0
    state.meta["evidence_summary"] = summary
    state.budget.tool_calls += 1
    return summary


async def _summarize_partial(state: AgentRuntimeState, policy: AgentPolicy, inp: dict[str, Any]) -> dict[str, Any]:
    summary = (
        f"partial_state: chunks={len(state.retrieved_chunks)} "
        f"risks={len(state.accepted_risks)} warnings={len(state.warnings)}"
    )
    state.observations.append(summary)
    state.budget.tool_calls += 1
    return {"summary": summary}


async def _finish(state: AgentRuntimeState, policy: AgentPolicy, inp: dict[str, Any]) -> dict[str, Any]:
    state.finished = True
    state.budget.tool_calls += 1
    return {"finished": True}


async def _degrade_output(state: AgentRuntimeState, policy: AgentPolicy, inp: dict[str, Any]) -> dict[str, Any]:
    state.degraded = True
    reason = inp.get("reason", "未满足验收标准，降级交付")
    state.warnings.append(str(reason))
    state.finished = True
    state.budget.tool_calls += 1
    return {"degraded": True, "reason": reason}


_REGISTRY: dict[str, ToolFn] = {
    "ensure_index": _ensure_index,
    "retrieve_context": _retrieve_context,
    "refine_query": _refine_query,
    "widen_retrieval": _widen_retrieval,
    "extract_clauses": _extract_clauses,
    "analyze_risks": _analyze_risks,
    "retry_generation_strict": _retry_generation_strict,
    "verify_evidence": _verify_evidence,
    "summarize_partial": _summarize_partial,
    "finish": _finish,
    "degrade_output": _degrade_output,
}


def list_tool_names() -> list[str]:
    return list(_REGISTRY.keys())


def get_tool_description_map() -> dict[str, str]:
    return dict(TOOL_DESCRIPTIONS)


async def run_tool(
    name: str,
    state: AgentRuntimeState,
    policy: AgentPolicy,
    action_input: dict[str, Any],
) -> dict[str, Any]:
    fn = _REGISTRY.get(name)
    if not fn:
        raise ValueError(f"unknown_tool:{name}")
    return await fn(state, policy, action_input)
