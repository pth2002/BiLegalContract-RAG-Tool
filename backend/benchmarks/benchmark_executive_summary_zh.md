# 检索实验总表

## Summary

| 实验集 | 语言/文档长度 | Case 数 | 推荐 Chunk | 推荐方法 | 推荐 Rerank Pool | 最佳 Top1 指标 | 最佳 Top3 指标 | 最佳 Top5 指标 | 
|---|---|---:|---|---|---:|---:|---:|---:|
| 中文短合同 | 中文 / 短 | 10 | 320 / 80 | 无明显差异 | 2 | 0.4000 | 1.0000 | 1.0000 | 
| 英文短合同 | 英文 / 短 | 10 | 900 / 150 | Hybrid + Rerank | 1 | 0.7500 | 1.0000 | 1.0000 | 
| 英文长信用协议 | 英文 / 长 | 6 | 480 / 120 | Lexical | 1 | 0.3333 | 0.5196 | 0.5294 |
| 中文长信用协议 | 中文 / 长 | 4 | 240 / 60 | Hybrid | 4 | 0.2077 | 0.4655 | 0.6786 |

## 方法对比表

| 实验集 | Dense (`R@1 / R@3 / R@5`) | Lexical (`R@1 / R@3 / R@5`) | Hybrid + Rerank (`R@1 / R@3 / R@5`) |
|---|---|---|---|
| 中文短合同 | 0.4000 / 1.0000 / 1.0000 | 0.4000 / 1.0000 / 1.0000 | 0.4000 / 1.0000 / 1.0000 |
| 英文短合同 | 0.5000 / 1.0000 / 1.0000 | 0.0500 / 1.0000 / 1.0000 | 0.7500 / 1.0000 / 1.0000 | 
| 英文长信用协议 | 0.1667 / 0.3333 / 0.5000 | 0.3333 / 0.5196 / 0.5294 | 0.1667 / 0.1667 / 0.1667 | 
| 中文长信用协议 | 0.0619 / 0.2696 / 0.3696 | 0.2077 / 0.4655 / 0.5393 | 0.1958 / 0.4208 / 0.6786 | 

## Rerank 效果表

| 实验集 | Pool = 1 | Pool = 2 | Pool = 4 | 
|---|---|---|---|
| 中文短合同 | `R@1 0.4000` / `827.98 ms` | `R@1 0.4000` / `399.37 ms` | `R@1 0.4000` / `364.45 ms` | 
| 英文短合同 | `R@1 0.7500` / `1142.65 ms` | `R@1 0.7500` / `1145.34 ms` | `R@1 0.7500` / `1156.92 ms` | 
| 英文长信用协议 | `R@5 0.3431` / `3228.15 ms` | `R@5 0.1765` / `3869.33 ms` | `R@5 0.1667` / `6095.89 ms` | 
| 中文长信用协议 | `R@5 0.5274` / `3088.73 ms` | `R@5 0.5274` / `3625.96 ms` | `R@5 0.6786` / `4753.70 ms` | 

## 原始报告

- 中文短合同：
  [retrieval_benchmark_report.md](D:/AI%20agent%20rag%20%E5%90%88%E5%90%8C%E9%A1%B9%E7%9B%AE/contract/backend/data/eval/retrieval_benchmark_report.md)
- 英文短合同：
  [retrieval_benchmark_report.md](D:/AI%20agent%20rag%20%E5%90%88%E5%90%8C%E9%A1%B9%E7%9B%AE/contract/backend/data/eval/en_short_contracts/retrieval_benchmark_report.md)
- 英文长合同：
  [retrieval_benchmark_report.md](D:/AI%20agent%20rag%20%E5%90%88%E5%90%8C%E9%A1%B9%E7%9B%AE/contract/backend/data/eval/long_credit_agreement/retrieval_benchmark_report.md)
- 中文长合同：
  [retrieval_benchmark_report.md](D:/AI%20agent%20rag%20%E5%90%88%E5%90%8C%E9%A1%B9%E7%9B%AE/contract/backend/data/eval/long_credit_agreement_zh/retrieval_benchmark_report.md)
