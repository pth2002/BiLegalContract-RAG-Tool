# Retrieval Benchmark Report

## Run Summary

- Cases: 6
- Top-K metrics: [1, 3, 5]
- Final top-k: 8
- Current vector backend: local
- Method comparison base chunk: 480 / 120

## Chunk Strategy

| Chunk Size | Overlap | Avg Chunks / Doc | Avg Index ms | Recall@1 | Recall@3 | Recall@5 | Relaxed Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 480 | 120 | 1220.0 | 414569.84 | 0.3472 | 0.8611 | 0.8750 | 0.4127 | 1.0000 |

## Retrieval Method Comparison

| Method | Rerank | Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Relaxed Recall@5 | Hit@5 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| dense | off | 4 | 15918.65 | 0.1667 | 0.6667 | 0.8333 | 0.3333 | 0.8333 |
| lexical | off | 4 | 1824.07 | 0.0000 | 0.1667 | 0.1667 | 0.0556 | 0.1667 |
| hybrid | on | 4 | 20020.50 | 0.3472 | 0.8611 | 0.8750 | 0.4127 | 1.0000 |

## Rerank Pool Size

| Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Relaxed Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 18211.19 | 0.5000 | 0.6667 | 0.6667 | 0.3889 | 0.6667 |
| 2 | 18527.59 | 0.5000 | 0.8472 | 0.8611 | 0.3452 | 1.0000 |
| 4 | 19743.08 | 0.3472 | 0.8611 | 0.8750 | 0.4127 | 1.0000 |

## Notes

- Gold labels are evidence snippets remapped to chunk ids under each chunk configuration.
- Relaxed metrics treat immediately adjacent chunk ids (±1) as acceptable neighborhood hits for structure-aware chunking.
- Retrieval methods reuse the current project logic: multi-query, dense / lexical fusion, and optional rerank.
- Method / rerank comparison uses the best non-trivial chunk config (avg chunks per document >= 2) to avoid one-document-one-chunk inflation.
- This benchmark does not change production behavior; it only adds offline evaluation tooling.
