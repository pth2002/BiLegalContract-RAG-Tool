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
| 900 | 150 | 254.17 | 2352.34 | 0.1953 | 0.3752 | 0.4534 | 0.5890 | 0.4170 | 191.4 | 0.6250 |

## Retrieval Method Comparison

| Method | Rerank | Pool Mult | Avg ms | P50 ms | P95 ms | Recall@5 | Neighbor Recall@5 | Text Match Recall@5 | MRR | Neighbor MRR | Text Match MRR | Hit@5 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | on | 4 | 565.0 | 134.0 | 1829.4 | 0.4534 | 0.5890 | 0.5781 | 0.4170 | 0.4829 | 0.4397 | 0.6250 |

## Rerank Pool Size

| Pool Mult | Avg ms | P50 ms | P95 ms | Recall@5 | Neighbor Recall@5 | Text Match Recall@5 | MRR | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 568.1 | 144.2 | 1854.5 | 0.4534 | 0.5890 | 0.5781 | 0.4170 | 0.6250 |

## Final Top-K Comparison

| Final Top-K | Avg ms | P50 ms | P95 ms | Recall@5 | Neighbor Recall@5 | Text Match Recall@5 | MRR | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 562.6 | 134.9 | 1806.0 | 0.4534 | 0.5890 | 0.5781 | 0.4170 | 0.6250 |

## Results by Document Group

> Three evaluation criteria are shown below. **Strict** requires exact chunk_id match. **Neighbor** also accepts the immediately adjacent chunks (±1). **Text Match** checks whether the retrieved chunk text covers ≥60% of the evidence snippet (longest common substring / snippet length).

### Strict chunk_id Match

| Group | Cases | Recall@1 | Recall@3 | Recall@5 | MRR | Hit@5 |
|---|---:|---:|---:|---:|---:|---:|
| bilingual | 7 | 0.1071 | 0.3929 | 0.3929 | 0.4252 | 0.5714 |
| en | 10 | 0.4000 | 0.5424 | 0.6424 | 0.6250 | 0.9000 |
| zh | 15 | 0.1000 | 0.2556 | 0.3556 | 0.2746 | 0.4667 |

### Neighbor Match (±1)

| Group | Cases | Recall@1 | Recall@3 | Recall@5 | MRR | Hit@5 |
|---|---:|---:|---:|---:|---:|---:|
| bilingual | 7 | 0.2143 | 0.5000 | 0.5714 | 0.4252 | 0.5714 |
| en | 10 | 0.5000 | 0.6515 | 0.7515 | 0.6250 | 0.9000 |
| zh | 15 | 0.2222 | 0.4222 | 0.4889 | 0.4151 | 0.5333 |

### Evidence Text Match

| Group | Cases | Recall@1 | Recall@3 | Recall@5 | MRR | Hit@5 |
|---|---:|---:|---:|---:|---:|---:|
| bilingual | 7 | 0.2143 | 0.5714 | 0.5714 | 0.4252 | 0.5714 |
| en | 10 | 0.5500 | 0.7500 | 0.8500 | 0.6917 | 0.9000 |
| zh | 15 | 0.1000 | 0.2667 | 0.4000 | 0.2784 | 0.5333 |

## Notes

- **Strict**: gold labels are evidence snippets remapped to exact chunk_ids.
- **Neighbor**: immediately adjacent chunk_ids (±1) are also accepted.
- **Text Match**: a chunk hits a snippet when LCS(normalize(chunk), normalize(snippet)) / len(snippet) ≥ 0.6.
- MRR (Mean Reciprocal Rank) = 1/rank of the first relevant chunk under each criterion.
- Retrieval uses current project logic: multi-query, dense/lexical fusion, optional rerank.
- This benchmark does not change production behavior; it only adds offline evaluation tooling.
