# Benchmark Comparison Summary

## Scope

- Chinese short contracts: [retrieval_benchmark_report.md](D:/AI%20agent%20rag%20%E5%90%88%E5%90%8C%E9%A1%B9%E7%9B%AE/contract/backend/data/eval/retrieval_benchmark_report.md)
- English short contracts (translated): [retrieval_benchmark_report.md](D:/AI%20agent%20rag%20%E5%90%88%E5%90%8C%E9%A1%B9%E7%9B%AE/contract/backend/data/eval/en_short_contracts/retrieval_benchmark_report.md)
- English long credit agreement: [retrieval_benchmark_report.md](D:/AI%20agent%20rag%20%E5%90%88%E5%90%8C%E9%A1%B9%E7%9B%AE/contract/backend/data/eval/long_credit_agreement/retrieval_benchmark_report.md)
- Chinese long credit agreement: [retrieval_benchmark_report.md](D:/AI%20agent%20rag%20%E5%90%88%E5%90%8C%E9%A1%B9%E7%9B%AE/contract/backend/data/eval/long_credit_agreement_zh/retrieval_benchmark_report.md)


## High-Level Comparison

| Dataset | Cases | Recommended Chunk | Chunk Recall@1 | Best Method | Method Recall@1 | Method Recall@3 | Recommended Rerank Pool |
|---|---:|---|---:|---|---:|---:|---:|
| Chinese short contracts | 10 | 320 / 80 | 0.4000 | lexical / dense / hybrid tie | 0.4000 | 1.0000 | 2 |
| English short contracts | 10 | 900 / 150 | 0.7500 | hybrid + rerank | 0.7500 | 1.0000 | 1 |
| English long credit agreement | 6 | 480 / 120 | 0.1667 | lexical | 0.3333 | 0.5196 | 1 |
| Chinese long credit agreement | 4 | 240 / 60 | 0.1958 | hybrid + rerank | 0.1958 | 0.4208 | 4 |

## Method Comparison Details

| Dataset | Dense Recall@1 / @3 / @5 | Lexical Recall@1 / @3 / @5 | Hybrid+Rerank Recall@1 / @3 / @5 |
|---|---|---|---|
| Chinese short contracts | 0.4000 / 1.0000 / 1.0000 | 0.4000 / 1.0000 / 1.0000 | 0.4000 / 1.0000 / 1.0000 |
| English short contracts | 0.5000 / 1.0000 / 1.0000 | 0.0500 / 1.0000 / 1.0000 | 0.7500 / 1.0000 / 1.0000 |
| English long credit agreement | 0.1667 / 0.3333 / 0.5000 | 0.3333 / 0.5196 / 0.5294 | 0.1667 / 0.1667 / 0.1667 |
| Chinese long credit agreement | 0.0619 / 0.2696 / 0.3696 | 0.2077 / 0.4655 / 0.5393 | 0.1958 / 0.4208 / 0.6786 |
## Rerank Comparison

| Dataset | Pool 1 | Pool 2 | Pool 4 |
|---|---|---|---|
| Chinese short contracts | Recall@1 0.4000, latency 827.98 ms | Recall@1 0.4000, latency 399.37 ms | Recall@1 0.4000, latency 364.45 ms | 
| English short contracts | Recall@1 0.7500, latency 1142.65 ms | Recall@1 0.7500, latency 1145.34 ms | Recall@1 0.7500, latency 1156.92 ms |
| English long credit agreement | Recall@5 0.3431, latency 3228.15 ms | Recall@5 0.1765, latency 3869.33 ms | Recall@5 0.1667, latency 6095.89 ms |
| Chinese long credit agreement | Recall@5 0.5274, latency 3088.73 ms | Recall@5 0.5274, latency 3625.96 ms | Recall@5 0.6786, latency 4753.70 ms | 
