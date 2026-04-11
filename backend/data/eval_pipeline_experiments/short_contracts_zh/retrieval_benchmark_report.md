# Retrieval Benchmark Report

## Run Summary

- Cases: 10
- Top-K metrics: [1, 3, 5]
- Final top-k: 8
- Current vector backend: local
- Method comparison base chunk: 320 / 80

## Chunk Strategy

| Chunk Size | Overlap | Avg Chunks / Doc | Avg Index ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 160 | 40 | 4.6 | 5196.04 | 0.3000 | 0.8667 | 1.0000 | 1.0000 |
| 240 | 60 | 3.0 | 3666.62 | 0.3000 | 1.0000 | 1.0000 | 1.0000 |
| 320 | 80 | 2.0 | 4949.55 | 0.4000 | 1.0000 | 1.0000 | 1.0000 |
| 480 | 120 | 2.0 | 3685.19 | 0.2500 | 1.0000 | 1.0000 | 1.0000 |
| 900 | 150 | 1.0 | 3670.16 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

## Retrieval Method Comparison

| Method | Rerank | Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---|---|---:|---:|---:|---:|---:|---:|
| dense | off | 4 | 2515.75 | 0.4000 | 1.0000 | 1.0000 | 1.0000 |
| lexical | off | 4 | 1.71 | 0.4000 | 1.0000 | 1.0000 | 1.0000 |
| hybrid | on | 4 | 2761.77 | 0.4000 | 1.0000 | 1.0000 | 1.0000 |

## Rerank Pool Size

| Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|
| 1 | 2741.32 | 0.4000 | 1.0000 | 1.0000 | 1.0000 |
| 2 | 2819.93 | 0.4000 | 1.0000 | 1.0000 | 1.0000 |
| 4 | 2814.94 | 0.4000 | 1.0000 | 1.0000 | 1.0000 |

## Notes

- Gold labels are evidence snippets remapped to chunk ids under each chunk configuration.
- Retrieval methods reuse the current project logic: multi-query, dense / lexical fusion, and optional rerank.
- Method / rerank comparison uses the best non-trivial chunk config (avg chunks per document >= 2) to avoid one-document-one-chunk inflation.
- This benchmark does not change production behavior; it only adds offline evaluation tooling.
