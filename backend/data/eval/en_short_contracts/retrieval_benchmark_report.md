# Retrieval Benchmark Report

## Run Summary

- Cases: 10
- Top-K metrics: [1, 3, 5]
- Final top-k: 8
- Current vector backend: local
- Method comparison base chunk: 900 / 150

## Chunk Strategy

| Chunk Size | Overlap | Avg Chunks / Doc | Avg Index ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 160 | 40 | 17.0 | 4073.37 | 0.6500 | 0.7500 | 0.8500 | 0.9000 |
| 240 | 60 | 11.6 | 2981.35 | 0.4500 | 0.7000 | 0.7000 | 0.9000 |
| 320 | 80 | 8.8 | 3037.34 | 0.5000 | 0.8000 | 0.9000 | 1.0000 |
| 480 | 120 | 5.8 | 3053.02 | 0.5000 | 0.9500 | 1.0000 | 1.0000 |
| 900 | 150 | 3.0 | 3121.88 | 0.7500 | 1.0000 | 1.0000 | 1.0000 |

## Retrieval Method Comparison

| Method | Rerank | Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---|---|---:|---:|---:|---:|---:|---:|
| dense | off | 4 | 844.87 | 0.5000 | 1.0000 | 1.0000 | 1.0000 |
| lexical | off | 4 | 1.59 | 0.0500 | 1.0000 | 1.0000 | 1.0000 |
| hybrid | on | 4 | 1132.47 | 0.7500 | 1.0000 | 1.0000 | 1.0000 |

## Rerank Pool Size

| Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|
| 1 | 1142.65 | 0.7500 | 1.0000 | 1.0000 | 1.0000 |
| 2 | 1145.34 | 0.7500 | 1.0000 | 1.0000 | 1.0000 |
| 4 | 1156.92 | 0.7500 | 1.0000 | 1.0000 | 1.0000 |

## Notes

- Gold labels are evidence snippets remapped to chunk ids under each chunk configuration.
- Retrieval methods reuse the current project logic: multi-query, dense / lexical fusion, and optional rerank.
- Method / rerank comparison uses the best non-trivial chunk config (avg chunks per document >= 2) to avoid one-document-one-chunk inflation.
- This benchmark does not change production behavior; it only adds offline evaluation tooling.
