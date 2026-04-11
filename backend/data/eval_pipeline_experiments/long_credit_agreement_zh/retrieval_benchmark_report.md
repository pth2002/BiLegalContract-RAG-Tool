# Retrieval Benchmark Report

## Run Summary

- Cases: 4
- Top-K metrics: [1, 3, 5]
- Final top-k: 8
- Current vector backend: local
- Method comparison base chunk: 160 / 40

## Chunk Strategy

| Chunk Size | Overlap | Avg Chunks / Doc | Avg Index ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 160 | 40 | 929.0 | 218833.31 | 0.1864 | 0.4530 | 0.6477 | 1.0000 |
| 240 | 60 | 619.0 | 210570.4 | 0.1958 | 0.4327 | 0.6286 | 1.0000 |
| 320 | 80 | 465.0 | 226432.37 | 0.1938 | 0.4271 | 0.5771 | 1.0000 |
| 480 | 120 | 310.0 | 222617.61 | 0.2058 | 0.5342 | 0.6342 | 1.0000 |
| 900 | 150 | 149.0 | 94698.31 | 0.2230 | 0.4877 | 0.4877 | 1.0000 |

## Retrieval Method Comparison

| Method | Rerank | Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---|---|---:|---:|---:|---:|---:|---:|
| dense | off | 4 | 1924.81 | 0.1364 | 0.2280 | 0.3311 | 1.0000 |
| lexical | off | 4 | 239.53 | 0.1864 | 0.4144 | 0.5705 | 1.0000 |
| hybrid | on | 4 | 3412.69 | 0.1864 | 0.4530 | 0.6477 | 1.0000 |

## Rerank Pool Size

| Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|
| 1 | 2691.82 | 0.1864 | 0.4644 | 0.5061 | 1.0000 |
| 2 | 2777.84 | 0.1864 | 0.4644 | 0.5561 | 1.0000 |
| 4 | 3499.76 | 0.1864 | 0.4530 | 0.6477 | 1.0000 |

## Notes

- Gold labels are evidence snippets remapped to chunk ids under each chunk configuration.
- Retrieval methods reuse the current project logic: multi-query, dense / lexical fusion, and optional rerank.
- Method / rerank comparison uses the best non-trivial chunk config (avg chunks per document >= 2) to avoid one-document-one-chunk inflation.
- This benchmark does not change production behavior; it only adds offline evaluation tooling.
