# Contract RAG — Embedding & Reranker Ablation Summary

Dataset: 32 benchmark cases (15 zh · 10 en · 7 bilingual) across 6 contracts (1525 chunks).

Fixed: chunk 900:150 · hybrid retrieval · rerank pool mult=4 · final top-k=8 · pgvector ivfflat probes=100


## Table 1 — Overall comparison (4 runs)

| # | Embedding | Reranker | Strict R@5 | Neighbor R@5 | Text R@5 | MRR | P50 ms | P95 ms |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | bge-large-zh-v1.5 | bge-reranker-base | 0.3804 | 0.4692 | 0.4375 | 0.3693 | 87.2 | 1780.5 |
| 2 | bge-large-zh-v1.5 | bge-reranker-large | 0.4534 | 0.5890 | 0.5781 | 0.4170 | 134.0 | 1829.4 |
| 3 | bge-m3 | bge-reranker-large | 0.4534 | 0.5890 | 0.5781 | 0.4154 | 172.1 | 1846.1 |
| 4 | multilingual-e5-large | bge-reranker-large | 0.4534 | 0.5890 | 0.5781 | 0.4305 | 156.9 | 1871.1 |

## Table 2 — Macro R@5 (language-weighted average)

| # | Embedding | Reranker | Strict Macro | Neighbor Macro | Text Match Macro |
|---|---|---|---:|---:|---:|
| 1 | bge-large-zh-v1.5 | bge-reranker-base | 0.3771 | 0.4658 | 0.4468 |
| 2 | bge-large-zh-v1.5 | bge-reranker-large | 0.4636 | 0.6039 | 0.6071 |
| 3 | bge-m3 | bge-reranker-large | 0.4636 | 0.6039 | 0.6071 |
| 4 | multilingual-e5-large | bge-reranker-large | 0.4636 | 0.6039 | 0.6071 |

## Table 3.1 — Strict chunk_id Match

| # | Embedding | Reranker | zh (15) | en (10) | bi (7) |
|---|---|---|---:|---:|---:|
| 1 | bge-large-zh-v1.5 | bge-reranker-base | 0.3222 | 0.5591 | 0.2500 |
| 2 | bge-large-zh-v1.5 | bge-reranker-large | 0.3556 | 0.6424 | 0.3929 |
| 3 | bge-m3 | bge-reranker-large | 0.3556 | 0.6424 | 0.3929 |
| 4 | multilingual-e5-large | bge-reranker-large | 0.3556 | 0.6424 | 0.3929 |

## Table 3.2 — Neighbor Match (±1)

| # | Embedding | Reranker | zh (15) | en (10) | bi (7) |
|---|---|---|---:|---:|---:|
| 1 | bge-large-zh-v1.5 | bge-reranker-base | 0.4222 | 0.6182 | 0.3571 |
| 2 | bge-large-zh-v1.5 | bge-reranker-large | 0.4889 | 0.7515 | 0.5714 |
| 3 | bge-m3 | bge-reranker-large | 0.4889 | 0.7515 | 0.5714 |
| 4 | multilingual-e5-large | bge-reranker-large | 0.4889 | 0.7515 | 0.5714 |

## Table 3.3 — Evidence Text Match (LCS ≥ 60%)

| # | Embedding | Reranker | zh (15) | en (10) | bi (7) |
|---|---|---|---:|---:|---:|
| 1 | bge-large-zh-v1.5 | bge-reranker-base | 0.3333 | 0.6500 | 0.3571 |
| 2 | bge-large-zh-v1.5 | bge-reranker-large | 0.4000 | 0.8500 | 0.5714 |
| 3 | bge-m3 | bge-reranker-large | 0.4000 | 0.8500 | 0.5714 |
| 4 | multilingual-e5-large | bge-reranker-large | 0.4000 | 0.8500 | 0.5714 |

## Key Findings

- **Reranker upgrade is the single biggest win**: base → large lifts overall Strict R@5 from 0.3804 → 0.4534 (+19.2%).
- **Bilingual group benefits the most from reranker-large**: 0.2500 → 0.3929 (+57.2%).
- **Embedding choice is neutralized by strong reranker**: bge-large-zh, bge-m3, and multilingual-e5-large all converge to identical Strict R@5 = 0.4534 once reranker-large is applied.
- **pgvector ivfflat bug discovered & fixed**: with default probes=1 on 1525 rows, bge-m3 zh R@5 dropped to 0. Fixed via `SET LOCAL ivfflat.probes = 100`.
- **Production pick**: bge-large-zh + bge-reranker-large — same accuracy as bge-m3/e5 but smaller model, fastest P50 (134.0 ms), lowest index cost.