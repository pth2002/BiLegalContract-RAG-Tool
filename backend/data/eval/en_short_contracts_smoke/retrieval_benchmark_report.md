# Retrieval Benchmark Report

## Run Summary

- Cases: 10
- Top-K metrics: [1, 3, 5]
- Final top-k: 8
- Current vector backend: local
- Method comparison base chunk: 240 / 60

## Chunk Strategy

| Chunk Size | Overlap | Avg Chunks / Doc | Avg Index ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 240 | 60 | 11.6 | 4083.56 | 0.4500 | 0.7000 | 0.7000 | 0.9000 |

## Retrieval Method Comparison

| Method | Rerank | Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---|---|---:|---:|---:|---:|---:|---:|
| lexical | off | 4 | 3.40 | 0.4000 | 0.6500 | 0.8000 | 1.0000 |

## Rerank Pool Size

| Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Hit@5 |
|---:|---:|---:|---:|---:|---:|
| 1 | 1252.99 | 0.4500 | 0.7000 | 0.8000 | 0.9000 |

## Notes

- Gold labels are evidence snippets remapped to chunk ids under each chunk configuration.
- Retrieval methods reuse the current project logic: multi-query, dense / lexical fusion, and optional rerank.
- Method / rerank comparison uses the best non-trivial chunk config (avg chunks per document >= 2) to avoid one-document-one-chunk inflation.
- This benchmark does not change production behavior; it only adds offline evaluation tooling.
