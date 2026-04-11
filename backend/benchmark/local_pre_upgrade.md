# Pre-Upgrade Baseline

**Timestamp**: 2026-04-11
**Config**: bge-reranker-base + PGVECTOR_PROBES=50 (code default) + chunk=900:150

## Configuration

| Parameter | Value |
|-----------|-------|
| EMBEDDING_MODEL | BAAI/bge-large-zh-v1.5 |
| RERANK_MODEL | BAAI/bge-reranker-base |
| PGVECTOR_PROBES | 50 (code default, not set in .env) |
| CHUNK_SIZE (zh) | 900 chars / 150 overlap |
| CHUNK_SIZE (en) | 900 chars / 150 overlap |
| RERANK_POOL_MULT | 4 |
| RETRIEVER_TOP_K | 8 |
| Retrieval method | hybrid (lang-routing: ZH queries → dense) |

## Results — Strict Recall@5 (hybrid, pool_mult=4, chunk=900:150)

| Group | Recall@5 | Hit@5 |
|-------|----------|-------|
| zh (15 cases) | 0.3222 | 0.4000 |
| en (10 cases) | 0.5591 | 0.7000 |
| bilingual (7 cases) | 0.2500 | — |
| **Macro** | **0.3804** | — |

## Latency (hybrid)

| Metric | Value |
|--------|-------|
| P50 | 230.4 ms |
| P95 | 3223.3 ms |

## Method Comparison (chunk=900:150)

| Method | Macro R@5 | zh | en | bilingual | P50 ms |
|--------|-----------|----|----|-----------|--------|
| dense    | 0.4010 | 0.4889 | 0.4500 | 0.1429 | 54.3 |
| lexical  | 0.1823 | 0.3556 | 0.0000 | 0.0714 | 439.3 |
| hybrid   | 0.3804 | 0.3222 | 0.5591 | 0.2500 | 230.4 |

## Notes

- bi group key in JSON report is `bilingual`, not `bi`
- AutoDL target (rr-large, probes=100): zh=0.3556 / en=0.6424 / bi=0.3929 / Macro=0.4636 / P50~134ms
- Expected deltas after upgrade: zh+0.033 / en+0.083 / bi+0.143 / Macro+0.083
