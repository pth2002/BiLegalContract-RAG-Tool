# Retrieval Benchmark Report

## Run Summary

- Cases: 4
- Top-K metrics: [1, 3, 5]
- Final top-k: 8
- Current vector backend: local
- Method comparison base chunk: 240 / 60

## Chunk Strategy

| Chunk Size | Overlap | Avg Chunks / Doc | Avg Index ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 240 | 60 | 619.0 | 256065.23 | 0.1958 | 0.4208 | 0.6786 | 1.0000 |
| 320 | 80 | 465.0 | 292288.75 | 0.1938 | 0.4271 | 0.5875 | 1.0000 |
| 480 | 120 | 310.0 | 291076.37 | 0.2058 | 0.5342 | 0.6342 | 1.0000 |

## Retrieval Method Comparison

| Method | Rerank | Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---|---|---:|---:|---:|---:|---:|---:|
| dense | off | 4 | 2137.38 | 0.0619 | 0.2696 | 0.3696 | 1.0000 |
| lexical | off | 4 | 251.30 | 0.2077 | 0.4655 | 0.5393 | 1.0000 |
| hybrid | on | 4 | 4834.82 | 0.1958 | 0.4208 | 0.6786 | 1.0000 |

## Rerank Pool Size

| Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|
| 1 | 3088.73 | 0.2077 | 0.4655 | 0.5274 | 1.0000 |
| 2 | 3625.96 | 0.2077 | 0.3702 | 0.5274 | 1.0000 |
| 4 | 4753.70 | 0.1958 | 0.4208 | 0.6786 | 1.0000 |

## Notes

- Gold labels are evidence snippets remapped to chunk ids under each chunk configuration.
- Retrieval methods reuse the current project logic: multi-query, dense / lexical fusion, and optional rerank.
- Method / rerank comparison uses the best non-trivial chunk config (avg chunks per document >= 2) to avoid one-document-one-chunk inflation.
- This benchmark does not change production behavior; it only adds offline evaluation tooling.
