# Benchmark Comparison Summary

## Scope

- Chinese short contracts: [retrieval_benchmark_report.md](D:/AI%20agent%20rag%20%E5%90%88%E5%90%8C%E9%A1%B9%E7%9B%AE/contract/backend/data/eval/retrieval_benchmark_report.md)
- English short contracts (translated): [retrieval_benchmark_report.md](D:/AI%20agent%20rag%20%E5%90%88%E5%90%8C%E9%A1%B9%E7%9B%AE/contract/backend/data/eval/en_short_contracts/retrieval_benchmark_report.md)
- English long credit agreement: [retrieval_benchmark_report.md](D:/AI%20agent%20rag%20%E5%90%88%E5%90%8C%E9%A1%B9%E7%9B%AE/contract/backend/data/eval/long_credit_agreement/retrieval_benchmark_report.md)
- Chinese long credit agreement: [retrieval_benchmark_report.md](D:/AI%20agent%20rag%20%E5%90%88%E5%90%8C%E9%A1%B9%E7%9B%AE/contract/backend/data/eval/long_credit_agreement_zh/retrieval_benchmark_report.md)

All three runs currently use the local vector-store fallback rather than pgvector.

## High-Level Comparison

| Dataset | Cases | Recommended Chunk | Chunk Recall@1 | Best Method | Method Recall@1 | Method Recall@3 | Recommended Rerank Pool | Notes |
|---|---:|---|---:|---|---:|---:|---:|---|
| Chinese short contracts | 10 | 320 / 80 | 0.4000 | lexical / dense / hybrid tie | 0.4000 | 1.0000 | 2 | Short Chinese samples are easy; all methods saturate by Recall@3. |
| English short contracts | 10 | 900 / 150 | 0.7500 | hybrid + rerank | 0.7500 | 1.0000 | 1 | Strong result, but chunk recommendation is optimistic because documents are very short and collapse to about 3 chunks each. |
| English long credit agreement | 6 | 480 / 120 | 0.1667 | lexical | 0.3333 | 0.5196 | 1 | Long English legal document exposes retrieval difficulty; hybrid + rerank underperforms. |
| Chinese long credit agreement | 4 | 240 / 60 | 0.1958 | hybrid + rerank | 0.1958 | 0.4208 | 4 | Chinese long-document retrieval is materially stronger than the English long version; dense alone is weakest, lexical is strong, and hybrid improves Recall@5. |

## Method Comparison Details

| Dataset | Dense Recall@1 / @3 / @5 | Lexical Recall@1 / @3 / @5 | Hybrid+Rerank Recall@1 / @3 / @5 | Main Takeaway |
|---|---|---|---|---|
| Chinese short contracts | 0.4000 / 1.0000 / 1.0000 | 0.4000 / 1.0000 / 1.0000 | 0.4000 / 1.0000 / 1.0000 | The task is too easy to separate methods on these short Chinese examples. |
| English short contracts | 0.5000 / 1.0000 / 1.0000 | 0.0500 / 1.0000 / 1.0000 | 0.7500 / 1.0000 / 1.0000 | English explicit queries plus rerank help top-1 ordering on short translated contracts. |
| English long credit agreement | 0.1667 / 0.3333 / 0.5000 | 0.3333 / 0.5196 / 0.5294 | 0.1667 / 0.1667 / 0.1667 | On a long English credit agreement, lexical anchors outperform dense/hybrid; current hybrid query path is not well aligned to this document type. |
| Chinese long credit agreement | 0.0619 / 0.2696 / 0.3696 | 0.2077 / 0.4655 / 0.5393 | 0.1958 / 0.4208 / 0.6786 | On the Chinese long document, lexical gives the best top-1 and top-3, while hybrid+rerank gives the best Recall@5. |

## Rerank Comparison

| Dataset | Pool 1 | Pool 2 | Pool 4 | Main Takeaway |
|---|---|---|---|---|
| Chinese short contracts | Recall@1 0.4000, latency 827.98 ms | Recall@1 0.4000, latency 399.37 ms | Recall@1 0.4000, latency 364.45 ms | Rerank pool size barely matters on easy short Chinese samples. |
| English short contracts | Recall@1 0.7500, latency 1142.65 ms | Recall@1 0.7500, latency 1145.34 ms | Recall@1 0.7500, latency 1156.92 ms | Rerank is stable across pool sizes on short translated samples; pool 1 is the cheapest acceptable choice. |
| English long credit agreement | Recall@5 0.3431, latency 3228.15 ms | Recall@5 0.1765, latency 3869.33 ms | Recall@5 0.1667, latency 6095.89 ms | On the English long agreement, increasing the rerank pool hurts both quality and latency. |
| Chinese long credit agreement | Recall@5 0.5274, latency 3088.73 ms | Recall@5 0.5274, latency 3625.96 ms | Recall@5 0.6786, latency 4753.70 ms | On the Chinese long agreement, a larger rerank pool improves Recall@5 but costs substantially more latency. |

## Interview Notes

- Short contracts mainly prove that the retrieval chain is wired correctly and that rerank can improve top-1 on compact English samples.
- Long contracts are much more valuable for evaluation because chunk count rises from single digits to hundreds or thousands, which exposes retrieval and ranking weaknesses.
- The English long-document result shows that the current project setup is not well aligned to long English finance-law documents.
- The Chinese long-document result is more representative of the project's intended language setting: lexical is best for top-1/top-3, while hybrid+rerank helps cover more relevant evidence by top-5.
- If asked why short and long results differ, the clean answer is: candidate-space size, clause density, and language/domain mismatch all scale up on the long agreement.
