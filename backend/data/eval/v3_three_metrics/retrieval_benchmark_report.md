# Retrieval Benchmark Report

## Run Summary

- Cases: 32
- Top-K metrics: [1, 3, 5]
- Final top-k: 8
- Current vector backend: pgvector
- Method comparison base chunk: 900 / 150

## Chunk Strategy

| Chunk Size | Overlap | Avg Chunks / Doc | Avg Index ms | Recall@1 | Recall@3 | Recall@5 | Neighbor Recall@5 | MRR | P50 ms | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 900 | 150 | 346.5 | 165732.62 | 0.1562 | 0.2578 | 0.3075 | 0.4119 | 0.3136 | 935.0 | 0.4375 |

## Retrieval Method Comparison

| Method | Rerank | Pool Mult | Avg ms | P50 ms | P95 ms | Recall@5 | Neighbor Recall@5 | Text Match Recall@5 | MRR | Neighbor MRR | Text Match MRR | Hit@5 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | on | 4 | 858.4 | 655.9 | 1880.7 | 0.3075 | 0.4119 | 0.3594 | 0.3136 | 0.3501 | 0.3410 | 0.4375 |

## Rerank Pool Size

| Pool Mult | Avg ms | P50 ms | P95 ms | Recall@5 | Neighbor Recall@5 | Text Match Recall@5 | MRR | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 834.5 | 633.2 | 1897.7 | 0.3075 | 0.4119 | 0.3594 | 0.3136 | 0.4375 |

## Final Top-K Comparison

| Final Top-K | Avg ms | P50 ms | P95 ms | Recall@5 | Neighbor Recall@5 | Text Match Recall@5 | MRR | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 856.5 | 654.0 | 2240.1 | 0.3075 | 0.4119 | 0.3594 | 0.3136 | 0.4375 |

## Results by Document Group

> Three evaluation criteria are shown below. **Strict** requires exact chunk_id match. **Neighbor** also accepts the immediately adjacent chunks (±1). **Text Match** checks whether the retrieved chunk text covers ≥60% of the evidence snippet (longest common substring / snippet length).

### Strict chunk_id Match

| Group | Cases | Recall@1 | Recall@3 | Recall@5 | MRR | Hit@5 |
|---|---:|---:|---:|---:|---:|---:|
| bilingual | 7 | 0.0714 | 0.1786 | 0.2500 | 0.2942 | 0.4286 |
| en | 10 | 0.4000 | 0.5000 | 0.5591 | 0.5893 | 0.7000 |
| zh | 15 | 0.0333 | 0.1333 | 0.1667 | 0.1389 | 0.2667 |

### Neighbor Match (±1)

| Group | Cases | Recall@1 | Recall@3 | Recall@5 | MRR | Hit@5 |
|---|---:|---:|---:|---:|---:|---:|
| bilingual | 7 | 0.1429 | 0.2143 | 0.3571 | 0.3180 | 0.4286 |
| en | 10 | 0.5000 | 0.6000 | 0.6182 | 0.5893 | 0.7000 |
| zh | 15 | 0.0667 | 0.2333 | 0.3000 | 0.2056 | 0.3333 |

### Evidence Text Match

| Group | Cases | Recall@1 | Recall@3 | Recall@5 | MRR | Hit@5 |
|---|---:|---:|---:|---:|---:|---:|
| bilingual | 7 | 0.0714 | 0.2857 | 0.3571 | 0.2942 | 0.4286 |
| en | 10 | 0.5500 | 0.6500 | 0.6500 | 0.6643 | 0.7000 |
| zh | 15 | 0.0333 | 0.1333 | 0.1667 | 0.1472 | 0.2667 |

## Notes

- **Strict**: gold labels are evidence snippets remapped to exact chunk_ids.
- **Neighbor**: immediately adjacent chunk_ids (±1) are also accepted.
- **Text Match**: a chunk hits a snippet when LCS(normalize(chunk), normalize(snippet)) / len(snippet) ≥ 0.6.
- MRR (Mean Reciprocal Rank) = 1/rank of the first relevant chunk under each criterion.
- Retrieval uses current project logic: multi-query, dense/lexical fusion, optional rerank.
- This benchmark does not change production behavior; it only adds offline evaluation tooling.
