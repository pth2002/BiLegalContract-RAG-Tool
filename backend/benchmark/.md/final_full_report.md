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
| 160 | 40 | 1179.5 | 16783.3 | 0.0781 | 0.1555 | 0.2375 | 0.3313 | 0.1897 | 691.1 | 0.3438 |
| 240 | 60 | 809.5 | 11289.94 | 0.0469 | 0.1389 | 0.2014 | 0.3984 | 0.1603 | 685.5 | 0.3125 |
| 320 | 80 | 625.83 | 9445.66 | 0.0982 | 0.1756 | 0.2355 | 0.4111 | 0.2775 | 633.5 | 0.4062 |
| 480 | 120 | 437.67 | 8171.31 | 0.1094 | 0.2500 | 0.3021 | 0.4868 | 0.2842 | 628.3 | 0.4375 |
| 900 | 150 | 254.17 | 7035.84 | 0.1953 | 0.3752 | 0.4534 | 0.5890 | 0.4170 | 731.3 | 0.6250 |

## Retrieval Method Comparison

| Method | Rerank | Pool Mult | Avg ms | P50 ms | P95 ms | Recall@5 | Neighbor Recall@5 | Text Match Recall@5 | MRR | Neighbor MRR | Text Match MRR | Hit@5 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | off | 4 | 58.1 | 44.2 | 106.6 | 0.4010 | 0.5104 | 0.4531 | 0.2815 | 0.3284 | 0.2815 | 0.5000 |
| lexical | off | 4 | 745.2 | 369.6 | 2079.7 | 0.1823 | 0.2917 | 0.2188 | 0.1592 | 0.2350 | 0.1949 | 0.2500 |
| hybrid | on | 4 | 1281.7 | 691.1 | 3164.7 | 0.4534 | 0.5890 | 0.5781 | 0.4170 | 0.4829 | 0.4397 | 0.6250 |

## Rerank Pool Size

| Pool Mult | Avg ms | P50 ms | P95 ms | Recall@5 | Neighbor Recall@5 | Text Match Recall@5 | MRR | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 940.1 | 330.1 | 2666.2 | 0.3880 | 0.5521 | 0.4844 | 0.3519 | 0.5312 |
| 2 | 1136.0 | 621.7 | 2919.7 | 0.4349 | 0.5521 | 0.5312 | 0.3806 | 0.5625 |
| 4 | 1303.1 | 713.2 | 3299.0 | 0.4534 | 0.5890 | 0.5781 | 0.4170 | 0.6250 |

## Final Top-K Comparison

| Final Top-K | Avg ms | P50 ms | P95 ms | Recall@5 | Neighbor Recall@5 | Text Match Recall@5 | MRR | Hit@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 929.4 | 315.2 | 2888.7 | 0.3179 | 0.4692 | 0.3906 | 0.3958 | 0.4688 |
| 5 | 1078.6 | 539.0 | 2813.7 | 0.4690 | 0.5890 | 0.5625 | 0.4073 | 0.6250 |
| 8 | 1271.9 | 700.2 | 3142.0 | 0.4534 | 0.5890 | 0.5781 | 0.4170 | 0.6250 |
| 12 | 1560.2 | 927.9 | 3589.9 | 0.4534 | 0.5890 | 0.5781 | 0.4113 | 0.6250 |
| 16 | 1809.8 | 1237.6 | 4056.8 | 0.4534 | 0.5890 | 0.5781 | 0.4098 | 0.6250 |

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
