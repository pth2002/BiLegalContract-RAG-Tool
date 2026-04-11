# Retrieval Benchmark Report

## Run Summary

- Cases: 4
- Top-K metrics: [1, 3, 5]
- Final top-k: 8
- Current vector backend: local
- Method comparison base chunk: 480 / 120

## Chunk Strategy

| Chunk Size | Overlap | Avg Chunks / Doc | Avg Index ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 480 | 120 | 310.0 | 185789.19 | 0.2058 | 0.5342 | 0.6342 | 1.0000 |

## Retrieval Method Comparison

| Method | Rerank | Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---|---|---:|---:|---:|---:|---:|---:|
| lexical | off | 4 | 136.95 | 0.1225 | 0.3883 | 0.4383 | 1.0000 |

## Rerank Pool Size

| Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|
| 1 | 2341.28 | 0.2058 | 0.3883 | 0.4483 | 1.0000 |

## Notes

- Gold labels are evidence snippets remapped to chunk ids under each chunk configuration.
- Retrieval methods reuse the current project logic: multi-query, dense / lexical fusion, and optional rerank.
- Method / rerank comparison uses the best non-trivial chunk config (avg chunks per document >= 2) to avoid one-document-one-chunk inflation.
- This benchmark does not change production behavior; it only adds offline evaluation tooling.
