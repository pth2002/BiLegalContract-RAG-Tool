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
| 900 | 150 | 254.17 | 140323.74 | 0.1875 | 0.2839 | 0.3492 | 0.4848 | 0.3553 | 953.5 | 0.4688 |

## Retrieval Method Comparison

| Method | Rerank | Pool Mult | Avg ms | P50 ms | P95 ms | Recall@5 | Neighbor Recall@5 | Text Match Recall@5 | MRR | Neighbor MRR | Text Match MRR | Hit@5 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | on | 4 | 944.9 | 651.5 | 2301.3 | 0.3492 | 0.4848 | 0.4219 | 0.3553 | 0.4438 | 0.3891 | 0.4688 |

## Rerank Pool Size

| Pool Mult | Avg ms | P50 ms | P95 ms | Recall@5 | Neighbor Recall@5 | Text Match Recall@5 | MRR | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 930.6 | 655.6 | 2276.1 | 0.3492 | 0.4848 | 0.4219 | 0.3553 | 0.4688 |

## Final Top-K Comparison

| Final Top-K | Avg ms | P50 ms | P95 ms | Recall@5 | Neighbor Recall@5 | Text Match Recall@5 | MRR | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 949.8 | 650.7 | 2325.1 | 0.3492 | 0.4848 | 0.4219 | 0.3553 | 0.4688 |

## Results by Document Group

> Three evaluation criteria are shown below. **Strict** requires exact chunk_id match. **Neighbor** also accepts the immediately adjacent chunks (±1). **Text Match** checks whether the retrieved chunk text covers ≥60% of the evidence snippet (longest common substring / snippet length).

### Strict chunk_id Match

| Group | Cases | Recall@1 | Recall@3 | Recall@5 | MRR | Hit@5 |
|---|---:|---:|---:|---:|---:|---:|
| bilingual | 7 | 0.0714 | 0.1786 | 0.2500 | 0.2942 | 0.4286 |
| en | 10 | 0.4000 | 0.5000 | 0.5591 | 0.5893 | 0.7000 |
| zh | 15 | 0.1000 | 0.1889 | 0.2556 | 0.2278 | 0.3333 |

### Neighbor Match (±1)

| Group | Cases | Recall@1 | Recall@3 | Recall@5 | MRR | Hit@5 |
|---|---:|---:|---:|---:|---:|---:|
| bilingual | 7 | 0.1429 | 0.2143 | 0.3571 | 0.3180 | 0.4286 |
| en | 10 | 0.5000 | 0.6000 | 0.6182 | 0.5893 | 0.7000 |
| zh | 15 | 0.2222 | 0.4222 | 0.4556 | 0.4056 | 0.5333 |

### Evidence Text Match

| Group | Cases | Recall@1 | Recall@3 | Recall@5 | MRR | Hit@5 |
|---|---:|---:|---:|---:|---:|---:|
| bilingual | 7 | 0.0714 | 0.2857 | 0.3571 | 0.2942 | 0.4286 |
| en | 10 | 0.5500 | 0.6500 | 0.6500 | 0.6643 | 0.7000 |
| zh | 15 | 0.1000 | 0.2333 | 0.3000 | 0.2500 | 0.4000 |

## Notes

- **Strict**: gold labels are evidence snippets remapped to exact chunk_ids.
- **Neighbor**: immediately adjacent chunk_ids (±1) are also accepted.
- **Text Match**: a chunk hits a snippet when LCS(normalize(chunk), normalize(snippet)) / len(snippet) ≥ 0.6.
- MRR (Mean Reciprocal Rank) = 1/rank of the first relevant chunk under each criterion.
- Retrieval uses current project logic: multi-query, dense/lexical fusion, optional rerank.
- This benchmark does not change production behavior; it only adds offline evaluation tooling.
