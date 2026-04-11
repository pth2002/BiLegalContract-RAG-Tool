# Retrieval Benchmark Report

## Run Summary

- Cases: 6
- Top-K metrics: [1, 3, 5]
- Final top-k: 8
- Current vector backend: local
- Method comparison base chunk: 480 / 120

## Chunk Strategy

| Chunk Size | Overlap | Avg Chunks / Doc | Avg Index ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 160 | 40 | 3522.0 | 363027.39 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 240 | 60 | 2348.0 | 327164.06 | 0.0000 | 0.0000 | 0.0139 | 0.1667 |
| 320 | 80 | 1761.0 | 312175.28 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 480 | 120 | 1174.0 | 316809.76 | 0.1667 | 0.1667 | 0.1667 | 0.1667 |
| 900 | 150 | 564.0 | 279785.27 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## Retrieval Method Comparison

| Method | Rerank | Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---|---|---:|---:|---:|---:|---:|---:|
| dense | off | 4 | 3744.14 | 0.0000 | 0.0000 | 0.1667 | 0.1667 |
| lexical | off | 4 | 1275.33 | 0.5000 | 0.8529 | 0.8627 | 1.0000 |
| hybrid | on | 4 | 4999.17 | 0.1667 | 0.1667 | 0.1667 | 0.1667 |

## Rerank Pool Size

| Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|
| 1 | 3680.20 | 0.1667 | 0.1667 | 0.3333 | 0.3333 |
| 2 | 4503.09 | 0.1667 | 0.1667 | 0.1765 | 0.3333 |
| 4 | 6316.67 | 0.1667 | 0.1667 | 0.1667 | 0.1667 |

## Notes

- Gold labels are evidence snippets remapped to chunk ids under each chunk configuration.
- Retrieval methods reuse the current project logic: multi-query, dense / lexical fusion, and optional rerank.
- Method / rerank comparison uses the best non-trivial chunk config (avg chunks per document >= 2) to avoid one-document-one-chunk inflation.
- This benchmark does not change production behavior; it only adds offline evaluation tooling.
