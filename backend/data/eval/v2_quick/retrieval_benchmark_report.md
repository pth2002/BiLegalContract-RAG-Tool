# Retrieval Benchmark Report

## Run Summary

- Cases: 32
- Top-K metrics: [1, 3, 5]
- Final top-k: 8
- Current vector backend: pgvector
- Method comparison base chunk: 900 / 150

## Chunk Strategy

| Chunk Size | Overlap | Avg Chunks / Doc | Avg Index ms | Recall@1 | Recall@3 | Recall@5 | Relaxed Recall@5 | MRR | P50 ms | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 900 | 150 | 346.5 | 138453.36 | 0.1562 | 0.2578 | 0.3075 | 0.1617 | 0.3136 | 910.9 | 0.4375 |

## Retrieval Method Comparison

| Method | Rerank | Pool Mult | Avg ms | P50 ms | P95 ms | Recall@1 | Recall@3 | Recall@5 | Relaxed Recall@5 | MRR | Hit@5 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | on | 4 | 896.8 | 634.3 | 2248.9 | 0.1562 | 0.2578 | 0.3075 | 0.1617 | 0.3136 | 0.4375 |

## Rerank Pool Size

| Pool Mult | Avg ms | P50 ms | P95 ms | Recall@1 | Recall@3 | Recall@5 | Relaxed Recall@5 | MRR | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 850.7 | 676.4 | 2293.0 | 0.1562 | 0.2578 | 0.3075 | 0.1617 | 0.3136 | 0.4375 |

## Final Top-K Comparison

| Final Top-K | Avg ms | P50 ms | P95 ms | Recall@1 | Recall@3 | Recall@5 | MRR | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 784.4 | 563.8 | 1928.9 | 0.1953 | 0.2607 | 0.2919 | 0.3318 | 0.4375 |
| 8 | 859.6 | 610.5 | 2349.7 | 0.1562 | 0.2578 | 0.3075 | 0.3136 | 0.4375 |

## Results by Document Group

| Group | Cases | Recall@3 | Recall@5 | MRR | Hit@5 |
|---|---:|---:|---:|---:|---:|
| bilingual | 7 | 0.1786 | 0.2500 | 0.2942 | 0.4286 |
| en | 10 | 0.5000 | 0.5591 | 0.5893 | 0.7000 |
| zh | 15 | 0.1333 | 0.1667 | 0.1389 | 0.2667 |

## Notes

- Gold labels are evidence snippets remapped to chunk ids under each chunk configuration.
- Relaxed metrics treat immediately adjacent chunk ids (±1) as acceptable neighborhood hits for structure-aware chunking.
- MRR (Mean Reciprocal Rank) = 1/rank of the first relevant chunk; measures how high the first hit ranks.
- Retrieval methods reuse the current project logic: multi-query, dense / lexical fusion, and optional rerank.
- Method / rerank comparison uses the best non-trivial chunk config (avg chunks per document >= 2) to avoid one-document-one-chunk inflation.
- This benchmark does not change production behavior; it only adds offline evaluation tooling.
