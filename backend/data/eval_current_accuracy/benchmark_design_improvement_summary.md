# Benchmark Summary: Design / Structure Upgrade vs Previous Accuracy

## Scope

This summary focuses on whether the current **design / parser / retrieval-branch upgrade**
improved retrieval accuracy relative to the previous benchmarkable baseline.

The most apples-to-apples comparison is:

- Same document: `Exh 10.1 - Credit Agreement.pdf`
- Same historical 6-case benchmark set
- Same base chunk config: `480 / 120`

Additional current-only robustness runs were also executed on:

- Expanded English long-contract set: 31 cases
- Mixed Chinese/English procurement contract: 32 cases

## 1. Comparable Before vs After (English Long Credit Agreement, 6 Cases)

### Previous Baseline

- Base chunk: `480 / 120`
- Best method: `lexical`
- Best rerank pool: `1`

Method comparison:

| Method | Recall@1 | Recall@3 | Recall@5 | Avg Latency ms |
|---|---:|---:|---:|---:|
| dense | 0.1667 | 0.3333 | 0.5000 | 2002.07 |
| lexical | 0.3333 | 0.5196 | 0.5294 | 739.92 |
| hybrid | 0.1667 | 0.1667 | 0.1667 | 4567.16 |

### Current Upgraded Version (Exact-Chunk Scoring)

- Base chunk: `480 / 120`
- Best method: `dense`
- Best rerank pool: `1`

Method comparison:

| Method | Recall@1 | Recall@3 | Recall@5 | Avg Latency ms |
|---|---:|---:|---:|---:|
| dense | 0.1667 | 0.5000 | 0.5000 | 5185.76 |
| lexical | 0.0139 | 0.1806 | 0.1806 | 466.48 |
| hybrid | 0.0000 | 0.0000 | 0.1667 | 7464.06 |

### Current Upgraded Version (Relaxed Adjacent-Chunk Scoring)

Relaxed metrics treat immediately adjacent chunk ids (`gold ± 1`) as acceptable neighborhood hits.

| Method | Relaxed Hit@1 | Relaxed Hit@3 | Relaxed Hit@5 | Relaxed Recall@5 |
|---|---:|---:|---:|---:|
| dense | 0.1667 | 0.5000 | 0.6667 | 0.2778 |
| lexical | 0.1667 | 0.3333 | 0.3333 | 0.0675 |
| hybrid | 0.0000 | 0.1667 | 0.3333 | 0.1111 |

### Direct Takeaway

On the old 6-case English benchmark, the new design **still did not improve overall exact-chunk accuracy**, but one major benchmark distortion has now been fixed.

- `dense` improved at `Recall@3` (`0.3333 -> 0.5000`)
- After unifying dense / lexical / benchmark gold onto the same chunking logic, `lexical` recovered from `0 / 0 / 0` to `0.0139 / 0.1806 / 0.1806`
- This confirms the earlier `lexical = 0` result was partly caused by chunk-world inconsistency rather than total lexical failure
- The current `hybrid + rerank` path still remained weak on this comparable set

After fixing the chunk-world mismatch, relaxed adjacent-chunk scoring for `lexical` is now:

- Relaxed Hit@3 = `0.3333`
- Relaxed Hit@5 = `0.3333`
- Relaxed Recall@5 = `0.0675`

This indicates the upgraded structure-aware chunking still moves some English clause hits into neighboring chunks, but the more serious issue was that lexical retrieval had been using a different chunking universe than indexing / dense search / benchmark gold mapping.

So if the question is:

> "After the parser / structure / branch redesign, did accuracy on the old English benchmark improve?"

The answer is:

> **No overall on the strict exact-chunk metric. It still regresses on the old English comparison set, but the earlier `lexical = 0` result was partially an artifact of inconsistent chunking logic and is no longer the correct diagnosis.**

## 2. Current Robustness Run (Expanded English Long Contract, 31 Cases)

- Document: `Exh 10.1 - Credit Agreement.pdf`
- Cases: `31`
- Base chunk: `480 / 120`
- Best method: `dense`
- Best rerank pool: `2`

Method comparison:

| Method | Recall@1 | Recall@3 | Recall@5 | Avg Latency ms |
|---|---:|---:|---:|---:|
| dense | 0.0000 | 0.0323 | 0.1613 | 3646.77 |
| lexical | 0.0000 | 0.0000 | 0.0323 | 486.52 |
| hybrid | 0.0000 | 0.0000 | 0.0323 | 6869.13 |

Takeaway:

- Once the case set is expanded from `6` to `31`, the task becomes much harder
- The current system is still far from robust long-English contract retrieval
- `dense` is currently the least bad option, but absolute accuracy remains low

## 3. Current Robustness Run (Mixed Chinese/English Procurement Contract, 32 Cases)

- Document: `purchase-of-goods-and-services-china-english.pdf`
- Cases: `32`
- Base chunk: `240 / 60`
- Method run: `hybrid`
- Rerank pool: `4`

Method result:

| Method | Recall@1 | Recall@3 | Recall@5 | Avg Latency ms |
|---|---:|---:|---:|---:|
| hybrid | 0.0000 | 0.0156 | 0.0312 | 11236.32 |

Takeaway:

- Mixed-language legal procurement retrieval is currently very weak
- Even after structure-aware parsing and Chinese branch improvements, accuracy on a larger mixed case set remains low
- This confirms the current system is **not yet a reliable general-purpose bilingual contract retriever**

## 4. Environment Notes

- Vector backend during these runs: `local` fallback
- Embedding model: `BAAI/bge-large-zh-v1.5`
- Reranker: `BAAI/bge-reranker-base`
- All runs were CPU-based
- `pgvector` was not active in the benchmark backend

## 5. Final Conclusion

The current parser / structure / retrieval-branch upgrade **did not produce a general accuracy improvement**.

What the benchmark shows is:

1. On the old comparable English benchmark, overall accuracy **did not improve**, and lexical retrieval regressed.
2. On a larger 31-case English benchmark, current retrieval accuracy is still low.
3. On a 32-case mixed Chinese/English procurement benchmark, current retrieval accuracy is also very low.

Therefore, the redesign added architectural value and a better foundation, but **it has not yet translated into stronger benchmark accuracy** on these larger / more realistic long-document settings.
