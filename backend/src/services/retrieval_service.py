"""Retrieval service: language-aware dense + lexical hybrid retrieval with RRF."""

from __future__ import annotations

import asyncio
import logging
import math
import re
from collections import Counter
from typing import Any, Literal
from uuid import UUID

from ..config import (
    get_coarse_recall_max_per_query,
    get_coarse_recall_mult, 
    get_hybrid_rrf_k,
    get_retrieval_filter_min_chars,
    get_rerank_pool_mult,
    get_retriever_top_k,
)
from ..models import Document, PerspectiveType, RetrievedChunk
from .chunking_service import chunk_document, chunk_text
from .embedding_service import embed_query_text, embed_texts
from .reranking_service import rerank_retrieved_chunks
from .vector_store_service import search

logger = logging.getLogger(__name__)

AnalysisLanguage = Literal["auto", "zh", "en"]


def detect_language(text: str) -> str:
    """Detect text language based on character ratios.

    Returns:
        'zh'    — CJK chars make up >= 30 % of non-whitespace chars
        'en'    — ASCII-alpha chars make up >= 70 % of non-whitespace chars
        'mixed' — everything else
    """
    if not text:
        return "mixed"
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return "mixed"
    total = len(chars)
    cjk = sum(1 for c in chars if "\u4e00" <= c <= "\u9fff")
    if cjk / total >= 0.3:
        return "zh"
    latin = sum(1 for c in chars if c.isascii() and c.isalpha())
    if latin / total >= 0.7:
        return "en"
    return "mixed"

_DEFAULT_FOCUS_BY_LANGUAGE_AND_PERSPECTIVE: dict[str, dict[PerspectiveType, list[str]]] = {
    "zh": {
        PerspectiveType.PARTY_A: [
            "付款条件",
            "违约责任",
            "终止解除",
            "赔偿责任",
            "责任边界",
            "风险分配",
        ],
        PerspectiveType.PARTY_B: [
            "付款条件",
            "违约责任",
            "免责条款",
            "终止解除",
            "责任边界",
            "风险分配",
        ],
    },
    "en": {
        PerspectiveType.PARTY_A: [
            "payment terms",
            "events of default",
            "termination rights",
            "indemnity",
            "liability allocation",
            "adverse obligations",
        ],
        PerspectiveType.PARTY_B: [
            "payment terms",
            "default remedies",
            "termination rights",
            "limitations of liability",
            "indemnity",
            "adverse obligations",
        ],
    },
}

_PERSPECTIVE_LABELS: dict[str, dict[PerspectiveType, str]] = {
    "zh": {
        PerspectiveType.PARTY_A: "甲方",
        PerspectiveType.PARTY_B: "乙方",
    },
    "en": {
        PerspectiveType.PARTY_A: "Party A",
        PerspectiveType.PARTY_B: "Party B",
    },
}

_ZH_AREA_EXPANSIONS: dict[str, list[str]] = {
    "付款条件": ["付款节点", "付款时间", "开票条件", "验收付款", "对账结算", "逾期付款"],
    "违约责任": ["违约金", "损失赔偿", "逾期责任", "补救期限", "继续履行", "违约认定"],
    "终止解除": ["合同终止", "提前解除", "单方解除", "解除条件", "自动终止", "通知期限"],
    "赔偿责任": ["赔偿范围", "赔偿上限", "间接损失", "补偿责任", "追偿", "赔偿方式"],
    "责任边界": ["责任限制", "责任上限", "免责条件", "例外责任", "不可抗力", "风险承担"],
    "风险分配": ["风险转移", "验收标准", "交付责任", "知识产权归属", "保密义务", "争议解决"],
    "免责条款": ["免责条件", "责任限制", "不可抗力", "例外情形", "责任免除", "风险自担"],
}

_ZH_LEGAL_TERMS: tuple[str, ...] = (
    "付款条件",
    "付款节点",
    "付款时间",
    "开票条件",
    "验收付款",
    "对账结算",
    "逾期付款",
    "违约责任",
    "违约金",
    "损失赔偿",
    "逾期责任",
    "补救期限",
    "继续履行",
    "违约认定",
    "合同终止",
    "提前解除",
    "单方解除",
    "解除条件",
    "自动终止",
    "通知期限",
    "赔偿责任",
    "赔偿范围",
    "赔偿上限",
    "间接损失",
    "补偿责任",
    "追偿",
    "责任边界",
    "责任限制",
    "责任上限",
    "免责条款",
    "免责条件",
    "责任免除",
    "不可抗力",
    "风险分配",
    "风险承担",
    "风险转移",
    "验收标准",
    "交付责任",
    "争议解决",
    "仲裁条款",
    "管辖法院",
    "适用法律",
    "知识产权归属",
    "保密义务",
    "交叉违约",
    "提前到期",
    "陈述与保证",
    "自动续约",
)


_GENERIC_QUERY_MARKERS_EN: tuple[str, ...] = (
    "review the contract",
    "focus on payment terms",
    "retrieve evidence-backed clauses",
    "locate clauses related to",
    "including trigger conditions",
    "liability boundaries",
    "evidence-rich wording",
    "adverse obligations",
)


def _normalize_focus_areas(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    if isinstance(raw, (list, tuple)):
        return [item.strip() for item in raw if isinstance(item, str) and item.strip()]
    return []


def _normalize_analysis_language(raw: Any) -> AnalysisLanguage:
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if normalized in {"zh", "en", "auto"}:
            return normalized  # type: ignore[return-value]
    return "auto"


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _detect_language_from_text(text: str | None) -> Literal["zh", "en"]:
    if not text:
        return "zh"
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin_chars = len(re.findall(r"[A-Za-z]", text))
    if cjk_chars >= max(8, latin_chars // 2):
        return "zh"
    return "en"


def resolve_analysis_language(
    options: dict[str, Any] | None,
    document_text: str | None = None,
) -> Literal["zh", "en"]:
    requested = _normalize_analysis_language((options or {}).get("analysis_language"))
    if requested in {"zh", "en"}:
        return requested
    return _detect_language_from_text(document_text)


def get_focus_areas_for_retrieval(
    perspective: PerspectiveType,
    options: dict[str, Any] | None,
    document_text: str | None = None,
) -> list[str]:
    focus_from_options = _normalize_focus_areas((options or {}).get("focus_areas"))
    if focus_from_options:
        return focus_from_options
    language = resolve_analysis_language(options, document_text)
    return _DEFAULT_FOCUS_BY_LANGUAGE_AND_PERSPECTIVE[language].get(perspective, [])


def _build_zh_queries(label: str, focus_areas: list[str]) -> list[str]:
    queries = [
        (
            f"从{label}视角审查合同，重点定位付款条件、违约责任、终止解除、赔偿责任、责任边界、风险分配等条款，"
            "优先召回可直接引用的原文证据，并关注法律术语明确的条款表述。"
        ),
        (
            f"{label}视角合同风险检索：付款节点、违约金、赔偿上限、单方解除、免责条件、争议解决、适用法律。"
        ),
    ]
    for area in focus_areas:
        queries.append(
            f"从{label}视角定位与“{area}”相关的合同条款，重点关注触发条件、责任边界、例外情形和可引用原文。"
        )
        expansions = _ZH_AREA_EXPANSIONS.get(area, [])
        if expansions:
            queries.append(
                f"{label}视角条款检索：{area}、" + "、".join(expansions) + "。优先命中责任限制和义务触发表述。"
            )
            queries.append(
                "在合同中查找与"
                + area
                + "有关的法律术语，包括"
                + "、".join(expansions[:4])
                + "等关键词。"
            )
    return queries


def _build_en_queries(label: str, focus_areas: list[str]) -> list[str]:
    queries: list[str] = []
    for area in focus_areas:
        normalized_area = re.sub(r"\s+", " ", area).strip()
        if not normalized_area:
            continue
        queries.extend(
            [
                f"\"{normalized_area}\"",
                f"Locate the exact clause containing \"{normalized_area}\".",
                f"From the {label} perspective, find the exact contractual wording for \"{normalized_area}\".",
                f"Find the clause title, defined term, or sentence for \"{normalized_area}\".",
            ]
        )

        upper_anchor = normalized_area.upper()
        if upper_anchor != normalized_area and len(normalized_area.split()) <= 5:
            queries.append(f"\"{upper_anchor}\"")

    queries.append(
        f"Review the contract from the {label} perspective for payment terms, default remedies, "
        "termination rights, indemnity, liability allocation, and other adverse obligations."
    )
    return queries


def _expand_query_with_llm(query: str, lang: str) -> list[str]:
    """Expand a raw query string into multiple search queries via an LLM provider.

    Provider is selected by the LLM_PROVIDER environment variable:
      - "openai" (default): calls OpenAI-compatible Chat API using OPENAI_API_KEY /
        OPENAI_BASE_URL / OPENAI_MODEL env vars.
      - "ollama": reserved for future Ollama integration.

    NOTE: The main `build_retrieval_queries(perspective, options, text)` path does NOT
    call any LLM — it uses fast local templates that already work well.  This function
    is only invoked when `build_retrieval_queries` is called with a raw string and `lang=`
    keyword, e.g. from a REST endpoint or CLI tool.

    On any failure the original query is returned as a single-element list (safe fallback).
    """
    import os

    provider = os.getenv("LLM_PROVIDER", "openai")
    logger.info("[LLM] query expansion via provider=%s", provider)

    if provider == "openai":
        try:
            from openai import OpenAI

            api_key = os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("OPENAI_BASE_URL") or None
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

            client = OpenAI(api_key=api_key, base_url=base_url)
            lang_label = "Chinese" if lang == "zh" else "English"
            system_prompt = (
                f"You are a legal contract search assistant. "
                f"Given a contract question in {lang_label}, generate 4 diverse search queries "
                f"that cover different angles of the question. "
                f"Return ONLY a JSON array of query strings, no explanation. "
                f'Example: ["query1", "query2", "query3", "query4"]'
            )
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            logger.info("[LLM] OpenAI model=%s responded", model)
            import json as _json
            content = resp.choices[0].message.content or ""
            # Extract JSON array from response
            match = re.search(r"\[.*\]", content, re.DOTALL)
            if match:
                candidates = _json.loads(match.group())
                if isinstance(candidates, list) and candidates:
                    queries = [str(q).strip() for q in candidates if str(q).strip()]
                    if queries:
                        return queries
            logger.warning("[LLM] OpenAI response did not contain a valid JSON array: %s", content[:200])
        except Exception as exc:
            logger.warning("[LLM] OpenAI query expansion failed, using fallback: %s", exc)

    elif provider == "ollama":
        logger.info("[LLM] Ollama provider not yet wired for query expansion; using fallback")

    # Safe fallback: return the original query unchanged
    return [query]


def build_retrieval_queries(
    perspective_or_query: PerspectiveType | str,
    options: dict[str, Any] | None = None,
    document_text: str | None = None,
    *,
    lang: str | None = None,
) -> list[str]:
    """Generate retrieval queries for a perspective or expand a raw query string.

    Two calling conventions:
    1. Perspective-based (existing, used by the RAG pipeline):
       ``build_retrieval_queries(PerspectiveType.PARTY_A, options, document_text)``
       → fast local template generation, no LLM involved.

    2. Raw-query expansion (new, for REST / CLI callers):
       ``build_retrieval_queries("甲方违约责任有哪些", lang="zh")``
       → optional LLM expansion via LLM_PROVIDER env var; falls back to [query].
    """
    # ── New path: raw string + lang keyword ──────────────────────────────────
    if isinstance(perspective_or_query, str) and not isinstance(perspective_or_query, PerspectiveType):
        effective_lang = lang or "zh"
        return _expand_query_with_llm(perspective_or_query, effective_lang)

    # ── Existing path: PerspectiveType ────────────────────────────────────────
    perspective: PerspectiveType = perspective_or_query  # type: ignore[assignment]
    language = resolve_analysis_language(options, document_text)
    label = _PERSPECTIVE_LABELS[language].get(perspective, perspective.value)
    focus_areas = get_focus_areas_for_retrieval(perspective, options, document_text)

    if language == "zh":
        queries = _build_zh_queries(label, focus_areas)
    else:
        queries = _build_en_queries(label, focus_areas)

    unique: list[str] = []
    seen: set[str] = set()
    for query in queries:
        if query not in seen:
            seen.add(query)
            unique.append(query)
    return unique


def _query_specificity_score(query: str) -> float:
    normalized = re.sub(r"\s+", " ", (query or "").strip())
    if not normalized:
        return float("-inf")

    lowered = normalized.lower()
    latin_words = re.findall(r"[a-z0-9_]+", lowered)
    quoted_spans = normalized.count('"') // 2 + normalized.count("'") // 2
    uppercase_anchors = re.findall(r"\b[A-Z][A-Z0-9-]{2,}\b", normalized)
    symbol_hits = len(re.findall(r"[%$0-9]", normalized))

    generic_penalty = sum(1.0 for marker in _GENERIC_QUERY_MARKERS_EN if marker in lowered)
    length_penalty = max(0, len(latin_words) - 8) * 0.18 + max(0, len(normalized) - 80) / 90.0
    short_bonus = 1.4 if len(latin_words) <= 6 else 0.0
    quote_bonus = min(2.0, quoted_spans * 1.2)
    anchor_bonus = min(1.8, len(uppercase_anchors) * 0.45) + min(0.9, symbol_hits * 0.08)
    specificity_bonus = len(set(latin_words)) / max(1, len(latin_words))

    return short_bonus + quote_bonus + anchor_bonus + specificity_bonus - generic_penalty - length_penalty


def _select_rerank_query(queries: list[str]) -> str:
    if not queries:
        return ""
    return max(queries, key=_query_specificity_score)


def _tokenize(text: str, language_hint: Literal["zh", "en"] | None = None) -> list[str]:
    normalized = re.sub(r"\s+", " ", (text or "").lower()).strip()
    if not normalized:
        return []

    if language_hint is None:
        language_hint = _detect_language_from_text(normalized)

    latin_tokens = re.findall(r"[a-z0-9_]+", normalized)
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
    tokens = list(latin_tokens)

    if language_hint == "zh":
        tokens.extend(cjk_chars)
        tokens.extend(
            cjk_chars[index] + cjk_chars[index + 1]
            for index in range(len(cjk_chars) - 1)
        )
        tokens.extend(
            cjk_chars[index] + cjk_chars[index + 1] + cjk_chars[index + 2]
            for index in range(len(cjk_chars) - 2)
        )
        for term in _ZH_LEGAL_TERMS:
            if term in normalized:
                tokens.append(term)
    else:
        tokens.extend(cjk_chars)

    return tokens


def _lexical_score(query: str, content: str) -> float:
    language_hint = _detect_language_from_text(f"{query}\n{content}")
    q_tokens = _tokenize(query, language_hint)
    c_tokens = _tokenize(content, language_hint)
    if not q_tokens or not c_tokens:
        return 0.0

    q_counter = Counter(q_tokens)
    c_counter = Counter(c_tokens)
    doc_len = sum(c_counter.values())
    avgdl = max(1.0, doc_len)
    k1 = 1.5
    b = 0.75
    overlap = 0.0

    for token, q_tf in q_counter.items():
        c_tf = c_counter.get(token, 0)
        if c_tf <= 0:
            continue
        tf_sat = (c_tf * (k1 + 1.0)) / (c_tf + k1 * (1.0 - b + b * (doc_len / avgdl)))
        token_boost = 1.0 + math.log1p(q_tf)
        overlap += tf_sat * token_boost

    phrase_boost = 0.0
    if language_hint == "zh":
        compact_query = "".join(re.findall(r"[\u4e00-\u9fff]+", query))
        compact_content = "".join(re.findall(r"[\u4e00-\u9fff]+", content))
        if compact_query and compact_query in compact_content:
            phrase_boost += 0.45
        matched_terms = sum(1 for term in _ZH_LEGAL_TERMS if term in query and term in content)
        if matched_terms:
            phrase_boost += min(0.45, 0.12 * matched_terms)
    else:
        query_norm = " ".join(q_tokens)
        if query_norm and query_norm in " ".join(c_tokens):
            phrase_boost += 0.35

    denom = math.sqrt(sum(value * value for value in q_counter.values())) * math.sqrt(
        sum(value * value for value in c_counter.values())
    )
    if denom <= 0:
        return 0.0

    length_penalty = 1.0 + math.log1p(max(0, doc_len - len(q_tokens)))
    return (overlap / denom) / length_penalty + phrase_boost


def _filter_min_chars_for_content(content: str) -> int:
    base_threshold = get_retrieval_filter_min_chars()
    if _contains_cjk(content):
        return max(36, min(base_threshold, 48))
    return base_threshold


def _looks_like_low_value_chunk(content: str) -> bool:
    normalized = re.sub(r"\s+", " ", (content or "")).strip()
    if len(normalized) < _filter_min_chars_for_content(normalized):
        return True

    uppercase_ratio = 0.0
    letters = [char for char in normalized if char.isalpha()]
    if letters:
        uppercase_ratio = sum(1 for char in letters if char.isupper()) / len(letters)

    dotted_leader = normalized.count("....") >= 1 or normalized.count(" . ") >= 3
    toc_like = (
        "table of contents" in normalized.lower()
        or "目录" in normalized
        or normalized.lower().startswith("contents")
        or dotted_leader
        or re.search(r"\.{4,}\s*\d+\s*$", normalized) is not None
    )
    title_like = len(normalized) <= 140 and uppercase_ratio > 0.8
    return toc_like or title_like


def _filter_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    return [chunk for chunk in chunks if not _looks_like_low_value_chunk(chunk.content)]


def _compute_per_query_k(final_k: int, query_count: int) -> int:
    query_count = max(1, query_count)
    coarse_mult = max(2, get_coarse_recall_mult())
    raw = (final_k * coarse_mult + query_count - 1) // query_count
    return max(final_k, min(get_coarse_recall_max_per_query(), raw))


def _merge_ranked_lists(rankings: list[tuple[str, list[RetrievedChunk]]], top_k: int) -> list[RetrievedChunk]:
    if not rankings:
        return []

    rrf_k = max(1, get_hybrid_rrf_k())
    fused: dict[str, RetrievedChunk] = {}
    fused_scores: dict[str, float] = {}

    for method, ranked in rankings:
        for rank, chunk in enumerate(ranked, start=1):
            score = 1.0 / (rrf_k + rank)
            if chunk.chunk_id not in fused:
                fused[chunk.chunk_id] = chunk.model_copy(deep=True)
                fused[chunk.chunk_id].retrieval_methods = []
                fused[chunk.chunk_id].score_breakdown = {}
            target = fused[chunk.chunk_id]
            if method not in target.retrieval_methods:
                target.retrieval_methods.append(method)
            target.score_breakdown[method] = round(float(chunk.score), 6)
            fused_scores[chunk.chunk_id] = fused_scores.get(chunk.chunk_id, 0.0) + score
            target.score = fused_scores[chunk.chunk_id]

    ordered = sorted(fused.values(), key=lambda item: item.score, reverse=True)
    return ordered[:top_k]


async def retrieve_contexts(
    *,
    document_id: UUID,
    session_id: str,
    query: str,
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    k = top_k or get_retriever_top_k()
    query_vec = embed_query_text(query)
    chunks = await search(
        document_id=document_id,
        session_id=session_id,
        query_embedding=query_vec,
        top_k=k,
    )
    for chunk in chunks:
        chunk.retrieval_methods = ["dense"]
        chunk.score_breakdown = {"dense": round(float(chunk.score), 6)}
    return chunks


async def retrieve_contexts_lexical(
    *,
    query: str,
    document_text: str | None,
    document: Document | None,
    top_k: int,
) -> list[RetrievedChunk]:
    ranked: list[RetrievedChunk] = []
    text_chunks = chunk_document(document) if document is not None else chunk_text(document_text or "")
    for text_chunk in text_chunks:
        score = _lexical_score(query, text_chunk.content)
        if score <= 0:
            continue
        ranked.append(
            RetrievedChunk(
                chunk_id=text_chunk.chunk_id,
                content=text_chunk.content,
                score=score,
                metadata={"start": text_chunk.start, "end": text_chunk.end},
                retrieval_methods=["lexical"],
                score_breakdown={"lexical": round(score, 6)},
            )
        )
    ranked.sort(key=lambda item: item.score, reverse=True)
    return _filter_chunks(ranked)[:top_k]


async def retrieve_ranked_chunks(
    *,
    document_id: UUID,
    session_id: str,
    queries: list[str],
    document_text: str | None,
    document: Document | None = None,
    final_top_k: int,
    method: str = "hybrid",
    rerank_enabled: bool | None = None,
    rerank_pool_mult: int | None = None,
    enable_lang_routing: bool = True,
) -> list[RetrievedChunk]:
    """Multi-query retrieval with optional language-aware branch routing.

    When *enable_lang_routing* is True and *method* is 'hybrid', Chinese queries
    are routed to the dense-only branch (lexical is skipped).  This avoids BM25
    noise on a Chinese embedding space where dense already dominates.
    """
    if not queries:
        return []

    per_query_k = _compute_per_query_k(final_top_k, len(queries))
    rankings: list[tuple[str, list[RetrievedChunk]]] = []

    for query in queries:
        # Language routing: ZH queries skip the noisy lexical branch.
        effective_method = method
        if enable_lang_routing and method == "hybrid":
            if detect_language(query) == "zh":
                effective_method = "dense"

        if effective_method in {"dense", "hybrid"}:
            dense_chunks = await retrieve_contexts(
                document_id=document_id,
                session_id=session_id,
                query=query,
                top_k=per_query_k,
            )
            rankings.append(("dense", _filter_chunks(dense_chunks)))

        if effective_method in {"lexical", "hybrid"} and document_text:
            lexical_chunks = await retrieve_contexts_lexical(
                query=query,
                document_text=document_text,
                document=document,
                top_k=per_query_k,
            )
            rankings.append(("lexical", lexical_chunks))

    if not rankings:
        return []

    pool_mult = max(1, rerank_pool_mult if rerank_pool_mult is not None else get_rerank_pool_mult())
    pool_limit = max(final_top_k, final_top_k * pool_mult)
    merged = _merge_ranked_lists(rankings, pool_limit)
    pool = _filter_chunks(merged[:pool_limit])

    should_rerank = True if rerank_enabled is None else rerank_enabled
    if should_rerank and pool:
        rerank_query = _select_rerank_query(queries)
        pool = await asyncio.to_thread(rerank_retrieved_chunks, rerank_query, pool)
        for chunk in pool:
            chunk.score_breakdown["rerank"] = round(float(chunk.score), 6)
            if "rerank" not in chunk.retrieval_methods:
                chunk.retrieval_methods.append("rerank")
        pool = _filter_chunks(pool)

    return pool[:final_top_k]


async def retrieve_contexts_merged(
    *,
    document_id: UUID,
    session_id: str,
    perspective: PerspectiveType,
    options: dict[str, Any] | None = None,
    final_top_k: int | None = None,
    document_text: str | None = None,
    document: Document | None = None,
) -> list[RetrievedChunk]:
    """Multi-query hybrid retrieval with language-aware query branching."""

    final_k = final_top_k or get_retriever_top_k()
    effective_document_text = document.text_content if document is not None else document_text
    queries = build_retrieval_queries(perspective, options, effective_document_text)
    method = "hybrid" if effective_document_text else "dense"
    result = await retrieve_ranked_chunks(
        document_id=document_id,
        session_id=session_id,
        queries=queries,
        document_text=effective_document_text,
        document=document,
        final_top_k=final_k,
        method=method,
    )
    logger.debug(
        "[RAG] retrieval branch=%s queries=%d results=%d method=%s",
        resolve_analysis_language(options, effective_document_text),
        len(queries),
        len(result),
        method,
    )
    return result
