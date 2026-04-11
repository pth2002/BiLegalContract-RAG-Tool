"""Offline retrieval benchmark for chunking / retrieval strategy / rerank experiments.

This tool does not change the main application logic. It reuses the existing
indexing, retrieval, reranking, and config modules with temporary env-based
overrides, then writes a Markdown + JSON report for interview-ready evidence.

Usage examples (from backend/):
  python -m src.tooling.run_retrieval_benchmark
  python -m src.tooling.run_retrieval_benchmark --cases data/retrieval_benchmark_cases.json
  python -m src.tooling.run_retrieval_benchmark --chunk-configs 160:40,240:60,320:80
  python -m src.tooling.run_retrieval_benchmark --methods dense,lexical,hybrid
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from ..config import get_config
from ..models import Document, FileType, PerspectiveType, RetrievedChunk
from ..services.chunking_service import chunk_document
from ..services.indexing_service import index_document
from ..services.parser_service import FileValidationError, parse_document_result, parse_pdf_result
from ..services.retrieval_eval_service import hit_rate_at_k, mrr, recall_at_k
from ..services.retrieval_service import (
    build_retrieval_queries,
    retrieve_ranked_chunks,
)
from ..services import vector_store_service
from ..services.vector_store_service import delete_chunks_for_document, init_vector_store

logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize(text: str) -> str:
    return "".join((text or "").lower().split())


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


@contextmanager
def _temporary_env(overrides: dict[str, str]) -> Any:
    old_values = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            os.environ[key] = str(value)
        get_config.cache_clear()
        yield
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_config.cache_clear()


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    document: Document
    perspective: PerspectiveType
    options: dict[str, Any] | None
    evidence_snippets: list[str]
    queries: list[str] | None
    tags: tuple[str, ...] = ()


def _load_document(case: dict[str, Any], repo_root: Path, default_session: str) -> Document:
    path = (repo_root / case["file"]).resolve()
    if path.suffix.lower() in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8")
        count = max(1, len([line for line in text.splitlines() if line.strip()]))
        raw = text.encode("utf-8")
        document = Document(
            id=UUID(case["document_id"]),
            filename=path.name,
            file_type=FileType.DOCX,
            file_size=len(raw),
            page_count=count,
            text_content=text,
            session_id=case.get("session_id") or default_session,
        )
        return document
    else:
        raw = path.read_bytes()
        try:
            parsed = parse_document_result(raw, path.name)
        except FileValidationError:
            # Benchmark-only fallback: allow oversized PDFs so we can evaluate
            # long-contract retrieval behavior without changing production limits.
            if path.suffix.lower() != ".pdf":
                raise
            parsed = parse_pdf_result(raw)
    return Document(
        id=UUID(case["document_id"]),
        filename=path.name,
        file_type=parsed.file_type,
        file_size=len(raw),
        page_count=parsed.count,
        text_content=parsed.text_content,
        page_summaries=parsed.page_summaries,
        content_blocks=parsed.content_blocks,
        parse_summary=parsed.parse_summary,
        document_profile=parsed.document_profile,
        session_id=case.get("session_id") or default_session,
    )


def _load_cases(cases_path: Path, repo_root: Path) -> tuple[list[BenchmarkCase], dict[str, Any]]:
    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    defaults = payload.get("defaults") or {}
    session_id = defaults.get("session_id") or "retrieval_benchmark_session"

    cases: list[BenchmarkCase] = []
    for raw_case in payload.get("cases") or []:
        document = _load_document(raw_case, repo_root, session_id)
        cases.append(
            BenchmarkCase(
                case_id=str(raw_case["id"]),
                document=document,
                perspective=PerspectiveType(raw_case["perspective"]),
                options=raw_case.get("options"),
                evidence_snippets=[str(x) for x in (raw_case.get("evidence_snippets") or []) if str(x).strip()],
                queries=[str(x) for x in (raw_case.get("queries") or []) if str(x).strip()] or None,
                tags=tuple(raw_case.get("tags") or []),
            )
        )
    return cases, defaults


def _resolve_gold_chunk_ids(document: Document, evidence_snippets: list[str]) -> set[str]:
    chunks = chunk_document(document)
    normalized_chunks = {chunk.chunk_id: _normalize(chunk.content) for chunk in chunks}
    relevant: set[str] = set()

    for snippet in evidence_snippets:
        needle = _normalize(snippet)
        if not needle:
            continue
        matched = False
        for chunk_id, normalized_content in normalized_chunks.items():
            if needle in normalized_content:
                relevant.add(chunk_id)
                matched = True
        if not matched:
            logger.warning("[BENCH] snippet not matched to any chunk: %s", snippet)
    return relevant


def _chunk_numeric_id(chunk_id: str) -> int | None:
    try:
        if not chunk_id.startswith("chunk_"):
            return None
        return int(chunk_id.split("_", 1)[1])
    except Exception:
        return None


def _expand_relaxed_chunk_ids(relevant_ids: set[str], window: int = 1) -> set[str]:
    expanded = set(relevant_ids)
    for chunk_id in relevant_ids:
        numeric = _chunk_numeric_id(chunk_id)
        if numeric is None:
            continue
        for offset in range(-window, window + 1):
            expanded.add(f"chunk_{numeric + offset:04d}")
    return expanded


# ---------------------------------------------------------------------------
# Additional evaluation criteria
# ---------------------------------------------------------------------------

def _normalize_for_text_match(text: str) -> str:
    """Lowercase + strip all non-word characters (punctuation, whitespace).

    CJK characters are kept because Python's \\w matches Unicode word chars.
    """
    return re.sub(r"\W", "", (text or "").lower(), flags=re.UNICODE)


def _lcs_length(a: str, b: str, max_len: int = 2000) -> int:
    """Longest common *substring* length via 1-D rolling DP.

    Inputs are capped at *max_len* characters to bound worst-case O(n²) cost.
    """
    a, b = a[:max_len], b[:max_len]
    if not a or not b:
        return 0
    m, n = len(a), len(b)
    best = 0
    dp = [0] * (n + 1)
    for i in range(1, m + 1):
        prev = 0
        for j in range(1, n + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev + 1
                if dp[j] > best:
                    best = dp[j]
            else:
                dp[j] = 0
            prev = temp
    return best


def evaluate_case_neighbor(
    retrieved_ids: list[str],
    gold_ids: set[str],
    ks: list[int],
) -> dict[str, Any]:
    """Compute neighbor (±1 chunk) hit metrics for one benchmark case.

    Denominator = |gold_ids| (unchanged from strict).
    A gold chunk g is "covered" if any retrieved chunk r satisfies
    |numeric(r) - numeric(g)| <= 1.  The gold set itself is never expanded,
    so Neighbor Recall >= Strict Recall is guaranteed.
    """
    if not gold_ids:
        result: dict[str, Any] = {"mrr": 1.0}
        for k in ks:
            result[f"recall@{k}"] = 1.0
            result[f"hit@{k}"] = 1.0
        return result

    gold_numeric: dict[str, int | None] = {g: _chunk_numeric_id(g) for g in gold_ids}
    retrieved_numeric: list[int | None] = [_chunk_numeric_id(r) for r in retrieved_ids]

    def _covered_at_k(k: int) -> set[str]:
        top_numeric = [n for n in retrieved_numeric[:k] if n is not None]
        top_exact = set(retrieved_ids[:k])
        covered: set[str] = set()
        for g, gn in gold_numeric.items():
            if gn is None:
                if g in top_exact:
                    covered.add(g)
            else:
                if any(abs(rn - gn) <= 1 for rn in top_numeric):
                    covered.add(g)
        return covered

    # MRR: rank of first retrieved chunk that neighbor-hits any gold
    first_hit_rank: int | None = None
    for rank, (rid, rn) in enumerate(zip(retrieved_ids, retrieved_numeric), start=1):
        hit = False
        if rn is None:
            hit = rid in gold_ids
        else:
            hit = any(
                gn is not None and abs(rn - gn) <= 1
                for gn in gold_numeric.values()
            )
        if hit:
            first_hit_rank = rank
            break

    total = len(gold_ids)
    result = {"mrr": (1.0 / first_hit_rank) if first_hit_rank else 0.0}
    for k in ks:
        covered = _covered_at_k(k)
        result[f"recall@{k}"] = len(covered) / total
        result[f"hit@{k}"] = 1.0 if covered else 0.0
    return result


def evaluate_case_text_match(
    retrieved_chunks: list[RetrievedChunk],
    evidence_snippets: list[str],
    ks: list[int],
    threshold: float = 0.6,
) -> dict[str, Any]:
    """Compute evidence text-match metrics for one benchmark case.

    A retrieved chunk is a hit for snippet S when:
        LCS(normalize(chunk), normalize(S)) / len(normalize(S)) >= threshold

    Recall@K = |snippets covered by ≥1 top-K chunk| / |total snippets|
    MRR      = 1 / rank of the first chunk that covers any snippet.
    """
    normed_snippets = [_normalize_for_text_match(s) for s in evidence_snippets]
    normed_snippets = [s for s in normed_snippets if s]
    total = len(normed_snippets)
    if total == 0:
        result: dict[str, Any] = {"mrr": 1.0}
        for k in ks:
            result[f"recall@{k}"] = 1.0
            result[f"hit@{k}"] = 1.0
        return result

    def _covered(content: str) -> set[int]:
        nc = _normalize_for_text_match(content)
        return {
            i for i, ns in enumerate(normed_snippets)
            if _lcs_length(nc, ns) / len(ns) >= threshold
        }

    coverages = [_covered(c.content) for c in retrieved_chunks]

    first_hit_rank: int | None = None
    for rank, cov in enumerate(coverages, start=1):
        if cov:
            first_hit_rank = rank
            break

    result = {"mrr": (1.0 / first_hit_rank) if first_hit_rank else 0.0}
    for k in ks:
        covered_at_k: set[int] = set()
        for cov in coverages[:k]:
            covered_at_k |= cov
        result[f"recall@{k}"] = len(covered_at_k) / total
        result[f"hit@{k}"] = 1.0 if covered_at_k else 0.0
    return result


# ---------------------------------------------------------------------------
# Retrieval helpers
# ---------------------------------------------------------------------------

async def _retrieve_ranked(
    *,
    document: Document,
    perspective: PerspectiveType,
    options: dict[str, Any] | None,
    queries_override: list[str] | None,
    method: str,
    final_top_k: int,
    rerank_enabled: bool,
    rerank_pool_mult: int,
    lang_routing: bool = True,
) -> list[RetrievedChunk]:
    queries = queries_override or build_retrieval_queries(perspective, options, document.text_content)
    if not queries:
        return []

    return await retrieve_ranked_chunks(
        document_id=document.id,
        session_id=document.session_id,
        queries=queries,
        document_text=document.text_content,
        document=document,
        final_top_k=final_top_k,
        method=method,
        rerank_enabled=rerank_enabled,
        rerank_pool_mult=rerank_pool_mult,
        enable_lang_routing=lang_routing,
    )


async def _index_documents(documents: list[Document]) -> dict[str, Any]:
    await init_vector_store()
    details: list[dict[str, Any]] = []
    total_ms = 0.0
    chunk_counts: list[int] = []

    for document in documents:
        await delete_chunks_for_document(document.id)
        started = time.perf_counter()
        chunk_count = await index_document(document)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        total_ms += elapsed_ms
        chunk_counts.append(chunk_count)
        details.append(
            {
                "document_id": str(document.id),
                "filename": document.filename,
                "chunk_count": chunk_count,
                "index_ms": round(elapsed_ms, 2),
            }
        )

    return {
        "backend": vector_store_service._BACKEND or "unknown",
        "documents": details,
        "avg_chunk_count": round(_mean(chunk_counts), 2),
        "total_index_ms": round(total_ms, 2),
        "avg_index_ms": round(_mean([d["index_ms"] for d in details]), 2) if details else 0.0,
    }


async def _evaluate_cases(
    *,
    cases: list[BenchmarkCase],
    method: str,
    final_top_k: int,
    ks: list[int],
    rerank_enabled: bool,
    rerank_pool_mult: int,
    lang_routing: bool = True,
) -> dict[str, Any]:
    per_case: list[dict[str, Any]] = []

    # --- strict chunk_id match ---
    macro_recall: dict[int, list[float]] = {k: [] for k in ks}
    macro_hit: dict[int, list[float]] = {k: [] for k in ks}
    macro_mrr: list[float] = []

    # --- neighbor match (±1) ---
    macro_nbr_recall: dict[int, list[float]] = {k: [] for k in ks}
    macro_nbr_hit: dict[int, list[float]] = {k: [] for k in ks}
    macro_nbr_mrr: list[float] = []

    # --- evidence text match ---
    macro_tm_recall: dict[int, list[float]] = {k: [] for k in ks}
    macro_tm_hit: dict[int, list[float]] = {k: [] for k in ks}
    macro_tm_mrr: list[float] = []

    query_times_ms: list[float] = []

    # Per-group accumulators (strict / neighbor / text-match)
    group_recall: dict[str, dict[int, list[float]]] = {}
    group_hit: dict[str, dict[int, list[float]]] = {}
    group_mrr: dict[str, list[float]] = {}
    group_nbr_recall: dict[str, dict[int, list[float]]] = {}
    group_nbr_hit: dict[str, dict[int, list[float]]] = {}
    group_nbr_mrr: dict[str, list[float]] = {}
    group_tm_recall: dict[str, dict[int, list[float]]] = {}
    group_tm_hit: dict[str, dict[int, list[float]]] = {}
    group_tm_mrr: dict[str, list[float]] = {}
    group_counts: dict[str, int] = {}

    for case in cases:
        group = case.tags[0] if case.tags else "other"
        if group not in group_recall:
            group_recall[group] = {k: [] for k in ks}
            group_hit[group] = {k: [] for k in ks}
            group_mrr[group] = []
            group_nbr_recall[group] = {k: [] for k in ks}
            group_nbr_hit[group] = {k: [] for k in ks}
            group_nbr_mrr[group] = []
            group_tm_recall[group] = {k: [] for k in ks}
            group_tm_hit[group] = {k: [] for k in ks}
            group_tm_mrr[group] = []
            group_counts[group] = 0

        relevant_ids = _resolve_gold_chunk_ids(case.document, case.evidence_snippets)

        started = time.perf_counter()
        retrieved = await _retrieve_ranked(
            document=case.document,
            perspective=case.perspective,
            options=case.options,
            queries_override=case.queries,
            method=method,
            final_top_k=final_top_k,
            rerank_enabled=rerank_enabled,
            rerank_pool_mult=rerank_pool_mult,
            lang_routing=lang_routing,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        query_times_ms.append(elapsed_ms)

        ordered_ids = [chunk.chunk_id for chunk in retrieved]

        # Strict
        case_mrr = mrr(ordered_ids, relevant_ids)
        macro_mrr.append(case_mrr)
        group_mrr[group].append(case_mrr)

        # Neighbor
        nbr = evaluate_case_neighbor(ordered_ids, relevant_ids, ks)
        macro_nbr_mrr.append(nbr["mrr"])
        group_nbr_mrr[group].append(nbr["mrr"])

        # Text match
        tm = evaluate_case_text_match(retrieved, case.evidence_snippets, ks)
        macro_tm_mrr.append(tm["mrr"])
        group_tm_mrr[group].append(tm["mrr"])

        group_counts[group] += 1

        per_k: dict[str, dict[str, float]] = {}
        for k in ks:
            recall = recall_at_k(ordered_ids, relevant_ids, k)
            hit = hit_rate_at_k(ordered_ids, relevant_ids, k)
            nbr_r = float(nbr[f"recall@{k}"])
            nbr_h = float(nbr[f"hit@{k}"])
            tm_r = float(tm[f"recall@{k}"])
            tm_h = float(tm[f"hit@{k}"])

            macro_recall[k].append(recall)
            macro_hit[k].append(hit)
            macro_nbr_recall[k].append(nbr_r)
            macro_nbr_hit[k].append(nbr_h)
            macro_tm_recall[k].append(tm_r)
            macro_tm_hit[k].append(tm_h)

            group_recall[group][k].append(recall)
            group_hit[group][k].append(hit)
            group_nbr_recall[group][k].append(nbr_r)
            group_nbr_hit[group][k].append(nbr_h)
            group_tm_recall[group][k].append(tm_r)
            group_tm_hit[group][k].append(tm_h)

            per_k[str(k)] = {
                "recall": round(recall, 6),
                "hit": round(hit, 6),
                "neighbor_recall": round(nbr_r, 6),
                "neighbor_hit": round(nbr_h, 6),
                "text_match_recall": round(tm_r, 6),
                "text_match_hit": round(tm_h, 6),
            }

        per_case.append(
            {
                "case_id": case.case_id,
                "document": case.document.filename,
                "perspective": case.perspective.value,
                "tags": list(case.tags),
                "relevant_chunk_ids": sorted(relevant_ids),
                "retrieved_ids": ordered_ids,
                "mrr": round(case_mrr, 6),
                "neighbor_mrr": round(float(nbr["mrr"]), 6),
                "text_match_mrr": round(float(tm["mrr"]), 6),
                "latency_ms": round(elapsed_ms, 2),
                "per_k": per_k,
            }
        )

    def _build_by_group(
        g_recall: dict[str, dict[int, list[float]]],
        g_hit: dict[str, dict[int, list[float]]],
        g_mrr: dict[str, list[float]],
    ) -> dict[str, dict[str, Any]]:
        return {
            group: {
                "case_count": group_counts[group],
                "mrr": round(_mean(g_mrr[group]), 6),
                **{f"recall@{k}": round(_mean(g_recall[group][k]), 6) for k in ks},
                **{f"hit@{k}": round(_mean(g_hit[group][k]), 6) for k in ks},
            }
            for group in sorted(g_recall)
        }

    by_group = _build_by_group(group_recall, group_hit, group_mrr)
    by_group_neighbor = _build_by_group(group_nbr_recall, group_nbr_hit, group_nbr_mrr)
    by_group_text_match = _build_by_group(group_tm_recall, group_tm_hit, group_tm_mrr)

    sorted_times = sorted(query_times_ms)
    n = len(sorted_times)
    p50 = sorted_times[n // 2] if n else 0.0
    p95 = sorted_times[min(int(n * 0.95), n - 1)] if n else 0.0

    macro: dict[str, Any] = (
        {f"recall@{k}": round(_mean(v), 6) for k, v in macro_recall.items()}
        | {f"hit@{k}": round(_mean(v), 6) for k, v in macro_hit.items()}
        | {f"neighbor_recall@{k}": round(_mean(v), 6) for k, v in macro_nbr_recall.items()}
        | {f"neighbor_hit@{k}": round(_mean(v), 6) for k, v in macro_nbr_hit.items()}
        | {f"text_match_recall@{k}": round(_mean(v), 6) for k, v in macro_tm_recall.items()}
        | {f"text_match_hit@{k}": round(_mean(v), 6) for k, v in macro_tm_hit.items()}
        | {
            "mrr": round(_mean(macro_mrr), 6),
            "neighbor_mrr": round(_mean(macro_nbr_mrr), 6),
            "text_match_mrr": round(_mean(macro_tm_mrr), 6),
            "avg_latency_ms": round(_mean(query_times_ms), 2),
            "latency_p50_ms": round(p50, 2),
            "latency_p95_ms": round(p95, 2),
        }
    )

    return {
        "method": method,
        "rerank_enabled": rerank_enabled,
        "rerank_pool_mult": rerank_pool_mult,
        "per_case": per_case,
        "macro": macro,
        "by_group": by_group,
        "by_group_neighbor": by_group_neighbor,
        "by_group_text_match": by_group_text_match,
    }


def _parse_chunk_configs(raw: str | None) -> list[tuple[int, int]]:
    if not raw:
        return [(160, 40), (240, 60), (320, 80), (480, 120), (900, 150)]
    configs: list[tuple[int, int]] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        size_s, overlap_s = item.split(":")
        configs.append((int(size_s), int(overlap_s)))
    return configs


def _parse_int_list(raw: str | None, default: list[int]) -> list[int]:
    if not raw:
        return default
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_str_list(raw: str | None, default: list[str]) -> list[str]:
    if not raw:
        return default
    return [x.strip() for x in raw.split(",") if x.strip()]


def _render_group_table(
    by_group: dict[str, Any],
    lines: list[str],
    title: str,
) -> None:
    lines.append(f"### {title}")
    lines.append("")
    lines.append("| Group | Cases | Recall@1 | Recall@3 | Recall@5 | MRR | Hit@5 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for group, stats in sorted(by_group.items()):
        lines.append(
            f"| {group} | {stats['case_count']} | "
            f"{stats.get('recall@1', 0):.4f} | {stats.get('recall@3', 0):.4f} | "
            f"{stats.get('recall@5', 0):.4f} | "
            f"{stats.get('mrr', 0):.4f} | {stats.get('hit@5', 0):.4f} |"
        )
    lines.append("")


def _render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Retrieval Benchmark Report")
    lines.append("")
    lines.append("## Run Summary")
    lines.append("")
    lines.append(f"- Cases: {report['meta']['case_count']}")
    lines.append(f"- Top-K metrics: {report['meta']['top_ks']}")
    lines.append(f"- Final top-k: {report['meta']['final_top_k']}")
    lines.append(f"- Current vector backend: {report['meta']['vector_backend']}")
    if report["meta"].get("method_base_chunk"):
        base = report["meta"]["method_base_chunk"]
        lines.append(f"- Method comparison base chunk: {base['chunk_size']} / {base['overlap']}")
    lines.append("")

    lines.append("## Chunk Strategy")
    lines.append("")
    lines.append("| Chunk Size | Overlap | Avg Chunks / Doc | Avg Index ms | Recall@1 | Recall@3 | Recall@5 | Neighbor Recall@5 | MRR | P50 ms | Hit@5 |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in report["chunk_strategy"]:
        macro = row["eval"]["macro"]
        lines.append(
            f"| {row['chunk_size']} | {row['overlap']} | {row['index']['avg_chunk_count']} | "
            f"{row['index']['avg_index_ms']} | {macro.get('recall@1', 0):.4f} | "
            f"{macro.get('recall@3', 0):.4f} | {macro.get('recall@5', 0):.4f} | "
            f"{macro.get('neighbor_recall@5', 0):.4f} | {macro.get('mrr', 0):.4f} | "
            f"{macro.get('latency_p50_ms', 0):.1f} | {macro.get('hit@5', 0):.4f} |"
        )
    lines.append("")

    lines.append("## Retrieval Method Comparison")
    lines.append("")
    lines.append("| Method | Rerank | Pool Mult | Avg ms | P50 ms | P95 ms | Recall@5 | Neighbor Recall@5 | Text Match Recall@5 | MRR | Neighbor MRR | Text Match MRR | Hit@5 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in report["retrieval_methods"]:
        macro = row["macro"]
        lines.append(
            f"| {row['method']} | {'on' if row['rerank_enabled'] else 'off'} | {row['rerank_pool_mult']} | "
            f"{macro['avg_latency_ms']:.1f} | {macro.get('latency_p50_ms', 0):.1f} | {macro.get('latency_p95_ms', 0):.1f} | "
            f"{macro.get('recall@5', 0):.4f} | {macro.get('neighbor_recall@5', 0):.4f} | "
            f"{macro.get('text_match_recall@5', 0):.4f} | "
            f"{macro.get('mrr', 0):.4f} | {macro.get('neighbor_mrr', 0):.4f} | "
            f"{macro.get('text_match_mrr', 0):.4f} | {macro.get('hit@5', 0):.4f} |"
        )
    lines.append("")

    lines.append("## Rerank Pool Size")
    lines.append("")
    lines.append("| Pool Mult | Avg ms | P50 ms | P95 ms | Recall@5 | Neighbor Recall@5 | Text Match Recall@5 | MRR | Hit@5 |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in report["rerank_pool"]:
        macro = row["macro"]
        lines.append(
            f"| {row['rerank_pool_mult']} | {macro['avg_latency_ms']:.1f} | "
            f"{macro.get('latency_p50_ms', 0):.1f} | {macro.get('latency_p95_ms', 0):.1f} | "
            f"{macro.get('recall@5', 0):.4f} | {macro.get('neighbor_recall@5', 0):.4f} | "
            f"{macro.get('text_match_recall@5', 0):.4f} | "
            f"{macro.get('mrr', 0):.4f} | {macro.get('hit@5', 0):.4f} |"
        )
    lines.append("")

    if report.get("final_top_k_sweep"):
        lines.append("## Final Top-K Comparison")
        lines.append("")
        lines.append("| Final Top-K | Avg ms | P50 ms | P95 ms | Recall@5 | Neighbor Recall@5 | Text Match Recall@5 | MRR | Hit@5 |")
        lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for row in report["final_top_k_sweep"]:
            macro = row["macro"]
            lines.append(
                f"| {row.get('final_top_k', '?')} | {macro['avg_latency_ms']:.1f} | "
                f"{macro.get('latency_p50_ms', 0):.1f} | {macro.get('latency_p95_ms', 0):.1f} | "
                f"{macro.get('recall@5', 0):.4f} | {macro.get('neighbor_recall@5', 0):.4f} | "
                f"{macro.get('text_match_recall@5', 0):.4f} | "
                f"{macro.get('mrr', 0):.4f} | {macro.get('hit@5', 0):.4f} |"
            )
        lines.append("")

    # Per-group stats with three labelled sections
    method_rows = report.get("retrieval_methods") or []
    if method_rows:
        best_row = next((r for r in method_rows if r["method"] == "hybrid"), method_rows[-1])

        lines.append("## Results by Document Group")
        lines.append("")
        lines.append(
            "> Three evaluation criteria are shown below. "
            "**Strict** requires exact chunk_id match. "
            "**Neighbor** also accepts the immediately adjacent chunks (±1). "
            "**Text Match** checks whether the retrieved chunk text covers ≥60% of the evidence snippet "
            "(longest common substring / snippet length)."
        )
        lines.append("")

        for section_key, section_title in [
            ("by_group", "Strict chunk_id Match"),
            ("by_group_neighbor", "Neighbor Match (±1)"),
            ("by_group_text_match", "Evidence Text Match"),
        ]:
            by_group = best_row.get(section_key) or {}
            if by_group:
                _render_group_table(by_group, lines, section_title)

    lines.append("## Notes")
    lines.append("")
    lines.append("- **Strict**: gold labels are evidence snippets remapped to exact chunk_ids.")
    lines.append("- **Neighbor**: immediately adjacent chunk_ids (±1) are also accepted.")
    lines.append("- **Text Match**: a chunk hits a snippet when LCS(normalize(chunk), normalize(snippet)) / len(snippet) ≥ 0.6.")
    lines.append("- MRR (Mean Reciprocal Rank) = 1/rank of the first relevant chunk under each criterion.")
    lines.append("- Retrieval uses current project logic: multi-query, dense/lexical fusion, optional rerank.")
    lines.append("- This benchmark does not change production behavior; it only adds offline evaluation tooling.")
    lines.append("")
    return "\n".join(lines)


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = _repo_root().parent
    cases_path = (Path(args.cases) if args.cases else repo_root / "backend" / "data" / "retrieval_benchmark_cases.json").resolve()
    cases, defaults = _load_cases(cases_path, repo_root)
    top_ks = _parse_int_list(args.top_ks, defaults.get("top_ks") or [1, 3, 5])
    final_top_k = int(args.final_top_k or defaults.get("final_top_k") or 8)
    chunk_configs = _parse_chunk_configs(args.chunk_configs)
    methods = _parse_str_list(args.methods, ["dense", "lexical", "hybrid"])
    rerank_pool_mults = _parse_int_list(args.rerank_pool_mults, [1, 2, 4])
    final_top_k_values = _parse_int_list(getattr(args, "final_top_ks", None), [3, 5, 8, 12, 16])
    lang_routing: bool = not getattr(args, "no_lang_routing", False)

    if not cases:
        raise ValueError("No benchmark cases loaded.")

    report: dict[str, Any] = {
        "meta": {
            "cases_file": str(cases_path),
            "case_count": len(cases),
            "top_ks": top_ks,
            "final_top_k": final_top_k,
            "lang_routing": lang_routing,
        },
        "chunk_strategy": [],
        "retrieval_methods": [],
        "rerank_pool": [],
        "final_top_k_sweep": [],
    }

    unique_documents = list({case.document.id: case.document for case in cases}.values())

    # Chunk strategy benchmark
    for chunk_size, overlap in chunk_configs:
        overrides = {
            "CHUNK_SIZE_CHARS": str(chunk_size),
            "CHUNK_OVERLAP_CHARS": str(overlap),
            "RERANK_POOL_MULT": "4",
            "RETRIEVER_TOP_K": str(final_top_k),
        }
        with _temporary_env(overrides):
            index_stats = await _index_documents(unique_documents)
            evaluation = await _evaluate_cases(
                cases=cases,
                method="hybrid",
                final_top_k=final_top_k,
                ks=top_ks,
                rerank_enabled=True,
                rerank_pool_mult=4,
                lang_routing=lang_routing,
            )
            report["chunk_strategy"].append(
                {
                    "chunk_size": chunk_size,
                    "overlap": overlap,
                    "index": index_stats,
                    "eval": evaluation,
                }
            )

    meaningful_chunk_rows = [
        row for row in report["chunk_strategy"] if float(row["index"]["avg_chunk_count"]) >= 2.0
    ] or list(report["chunk_strategy"])
    method_base_chunk = max(
        meaningful_chunk_rows,
        key=lambda item: (
            item["eval"]["macro"].get("recall@5", 0.0),
            item["eval"]["macro"].get("recall@3", 0.0),
            item["eval"]["macro"].get("recall@1", 0.0),
            -item["index"]["avg_index_ms"],
        ),
    )

    # Method comparison
    with _temporary_env(
        {
            "RETRIEVER_TOP_K": str(final_top_k),
            "CHUNK_SIZE_CHARS": str(method_base_chunk["chunk_size"]),
            "CHUNK_OVERLAP_CHARS": str(method_base_chunk["overlap"]),
        }
    ):
        default_index_stats = await _index_documents(unique_documents)
        report["meta"]["vector_backend"] = default_index_stats["backend"]
        report["meta"]["method_base_chunk"] = {
            "chunk_size": method_base_chunk["chunk_size"],
            "overlap": method_base_chunk["overlap"],
        }
        for method in methods:
            rerank_enabled = method == "hybrid"
            row = await _evaluate_cases(
                cases=cases,
                method=method,
                final_top_k=final_top_k,
                ks=top_ks,
                rerank_enabled=rerank_enabled,
                rerank_pool_mult=4,
                lang_routing=lang_routing,
            )
            report["retrieval_methods"].append(row)

        for pool_mult in rerank_pool_mults:
            row = await _evaluate_cases(
                cases=cases,
                method="hybrid",
                final_top_k=final_top_k,
                ks=top_ks,
                rerank_enabled=True,
                rerank_pool_mult=pool_mult,
                lang_routing=lang_routing,
            )
            report["rerank_pool"].append(row)

    # Final top-k sweep
    with _temporary_env(
        {
            "CHUNK_SIZE_CHARS": str(method_base_chunk["chunk_size"]),
            "CHUNK_OVERLAP_CHARS": str(method_base_chunk["overlap"]),
        }
    ):
        await _index_documents(unique_documents)
        for ftk in final_top_k_values:
            row = await _evaluate_cases(
                cases=cases,
                method="hybrid",
                final_top_k=ftk,
                ks=top_ks,
                rerank_enabled=True,
                rerank_pool_mult=4,
                lang_routing=lang_routing,
            )
            row["final_top_k"] = ftk
            report["final_top_k_sweep"].append(row)

    best_chunk = method_base_chunk
    best_method = max(
        report["retrieval_methods"],
        key=lambda item: (
            item["macro"].get("recall@5", 0.0),
            item["macro"].get("recall@3", 0.0),
            -item["macro"]["avg_latency_ms"],
        ),
    )
    best_rerank = max(
        report["rerank_pool"],
        key=lambda item: (
            item["macro"].get("recall@5", 0.0),
            item["macro"].get("recall@3", 0.0),
            -item["macro"]["avg_latency_ms"],
        ),
    )
    report["summary"] = {
        "recommended_chunk": {
            "chunk_size": best_chunk["chunk_size"],
            "overlap": best_chunk["overlap"],
        },
        "recommended_method": best_method["method"],
        "recommended_rerank_pool_mult": best_rerank["rerank_pool_mult"],
    }

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline retrieval benchmark experiments")
    parser.add_argument("--cases", type=str, default=None, help="Benchmark JSON path")
    parser.add_argument(
        "--chunk-configs",
        type=str,
        default=None,
        help="Comma-separated SIZE:OVERLAP pairs, e.g. 160:40,240:60,320:80",
    )
    parser.add_argument("--methods", type=str, default=None, help="dense,lexical,hybrid")
    parser.add_argument("--top-ks", type=str, default=None, help="Comma-separated metrics k values")
    parser.add_argument("--final-top-k", type=int, default=None, help="Final retrieval top-k")
    parser.add_argument(
        "--rerank-pool-mults",
        type=str,
        default=None,
        help="Comma-separated rerank pool multipliers, e.g. 1,2,4",
    )
    parser.add_argument(
        "--final-top-ks",
        type=str,
        default=None,
        help="Comma-separated final_top_k values to sweep, e.g. 3,5,8,12,16",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/eval",
        help="Directory for benchmark outputs (Markdown + JSON)",
    )
    parser.add_argument(
        "--no-lang-routing",
        action="store_true",
        default=False,
        help="Disable language-aware retrieval routing (ablation: ZH queries go through full hybrid)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    report = asyncio.run(_run(args))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_json = output_dir / "retrieval_benchmark_report.json"
    report_md = output_dir / "retrieval_benchmark_report.md"

    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(_render_markdown(report), encoding="utf-8")

    print(f"[BENCH] JSON report: {report_json.resolve()}")
    print(f"[BENCH] Markdown report: {report_md.resolve()}")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
