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
| 240 | 60 | 902.0 | 201933.54 | 0.0191 | 0.0816 | 0.1476 | 0.1060 | 0.1245 | 678.9 | 0.2500 |
| 480 | 120 | 530.0 | 106854.21 | 0.0677 | 0.1615 | 0.2264 | 0.1591 | 0.2224 | 533.4 | 0.3750 |
| 900 | 150 | 346.5 | 87029.96 | 0.1562 | 0.2578 | 0.3075 | 0.1617 | 0.3136 | 552.7 | 0.4375 |

## Retrieval Method Comparison

| Method | Rerank | Pool Mult | Avg ms | P50 ms | P95 ms | Recall@1 | Recall@3 | Recall@5 | Relaxed Recall@5 | MRR | Hit@5 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | off | 4 | 31.7 | 25.9 | 54.8 | 0.0547 | 0.1406 | 0.1719 | 0.1224 | 0.1461 | 0.2188 |
| lexical | off | 4 | 485.5 | 267.2 | 1323.7 | 0.0000 | 0.0312 | 0.0625 | 0.0495 | 0.0326 | 0.0938 |
| hybrid | on | 4 | 690.5 | 592.9 | 1505.1 | 0.1562 | 0.2891 | 0.3075 | 0.1617 | 0.3162 | 0.4375 |

## Rerank Pool Size

| Pool Mult | Avg ms | P50 ms | P95 ms | Recall@1 | Recall@3 | Recall@5 | Relaxed Recall@5 | MRR | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 601.5 | 359.9 | 1580.5 | 0.1328 | 0.2109 | 0.2370 | 0.1590 | 0.2454 | 0.3125 |
| 2 | 614.3 | 404.9 | 1480.8 | 0.1641 | 0.2422 | 0.2734 | 0.1545 | 0.2855 | 0.3750 |
| 4 | 679.0 | 527.9 | 1563.0 | 0.1562 | 0.2578 | 0.3075 | 0.1617 | 0.3136 | 0.4375 |

## Final Top-K Comparison

| Final Top-K | Avg ms | P50 ms | P95 ms | Recall@1 | Recall@3 | Recall@5 | MRR | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 602.3 | 413.1 | 1496.5 | 0.1172 | 0.1669 | 0.1669 | 0.2292 | 0.2812 |
| 5 | 629.7 | 463.9 | 1449.5 | 0.1797 | 0.2450 | 0.2763 | 0.3109 | 0.4375 |
| 8 | 677.5 | 561.6 | 1587.0 | 0.1562 | 0.2578 | 0.3075 | 0.3136 | 0.4375 |
| 12 | 773.5 | 669.7 | 1628.7 | 0.1562 | 0.2578 | 0.3075 | 0.3128 | 0.4375 |
| 16 | 866.2 | 797.7 | 1804.5 | 0.1562 | 0.2578 | 0.2919 | 0.3080 | 0.4062 |

## Results by Document Group

| Group | Cases | Recall@3 | Recall@5 | MRR | Hit@5 |
|---|---:|---:|---:|---:|---:|
| bilingual | 7 | 0.1786 | 0.2500 | 0.2942 | 0.4286 |
| en | 10 | 0.5500 | 0.5591 | 0.5893 | 0.7000 |
| zh | 15 | 0.1667 | 0.1667 | 0.1444 | 0.2667 |

## Notes

- Gold labels are evidence snippets remapped to chunk ids under each chunk configuration.
- Relaxed metrics treat immediately adjacent chunk ids (±1) as acceptable neighborhood hits for structure-aware chunking.
- MRR (Mean Reciprocal Rank) = 1/rank of the first relevant chunk; measures how high the first hit ranks.
- Retrieval methods reuse the current project logic: multi-query, dense / lexical fusion, and optional rerank.
- Method / rerank comparison uses the best non-trivial chunk config (avg chunks per document >= 2) to avoid one-document-one-chunk inflation.
- This benchmark does not change production behavior; it only adds offline evaluation tooling.
