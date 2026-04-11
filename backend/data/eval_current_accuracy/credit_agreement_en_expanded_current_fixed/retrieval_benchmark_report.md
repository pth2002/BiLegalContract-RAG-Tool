# Retrieval Benchmark Report

## Run Summary

- Cases: 31
- Top-K metrics: [1, 3, 5]
- Final top-k: 8
- Current vector backend: local
- Method comparison base chunk: 480 / 120

## Chunk Strategy

| Chunk Size | Overlap | Avg Chunks / Doc | Avg Index ms | Recall@1 | Recall@3 | Recall@5 | Relaxed Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 480 | 120 | 1220.0 | 501231.67 | 0.5522 | 0.8272 | 0.8417 | 0.3712 | 0.9355 |

## Retrieval Method Comparison

| Method | Rerank | Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Relaxed Recall@5 | Hit@5 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| dense | off | 4 | 13812.26 | 0.2000 | 0.4204 | 0.5035 | 0.2300 | 0.6129 |
| hybrid | on | 4 | 17818.41 | 0.5522 | 0.8272 | 0.8417 | 0.3712 | 0.9355 |

## Rerank Pool Size

| Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Relaxed Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|
| 4 | 17593.51 | 0.5522 | 0.8272 | 0.8417 | 0.3712 | 0.9355 |

## Notes

- Gold labels are evidence snippets remapped to chunk ids under each chunk configuration.
- Relaxed metrics treat immediately adjacent chunk ids (±1) as acceptable neighborhood hits for structure-aware chunking.
- Retrieval methods reuse the current project logic: multi-query, dense / lexical fusion, and optional rerank.
- Method / rerank comparison uses the best non-trivial chunk config (avg chunks per document >= 2) to avoid one-document-one-chunk inflation.
- This benchmark does not change production behavior; it only adds offline evaluation tooling.
