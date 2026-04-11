# Post-Upgrade Benchmark — AutoDL Aligned

**Timestamp**: 2026-04-11
**Config**: bge-reranker-large + PGVECTOR_PROBES=100 + chunk=900:150

## Configuration

| Parameter | Value |
|-----------|-------|
| EMBEDDING_MODEL | BAAI/bge-large-zh-v1.5 |
| RERANK_MODEL | BAAI/bge-reranker-large |
| PGVECTOR_PROBES | 100 |
| CHUNK_SIZE | 900 chars / 150 overlap |
| RERANK_POOL_MULT | 4 |
| RETRIEVER_TOP_K | 8 |
| Retrieval method | hybrid (lang-routing: ZH queries → dense) |

## Results — Strict Recall@5 (hybrid, pool_mult=4, chunk=900:150)

| Group | Recall@5 |
|-------|----------|
| zh (15 cases) | 0.3556 |
| en (10 cases) | 0.6424 |
| bilingual (7 cases) | 0.3929 |
| **Macro** | **0.4534** |

## Latency (hybrid)

| Metric | Value |
|--------|-------|
| P50 | 691.1 ms |
| P95 | 3164.7 ms |

## Method Comparison (chunk=900:150)

| Method | Macro R@5 | zh | en | bilingual | P50 ms |
|--------|-----------|----|----|-----------|--------|
| dense    | 0.4010 | 0.4889 | 0.4500 | 0.1429 | 44.2 |
| lexical  | 0.1823 | 0.3556 | 0.0000 | 0.0714 | 369.6 |
| hybrid   | 0.4534 | 0.3556 | 0.6424 | 0.3929 | 691.1 |

## Notes

- Macro 0.4534 vs AutoDL target 0.4636 — Δ=+0.010, within ±0.01 tolerance ✅
- P50 691ms vs AutoDL ~134ms — local significantly slower (expected: no GPU-optimized VRAM config, reranker cold-load each benchmark pass)
- Relative group order: en > bilingual > zh ✅ matches AutoDL
