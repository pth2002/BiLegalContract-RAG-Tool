"""End-to-end (generation + LLM-as-Judge) benchmark for the contract RAG system.

For each benchmark case:
  1. Build a natural-language e2e_query from focus_areas (Method C).
  2. Retrieve top-8 chunks via the existing retrieval pipeline.
  3. Call gpt-4o to generate an answer grounded in those chunks.
  4. Call gpt-4o as judge to score Faithfulness and Completeness (1-5).
  5. Aggregate results by language group (zh / en / bilingual).

Usage (from backend/):
  python -m src.tooling.run_e2e_benchmark
  python -m src.tooling.run_e2e_benchmark --cases data/retrieval_benchmark_cases_v2.json
  python -m src.tooling.run_e2e_benchmark --smoke-test   # first zh + en + bilingual only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# OpenAI — always hit the real endpoint, never a proxy
# ---------------------------------------------------------------------------
import openai

_OPENAI_BASE_URL = "https://api.openai.com/v1"
_OPENAI_MODEL = "gpt-4o"
_TEMPERATURE = 0

# ---------------------------------------------------------------------------
# Reuse retrieval benchmark internals
# ---------------------------------------------------------------------------
from .run_retrieval_benchmark import (
    BenchmarkCase,
    _load_cases,
    _retrieve_ranked,
    _resolve_gold_chunk_ids,
    _temporary_env,
)
from ..services.indexing_service import index_document
from ..services.retrieval_eval_service import hit_rate_at_k
from ..services.vector_store_service import delete_chunks_for_document, init_vector_store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optimal retrieval config (AutoDL-aligned, frozen at v1.0-retrieval-frozen)
# ---------------------------------------------------------------------------
_RETRIEVAL_ENV = {
    "CHUNK_SIZE_CHARS": "900",
    "CHUNK_OVERLAP_CHARS": "150",
    "RETRIEVER_TOP_K": "8",
    "RERANK_POOL_MULT": "4",
    "PGVECTOR_PROBES": "100",
}

_FINAL_TOP_K = 8


# ---------------------------------------------------------------------------
# e2e query builder  (Method C)
# ---------------------------------------------------------------------------

def _join_focus_areas(areas: list[str], lang: str) -> str:
    """Join focus_areas with proper connectives."""
    if not areas:
        return ""
    if len(areas) == 1:
        return areas[0]
    if lang == "en":
        return ", ".join(areas[:-1]) + " and " + areas[-1]
    else:
        return "、".join(areas[:-1]) + "和" + areas[-1]


def _make_e2e_query(case: BenchmarkCase) -> str:
    """Build a natural-language question from the case's focus_areas."""
    lang = case.tags[0] if case.tags else "zh"
    options = case.options or {}
    focus_areas: list[str] = options.get("focus_areas") or []
    joined = _join_focus_areas(focus_areas, lang)

    if lang == "en":
        if joined:
            return f"What are the specific contractual provisions regarding {joined}?"
        return "What are the key contractual provisions in this agreement?"
    else:
        if joined:
            return f"请说明本合同中关于{joined}的具体条款内容。"
        return "请说明本合同的主要条款内容。"


# ---------------------------------------------------------------------------
# OpenAI client factory
# ---------------------------------------------------------------------------

def _get_openai_client() -> openai.AsyncOpenAI:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Add it to backend/.env or set the environment variable."
        )
    return openai.AsyncOpenAI(
        api_key=api_key,
        base_url=_OPENAI_BASE_URL,
    )


# ---------------------------------------------------------------------------
# GPT-4o call with retry
# ---------------------------------------------------------------------------

async def _call_gpt4o(
    *,
    client: openai.AsyncOpenAI,
    system: str,
    user: str,
    max_retries: int = 3,
) -> str:
    """Call gpt-4o with up to max_retries attempts. Returns the content string."""
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = await client.chat.completions.create(
                model=_OPENAI_MODEL,
                temperature=_TEMPERATURE,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            last_exc = exc
            logger.warning("[E2E] gpt-4o call attempt %d/%d failed: %s", attempt, max_retries, exc)
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)  # exponential back-off: 2s, 4s
    raise RuntimeError(f"gpt-4o call failed after {max_retries} attempts") from last_exc


# ---------------------------------------------------------------------------
# Generation step
# ---------------------------------------------------------------------------

_GEN_SYSTEM_ZH = "你是一个合同审查助手。根据检索到的合同条款片段，准确回答用户的问题。"
_GEN_SYSTEM_EN = "You are a contract review assistant. Answer the user's question accurately based on the retrieved contract clause excerpts."

_GEN_USER_ZH = """\
你是一个合同审查助手。根据以下检索到的合同条款片段，回答用户的问题。

要求：
- 只根据提供的条款内容回答，不要编造
- 如果条款中没有相关信息，明确说明"未找到相关条款"
- 引用具体条款编号（如果有的话）

【检索到的条款片段】
{chunks}

【用户问题】
{query}"""

_GEN_USER_EN = """\
You are a contract review assistant. Answer the user's question based solely on the retrieved contract clause excerpts below.

Requirements:
- Only use information from the provided excerpts; do not fabricate content.
- If the relevant information is not found in the excerpts, clearly state "No relevant clause found."
- Cite specific clause numbers where available.

[Retrieved Contract Excerpts]
{chunks}

[User Question]
{query}"""


def _format_chunks_for_prompt(chunks: list[Any]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        chunk_id = getattr(chunk, "chunk_id", f"chunk_{i}")
        content = getattr(chunk, "content", str(chunk))
        score = getattr(chunk, "score", None)
        score_str = f" (score={score:.4f})" if score is not None else ""
        parts.append(f"[{chunk_id}]{score_str}\n{content.strip()}")
    return "\n\n---\n\n".join(parts)


async def _generate_answer(
    *,
    client: openai.AsyncOpenAI,
    case: BenchmarkCase,
    chunks: list[Any],
    e2e_query: str,
) -> str:
    lang = case.tags[0] if case.tags else "zh"
    chunks_text = _format_chunks_for_prompt(chunks)

    if lang == "en":
        system = _GEN_SYSTEM_EN
        user = _GEN_USER_EN.format(chunks=chunks_text, query=e2e_query)
    else:
        system = _GEN_SYSTEM_ZH
        user = _GEN_USER_ZH.format(chunks=chunks_text, query=e2e_query)

    return await _call_gpt4o(client=client, system=system, user=user)


# ---------------------------------------------------------------------------
# Judge step
# ---------------------------------------------------------------------------

_JUDGE_SYSTEM = "你是一个合同审查 RAG 系统的评估专家，只输出 JSON，不输出其他任何内容。"

_JUDGE_USER = """\
你是一个合同审查 RAG 系统的评估专家。请评估以下 AI 生成的回答。

【用户问题】
{query}

【检索到的合同条款片段】
{retrieved_chunks_text}

【参考证据（关键条款）】
{evidence_snippet}

【AI 生成的回答】
{generated_answer}

请从以下两个维度评分（1-5 分），并给出简短理由：

## Faithfulness（忠实度）
回答内容是否忠实于合同条款？有没有编造不存在的信息？
评判依据：回答中的内容如果能在"检索到的合同条款片段"或"参考证据"中找到出处，就是忠实的。只有回答中出现了这两个来源都没有的信息，才算编造。

- 5分：所有内容都有检索片段或参考证据支撑
- 4分：基本忠实，有少量合理推断但不改变事实
- 3分：大部分忠实，有少量无法从任何来源验证的说法
- 2分：较多无法验证的内容或明显曲解
- 1分：大量编造，严重偏离合同内容

## Completeness（完整性）
相对于参考证据中的关键信息，回答覆盖了多少？

- 5分：完全覆盖参考证据中的所有关键点
- 4分：覆盖了大部分关键点，遗漏少量细节
- 3分：覆盖了约一半的关键点
- 2分：只覆盖了少量关键点，大量遗漏
- 1分：几乎没有覆盖参考证据的内容

请严格按以下 JSON 格式输出，不要输出其他任何内容：
{{"faithfulness": <分数>, "faithfulness_reason": "<理由>", "completeness": <分数>, "completeness_reason": "<理由>"}}"""


def _parse_judge_json(raw: str) -> dict[str, Any] | None:
    """Parse judge output JSON with fallback stripping of markdown fences."""
    text = raw.strip()
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    # Find first { ... } block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
        required = {"faithfulness", "faithfulness_reason", "completeness", "completeness_reason"}
        if required.issubset(data.keys()):
            return data
    except Exception:
        pass
    return None


async def _judge_answer(
    *,
    client: openai.AsyncOpenAI,
    e2e_query: str,
    evidence_snippets: list[str],
    generated_answer: str,
    chunks: list[Any],
) -> dict[str, Any]:
    evidence_text = "\n".join(f"- {s}" for s in evidence_snippets)
    retrieved_chunks_text = _format_chunks_for_prompt(chunks)
    user = _JUDGE_USER.format(
        query=e2e_query,
        retrieved_chunks_text=retrieved_chunks_text,
        evidence_snippet=evidence_text,
        generated_answer=generated_answer,
    )
    raw = await _call_gpt4o(client=client, system=_JUDGE_SYSTEM, user=user)
    parsed = _parse_judge_json(raw)
    if parsed is not None:
        return {"status": "ok", **parsed}
    return {"status": "parse_error", "raw_output": raw}


# ---------------------------------------------------------------------------
# Main benchmark loop
# ---------------------------------------------------------------------------

async def _run_e2e(
    cases: list[BenchmarkCase],
    smoke_test: bool = False,
    case_id: str | None = None,
) -> list[dict[str, Any]]:
    client = _get_openai_client()

    # Single-case mode
    if case_id:
        matched = [c for c in cases if c.case_id == case_id]
        if not matched:
            available = [c.case_id for c in cases]
            raise SystemExit(f"case_id '{case_id}' not found. Available:\n" + "\n".join(f"  {x}" for x in available))
        cases = matched
        print(f"\n[SINGLE CASE] {case_id}\n")

    # For smoke test: pick first of each language group
    elif smoke_test:
        seen: set[str] = set()
        selected: list[BenchmarkCase] = []
        for c in cases:
            lang = c.tags[0] if c.tags else "other"
            if lang not in seen and lang in {"zh", "en", "bilingual"}:
                seen.add(lang)
                selected.append(c)
            if len(selected) == 3:
                break
        cases = selected
        print(f"\n[SMOKE TEST] Running {len(cases)} cases: {[c.case_id for c in cases]}\n")

    results: list[dict[str, Any]] = []
    total = len(cases)

    for idx, case in enumerate(cases, 1):
        lang = case.tags[0] if case.tags else "other"
        print(f"[{idx:02d}/{total:02d}] case={case.case_id}  lang={lang}")

        e2e_query = _make_e2e_query(case)
        print(f"         e2e_query: {e2e_query}")

        # --- Retrieval ---
        t0 = time.perf_counter()
        try:
            chunks = await _retrieve_ranked(
                document=case.document,
                perspective=case.perspective,
                options=case.options,
                queries_override=None,
                method="hybrid",
                final_top_k=_FINAL_TOP_K,
                rerank_enabled=True,
                rerank_pool_mult=4,
                lang_routing=True,
            )
        except Exception as exc:
            logger.error("[E2E] retrieval failed for %s: %s", case.case_id, exc)
            results.append({
                "case_id": case.case_id, "lang": lang, "e2e_query": e2e_query,
                "status": "retrieval_error", "error": str(exc),
            })
            continue
        retrieval_ms = round((time.perf_counter() - t0) * 1000, 1)

        # Strict Hit@5 for correlation analysis
        gold_ids = _resolve_gold_chunk_ids(case.document, case.evidence_snippets)
        retrieved_ids = [c.chunk_id for c in chunks]
        strict_hit5 = hit_rate_at_k(retrieved_ids, gold_ids, 5)

        print(f"         retrieved {len(chunks)} chunks in {retrieval_ms}ms  hit@5={strict_hit5:.0f}")

        # --- Generation ---
        print(f"         → generating answer ...")
        try:
            generated_answer = await _generate_answer(
                client=client, case=case, chunks=chunks, e2e_query=e2e_query,
            )
        except Exception as exc:
            logger.error("[E2E] generation failed for %s: %s", case.case_id, exc)
            results.append({
                "case_id": case.case_id, "lang": lang, "e2e_query": e2e_query,
                "retrieved_chunk_ids": retrieved_ids,
                "strict_hit5": strict_hit5,
                "status": "generation_error", "error": str(exc),
            })
            continue

        # --- Judge ---
        print(f"         → judging answer ...")
        try:
            judge_result = await _judge_answer(
                client=client,
                e2e_query=e2e_query,
                evidence_snippets=case.evidence_snippets,
                generated_answer=generated_answer,
                chunks=chunks,
            )
        except Exception as exc:
            logger.error("[E2E] judge failed for %s: %s", case.case_id, exc)
            judge_result = {"status": "judge_error", "error": str(exc)}

        status = judge_result.get("status", "ok")
        if status == "ok":
            faith = judge_result.get("faithfulness", "?")
            comp = judge_result.get("completeness", "?")
            print(f"         [OK] faithfulness={faith}  completeness={comp}")
        else:
            print(f"         [FAIL] judge status={status}")

        results.append({
            "case_id": case.case_id,
            "lang": lang,
            "tags": list(case.tags),
            "perspective": case.perspective.value,
            "e2e_query": e2e_query,
            "evidence_snippets": case.evidence_snippets,
            "retrieved_chunk_ids": retrieved_ids,
            "retrieval_ms": retrieval_ms,
            "strict_hit5": strict_hit5,
            "generated_answer": generated_answer,
            **{k: v for k, v in judge_result.items() if k != "status"},
            "judge_status": status,
        })

    return results


# ---------------------------------------------------------------------------
# Aggregation & reporting
# ---------------------------------------------------------------------------

def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [r for r in results if r.get("judge_status") == "ok"]
    parse_errors = sum(1 for r in results if r.get("judge_status") == "parse_error")
    other_errors = sum(1 for r in results if r.get("judge_status") not in {"ok", "parse_error"})

    groups: dict[str, list[dict]] = {}
    for r in scored:
        lang = r["lang"]
        groups.setdefault(lang, []).append(r)

    by_group: dict[str, dict] = {}
    for lang, rows in groups.items():
        by_group[lang] = {
            "count": len(rows),
            "faithfulness_avg": round(_mean([r["faithfulness"] for r in rows]), 3),
            "completeness_avg": round(_mean([r["completeness"] for r in rows]), 3),
        }

    all_faith = [r["faithfulness"] for r in scored]
    all_comp = [r["completeness"] for r in scored]

    # Retrieval hit vs miss
    hit_rows = [r for r in scored if r.get("strict_hit5", 0) >= 1.0]
    miss_rows = [r for r in scored if r.get("strict_hit5", 0) < 1.0]

    return {
        "total_cases": len(results),
        "scored_cases": len(scored),
        "parse_errors": parse_errors,
        "other_errors": other_errors,
        "macro_faithfulness": round(_mean(all_faith), 3),
        "macro_completeness": round(_mean(all_comp), 3),
        "by_group": by_group,
        "retrieval_hit_cases": len(hit_rows),
        "retrieval_miss_cases": len(miss_rows),
        "hit_faithfulness_avg": round(_mean([r["faithfulness"] for r in hit_rows]), 3) if hit_rows else None,
        "hit_completeness_avg": round(_mean([r["completeness"] for r in hit_rows]), 3) if hit_rows else None,
        "miss_faithfulness_avg": round(_mean([r["faithfulness"] for r in miss_rows]), 3) if miss_rows else None,
        "miss_completeness_avg": round(_mean([r["completeness"] for r in miss_rows]), 3) if miss_rows else None,
    }


def _render_markdown(results: list[dict[str, Any]], agg: dict[str, Any], run_ts: str) -> str:
    lines: list[str] = []
    lines.append("# End-to-End Benchmark Report")
    lines.append(f"\n_Run: {run_ts}_\n")

    lines.append("## Overall Scores\n")
    lines.append("| Dimension | zh | en | bilingual | Macro |")
    lines.append("|-----------|---:|---:|----------:|------:|")
    for dim, key in [("Faithfulness", "faithfulness_avg"), ("Completeness", "completeness_avg")]:
        by_g = agg["by_group"]
        zh = f"{by_g.get('zh', {}).get(key, '-')}"
        en = f"{by_g.get('en', {}).get(key, '-')}"
        bi = f"{by_g.get('bilingual', {}).get(key, '-')}"
        macro_key = "macro_faithfulness" if dim == "Faithfulness" else "macro_completeness"
        macro = f"{agg[macro_key]}"
        lines.append(f"| {dim} | {zh} | {en} | {bi} | {macro} |")
    lines.append("")

    lines.append("## Retrieval Hit vs Miss\n")
    lines.append(f"- Hit cases (Strict Hit@5=1): **{agg['retrieval_hit_cases']}**")
    lines.append(f"- Miss cases (Strict Hit@5=0): **{agg['retrieval_miss_cases']}**")
    if agg["hit_faithfulness_avg"] is not None:
        lines.append(f"- Hit → Faithfulness avg: **{agg['hit_faithfulness_avg']}** / Completeness avg: **{agg['hit_completeness_avg']}**")
    if agg["miss_faithfulness_avg"] is not None:
        lines.append(f"- Miss → Faithfulness avg: **{agg['miss_faithfulness_avg']}** / Completeness avg: **{agg['miss_completeness_avg']}**")
    lines.append("")

    lines.append("## Per-Case Detail\n")
    lines.append("| case_id | lang | e2e_query | Faith | Comp | Faith reason (50c) | Comp reason (50c) | hit@5 |")
    lines.append("|---------|------|-----------|------:|-----:|--------------------|-------------------|------:|")
    for r in results:
        if r.get("judge_status") != "ok":
            lines.append(
                f"| {r['case_id']} | {r.get('lang','')} | {r.get('e2e_query','')} "
                f"| — | — | judge_status={r.get('judge_status')} | | {r.get('strict_hit5','?')} |"
            )
            continue
        fr = (r.get("faithfulness_reason") or "")[:50]
        cr = (r.get("completeness_reason") or "")[:50]
        lines.append(
            f"| {r['case_id']} | {r['lang']} | {r['e2e_query']} "
            f"| {r['faithfulness']} | {r['completeness']} "
            f"| {fr} | {cr} | {r.get('strict_hit5', '?')} |"
        )
    lines.append("")

    lines.append("## Anomalous Cases (faith=1 or comp=1)\n")
    anomalies = [r for r in results if r.get("judge_status") == "ok"
                 and (r.get("faithfulness") == 1 or r.get("completeness") == 1)]
    if anomalies:
        for r in anomalies:
            lines.append(f"### {r['case_id']} (lang={r['lang']}, hit@5={r.get('strict_hit5')})")
            lines.append(f"- faithfulness={r.get('faithfulness')}  reason: {r.get('faithfulness_reason')}")
            lines.append(f"- completeness={r.get('completeness')}  reason: {r.get('completeness_reason')}")
            lines.append(f"- generated_answer: {r.get('generated_answer','')[:300]}")
            lines.append("")
    else:
        lines.append("_None._\n")

    lines.append("## Error Summary\n")
    lines.append(f"- parse_error: {agg['parse_errors']}")
    lines.append(f"- other_errors: {agg['other_errors']}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def _main(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    # Ensure OPENAI_API_KEY is available (may be passed via env or .env)
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")

    # Inject OPENAI_API_KEY from CLI if provided (overrides .env)
    if args.api_key:
        os.environ["OPENAI_API_KEY"] = args.api_key

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("ERROR: OPENAI_API_KEY not set. Add it to backend/.env or pass --api-key.")

    repo_root = Path(__file__).resolve().parents[3]
    cases_path = (
        Path(args.cases) if args.cases
        else repo_root / "backend" / "data" / "retrieval_benchmark_cases_v2.json"
    ).resolve()

    print(f"Loading cases from: {cases_path}")
    cases, defaults = _load_cases(cases_path, repo_root)
    print(f"Loaded {len(cases)} cases.\n")

    with _temporary_env(_RETRIEVAL_ENV):
        # Index all unique documents once
        print("Indexing documents ...")
        await init_vector_store()
        unique_docs = list({c.document.id: c.document for c in cases}.values())
        for doc in unique_docs:
            await delete_chunks_for_document(doc.id)
            await index_document(doc)
        print(f"Indexed {len(unique_docs)} document(s).\n")

        # Run benchmark
        results = await _run_e2e(cases, smoke_test=args.smoke_test, case_id=args.case_id)

    agg = _aggregate(results)

    # Print smoke-test details to stdout
    if args.smoke_test:
        print("\n" + "=" * 70)
        print("SMOKE TEST DETAILED OUTPUT")
        print("=" * 70)
        for r in results:
            print(f"\n{'─'*60}")
            print(f"case_id   : {r['case_id']}")
            print(f"lang      : {r.get('lang')}")
            print(f"e2e_query : {r.get('e2e_query')}")
            print(f"strict_hit5: {r.get('strict_hit5')}")
            print(f"\n--- Generated Answer ---")
            print(r.get("generated_answer", "(error)"))
            if r.get("judge_status") == "ok":
                print(f"\n--- Judge Score ---")
                print(f"faithfulness  : {r.get('faithfulness')} — {r.get('faithfulness_reason')}")
                print(f"completeness  : {r.get('completeness')} — {r.get('completeness_reason')}")
            else:
                print(f"\n--- Judge Status: {r.get('judge_status')} ---")
                if "raw_output" in r:
                    print("raw_output:", r["raw_output"])
                if "error" in r:
                    print("error:", r["error"])
        print("\n" + "=" * 70)

    # Print summary table
    print("\n── Summary ──────────────────────────────────────────────────────")
    print(f"Total cases: {agg['total_cases']}  scored: {agg['scored_cases']}  "
          f"parse_error: {agg['parse_errors']}  other_error: {agg['other_errors']}")
    print(f"Macro Faithfulness: {agg['macro_faithfulness']}  "
          f"Macro Completeness: {agg['macro_completeness']}")
    print("\nBy group:")
    for lang, g in sorted(agg["by_group"].items()):
        print(f"  {lang:10s}  n={g['count']}  faith={g['faithfulness_avg']}  comp={g['completeness_avg']}")
    if agg.get("hit_faithfulness_avg") is not None or agg.get("miss_faithfulness_avg") is not None:
        print(f"\nRetrieval hit ({agg['retrieval_hit_cases']} cases): "
              f"faith={agg['hit_faithfulness_avg']}  comp={agg['hit_completeness_avg']}")
        print(f"Retrieval miss ({agg['retrieval_miss_cases']} cases): "
              f"faith={agg['miss_faithfulness_avg']}  comp={agg['miss_completeness_avg']}")

    # Save results
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(__file__).resolve().parents[2] / "benchmarks"
    out_dir.mkdir(exist_ok=True)

    suffix = f"_{args.case_id}" if args.case_id else ("_smoke" if args.smoke_test else "")
    json_path = out_dir / f"e2e_results{suffix}_{run_ts}.json"
    md_path = out_dir / f"e2e_report{suffix}_{run_ts}.md"

    payload = {"run_ts": run_ts, "aggregate": agg, "results": results}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(results, agg, run_ts), encoding="utf-8")

    print(f"\nResults → {json_path}")
    print(f"Report  → {md_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="E2E benchmark for contract RAG (generation + LLM-as-Judge)")
    parser.add_argument("--cases", default=None, help="Path to benchmark cases JSON")
    parser.add_argument("--smoke-test", action="store_true", help="Run only 1 zh + 1 en + 1 bilingual case")
    parser.add_argument("--case-id", default=None, help="Run a single case by its ID (e.g. arlo_purchase_price)")
    parser.add_argument("--api-key", default=None, help="OpenAI API key (overrides OPENAI_API_KEY env var)")
    args = parser.parse_args()
    asyncio.run(_main(args))


if __name__ == "__main__":
    main()
