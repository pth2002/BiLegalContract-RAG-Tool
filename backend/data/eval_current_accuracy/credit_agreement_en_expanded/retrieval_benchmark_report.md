# Retrieval Benchmark Report

## Run Summary

- Cases: 31
- Top-K metrics: [1, 3, 5]
- Final top-k: 8
- Current vector backend: local
- Method comparison base chunk: 480 / 120

## Chunk Strategy

| Chunk Size | Overlap | Avg Chunks / Doc | Avg Index ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 480 | 120 | 1220.0 | 510642.64 | 0.0000 | 0.0000 | 0.0323 | 0.0323 |

## Retrieval Method Comparison

| Method | Rerank | Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---|---|---:|---:|---:|---:|---:|---:|
| dense | off | 4 | 3646.77 | 0.0000 | 0.0323 | 0.1613 | 0.1613 |
| lexical | off | 4 | 486.52 | 0.0000 | 0.0000 | 0.0323 | 0.0323 |
| hybrid | on | 4 | 6869.13 | 0.0000 | 0.0000 | 0.0323 | 0.0323 |

## Rerank Pool Size

| Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|
| 1 | 5018.31 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 2 | 5537.74 | 0.0000 | 0.0323 | 0.0645 | 0.0645 |
| 4 | 6730.54 | 0.0000 | 0.0000 | 0.0323 | 0.0323 |

## Notes

- Gold labels are evidence snippets remapped to chunk ids under each chunk configuration.
- Retrieval methods reuse the current project logic: multi-query, dense / lexical fusion, and optional rerank.
- Method / rerank comparison uses the best non-trivial chunk config (avg chunks per document >= 2) to avoid one-document-one-chunk inflation.
- This benchmark does not change production behavior; it only adds offline evaluation tooling.
