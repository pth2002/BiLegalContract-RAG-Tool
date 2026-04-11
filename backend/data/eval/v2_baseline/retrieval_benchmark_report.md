# Retrieval Benchmark Report

## Run Summary

- Cases: 32
- Top-K metrics: [1, 3, 5]
- Final top-k: 8
- Current vector backend: local
- Method comparison base chunk: 900 / 150

## Chunk Strategy

| Chunk Size | Overlap | Avg Chunks / Doc | Avg Index ms | Recall@1 | Recall@3 | Recall@5 | Relaxed Recall@5 | MRR | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 900 | 150 | 346.5 | 15902.85 | 0.2344 | 0.3594 | 0.3906 | 0.2512 | 0.3605 | 0.4375 |

## Retrieval Method Comparison

| Method | Rerank | Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Relaxed Recall@5 | MRR | Hit@5 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | on | 4 | 3989.37 | 0.2188 | 0.3125 | 0.3594 | 0.2433 | 0.3193 | 0.4062 |

## Rerank Pool Size

| Pool Mult | Avg Latency ms | Recall@1 | Recall@3 | Recall@5 | Relaxed Recall@5 | MRR | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1065.91 | 0.1250 | 0.1719 | 0.1875 | 0.1693 | 0.1562 | 0.1875 |
| 2 | 10552.40 | 0.2344 | 0.2812 | 0.3125 | 0.2303 | 0.2862 | 0.3438 |
| 4 | 14903.98 | 0.2344 | 0.3594 | 0.3906 | 0.2512 | 0.3657 | 0.4375 |

## Results by Document Group

| Group | Cases | Recall@3 | Recall@5 | MRR | Hit@5 |
|---|---:|---:|---:|---:|---:|
| bilingual | 7 | 0.0000 | 0.0714 | 0.0536 | 0.1429 |
| en | 10 | 0.5500 | 0.5500 | 0.5810 | 0.6000 |
| zh | 15 | 0.3000 | 0.3667 | 0.2689 | 0.4000 |

## Notes

- Gold labels are evidence snippets remapped to chunk ids under each chunk configuration.
- Relaxed metrics treat immediately adjacent chunk ids (±1) as acceptable neighborhood hits for structure-aware chunking.
- MRR (Mean Reciprocal Rank) = 1/rank of the first relevant chunk; measures how high the first hit ranks.
- Retrieval methods reuse the current project logic: multi-query, dense / lexical fusion, and optional rerank.
- Method / rerank comparison uses the best non-trivial chunk config (avg chunks per document >= 2) to avoid one-document-one-chunk inflation.
- This benchmark does not change production behavior; it only adds offline evaluation tooling.
