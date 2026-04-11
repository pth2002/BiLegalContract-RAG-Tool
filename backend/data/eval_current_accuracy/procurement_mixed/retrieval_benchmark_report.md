# Retrieval Benchmark Report

## Run Summary

- Cases: 32
- Top-K metrics: [1, 3, 5]
- Final top-k: 8
- Current vector backend: local
- Method comparison base chunk: 240 / 60

## Chunk Strategy

| Chunk Size | Overlap | Avg Chunks / Doc | Avg Index ms | Recall@1 | Recall@3 | Recall@5 | Relaxed Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 240 | 60 | 479.0 | 135789.38 | 0.0000 | 0.0156 | 0.0938 | 0.0781 | 0.0938 |

## Retrieval Method Comparison

| Method | Rerank | Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Relaxed Recall@5 | Hit@5 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| hybrid | on | 4 | 11018.27 | 0.0000 | 0.0156 | 0.0938 | 0.0781 | 0.0938 |

## Rerank Pool Size

| Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Relaxed Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|
| 4 | 11166.76 | 0.0000 | 0.0156 | 0.0938 | 0.0781 | 0.0938 |

## Notes

- Gold labels are evidence snippets remapped to chunk ids under each chunk configuration.
- Relaxed metrics treat immediately adjacent chunk ids (±1) as acceptable neighborhood hits for structure-aware chunking.
- Retrieval methods reuse the current project logic: multi-query, dense / lexical fusion, and optional rerank.
- Method / rerank comparison uses the best non-trivial chunk config (avg chunks per document >= 2) to avoid one-document-one-chunk inflation.
- This benchmark does not change production behavior; it only adds offline evaluation tooling.
