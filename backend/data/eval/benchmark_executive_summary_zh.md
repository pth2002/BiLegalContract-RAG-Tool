# 检索实验总表

## 一页 Summary

| 实验集 | 语言/文档长度 | Case 数 | 推荐 Chunk | 推荐方法 | 推荐 Rerank Pool | 最佳 Top1 指标 | 最佳 Top3 指标 | 最佳 Top5 指标 | 结论一句话 |
|---|---|---:|---|---|---:|---:|---:|---:|---|
| 中文短合同 | 中文 / 短 | 10 | 320 / 80 | 无明显差异 | 2 | 0.4000 | 1.0000 | 1.0000 | 短中文合同任务较容易，三种方法在 Top3 以后几乎全部拉满。 |
| 英文短合同 | 英文 / 短 | 10 | 900 / 150 | Hybrid + Rerank | 1 | 0.7500 | 1.0000 | 1.0000 | 英文短文本里，显式英文 query 加 rerank 能明显抬升 Top1 排序。 |
| 英文长信用协议 | 英文 / 长 | 6 | 480 / 120 | Lexical | 1 | 0.3333 | 0.5196 | 0.5294 | 长英文法律合同把默认 query 策略的短板放大了，lexical 锚点最稳。 |
| 中文长信用协议 | 中文 / 长 | 4 | 240 / 60 | Hybrid | 4 | 0.2077 | 0.4655 | 0.6786 | 中文长合同里 lexical 的 Top1/Top3 更强，但 hybrid + rerank 的 Top5 覆盖最好。 |

注：
- 全部实验当前都跑在 `local vector store fallback` 上，不是 `pgvector`。
- Top1 / Top3 / Top5 列展示的是该实验集里“最能代表结论”的最优指标，不一定全部来自同一种方法。

## 方法对比表

| 实验集 | Dense (`R@1 / R@3 / R@5`) | Lexical (`R@1 / R@3 / R@5`) | Hybrid + Rerank (`R@1 / R@3 / R@5`) | 最适合怎么讲 |
|---|---|---|---|---|
| 中文短合同 | 0.4000 / 1.0000 / 1.0000 | 0.4000 / 1.0000 / 1.0000 | 0.4000 / 1.0000 / 1.0000 | 这组主要证明链路跑通，样本太短，难以拉开方法差异。 |
| 英文短合同 | 0.5000 / 1.0000 / 1.0000 | 0.0500 / 1.0000 / 1.0000 | 0.7500 / 1.0000 / 1.0000 | 英文显式 query 配合 rerank 能明显优化 Top1。 |
| 英文长信用协议 | 0.1667 / 0.3333 / 0.5000 | 0.3333 / 0.5196 / 0.5294 | 0.1667 / 0.1667 / 0.1667 | 长英文法务文本里，lexical 比 dense / hybrid 更可靠。 |
| 中文长信用协议 | 0.0619 / 0.2696 / 0.3696 | 0.2077 / 0.4655 / 0.5393 | 0.1958 / 0.4208 / 0.6786 | 中文长文档里 lexical 负责精准命中，hybrid 负责扩大证据覆盖。 |

## Rerank 效果表

| 实验集 | Pool = 1 | Pool = 2 | Pool = 4 | 结论 |
|---|---|---|---|---|
| 中文短合同 | `R@1 0.4000` / `827.98 ms` | `R@1 0.4000` / `399.37 ms` | `R@1 0.4000` / `364.45 ms` | 样本太短，pool size 几乎不影响结果。 |
| 英文短合同 | `R@1 0.7500` / `1142.65 ms` | `R@1 0.7500` / `1145.34 ms` | `R@1 0.7500` / `1156.92 ms` | 结果稳定，`pool=1` 成本最低。 |
| 英文长信用协议 | `R@5 0.3431` / `3228.15 ms` | `R@5 0.1765` / `3869.33 ms` | `R@5 0.1667` / `6095.89 ms` | 英文长合同里，pool 越大越慢，而且效果更差。 |
| 中文长信用协议 | `R@5 0.5274` / `3088.73 ms` | `R@5 0.5274` / `3625.96 ms` | `R@5 0.6786` / `4753.70 ms` | 中文长合同里更大的 rerank pool 能换来更高 Top5 覆盖。 |

## 面试结论

| 问题 | 最稳回答 |
|---|---|
| 为什么短合同结果都很好？ | 候选 chunk 很少，检索空间小，Top3 很容易覆盖到 gold evidence。 |
| 为什么长合同结果明显变差？ | 候选空间从个位数上升到几百上千块，条款密度更高，排序误差被放大。 |
| 为什么英文长合同 lexical 最强？ | 这份英文信贷协议的条款锚点词非常强，而当前默认 query / hybrid 设计更偏中文合同审查语境。 |
| 为什么中文长合同 hybrid 又变好了？ | 中文长合同更贴近项目本来的 query 设计，dense 能补语义召回，lexical 能补精确命中，二者融合后 Top5 证据覆盖更完整。 |
| rerank 一定有用吗？ | 不一定。短文本里可能不明显，长英文合同里甚至可能变差，但在中文长文档上它能提高证据覆盖。 |

## 原始报告

- 中文短合同：
  [retrieval_benchmark_report.md](D:/AI%20agent%20rag%20%E5%90%88%E5%90%8C%E9%A1%B9%E7%9B%AE/contract/backend/data/eval/retrieval_benchmark_report.md)
- 英文短合同：
  [retrieval_benchmark_report.md](D:/AI%20agent%20rag%20%E5%90%88%E5%90%8C%E9%A1%B9%E7%9B%AE/contract/backend/data/eval/en_short_contracts/retrieval_benchmark_report.md)
- 英文长合同：
  [retrieval_benchmark_report.md](D:/AI%20agent%20rag%20%E5%90%88%E5%90%8C%E9%A1%B9%E7%9B%AE/contract/backend/data/eval/long_credit_agreement/retrieval_benchmark_report.md)
- 中文长合同：
  [retrieval_benchmark_report.md](D:/AI%20agent%20rag%20%E5%90%88%E5%90%8C%E9%A1%B9%E7%9B%AE/contract/backend/data/eval/long_credit_agreement_zh/retrieval_benchmark_report.md)
