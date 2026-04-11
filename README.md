# 基于RAG+Agent的超长合同分析工具

基于 RAG 的合同智能审查系统，支持中英双语合同分析。系统采用混合检索 + 交叉编码重排 + 多轮 Agentic 推理，并通过 gpt-4o 端到端评测验证生成质量。

---

## 功能特性

- **混合检索**：密集向量（bge-large-zh-v1.5）+ 词法匹配 + RRF 融合，支持语言路由
- **交叉编码重排**：BAAI/bge-reranker-large 精排，pool_mult=4 扩大候选召回
- **Agentic 推理循环**：Critic + Reflection 双自评估，利用工具注册表
- **多语言支持**：中文 / 英文 / 双语合同，按语言路由检索模型

---

## 评测结果

### Embedding 消融实验

在 reranker-large 下对比 bge-large-zh-v1.5 / bge-m3 / multilingual-e5-large 三个 embedding，固定 hybrid + pool_mult=4 + top-k=8。
结果三个模型的 Strict R@5 完全收敛至 0.4636，cross-encoder 从 top-32 候选重排后主导了最终排序。
据此选用模型最小、P50 最低（134ms）的 bge-large-zh-v1.5 作为生产配置。

### 检索层（Recall@5）

| 配置 | zh | en | bilingual | Macro R@5 | P50 延迟 |
|------|----|----|-----------|-----------|---------|
| 基线（rr-base, probes=50） | 0.3222 | 0.5591 | 0.2500 | 0.3804 | 230 ms |
| 最优（rr-large, probes=100） | 0.3556 | 0.6424 | 0.3929 | **0.4534** | 691 ms |

> 基准测试：32 cases（zh=15 / en=10 / bilingual=7，总case=32），混合检索 chunk=900:150，top-k=8

### 端到端生成层（gpt-4o 评审）

| 维度 | zh (15) | en (10) | bilingual (7) | Macro |
|------|---------|---------|---------------|-------|
| Faithfulness | 4.20 | 5.00 | 3.86 | **4.38** |
| Completeness | 3.07 | 4.10 | 3.71 | **3.53** |

**检索命中 vs 未命中对比（32 cases）：**

| 分组 | Faithfulness | Completeness |
|------|-------------|-------------|
| 检索命中（20 cases） | 5.0 | 4.4 |
| 检索未命中（12 cases） | 3.33 | 2.08 |


---

## 关键发现

- **Reranker 升级**：base → large 使 Macro R@5 从 0.38 提升至 0.46（+23%），双语组从 0.25 → 0.39（+57%），延迟仅增加 47ms
- **中文检索优化 +93%**：中文专用切块（500:100 按条款边界）+ 语种路由，中文 R@5 从 0.17 → 0.32
- **检索质量影响端到端质量**：检索命中的 case Completeness 平均 4.4，未命中仅 2.08，验证了检索层优化对最终生成质量的决定性影响
---

## 系统架构

```
前端 
    └── 后端
         ├── AgentRuntime（推理循环）
         │    ├── OrchestratorAgent（任务分解 + 工具调用）
         │    ├── CriticAgent（质量评估）
         │    └── ReflectionAgent（自我反思）
         ├── 检索服务
         │    ├── 密集检索（bge-large-zh-v1.5 + pgvector）
         │    ├── 词法检索
         │    └── 重排（reranker）
         └── 索引服务
              ├── PDF / DOCX 解析
              ├── 语义分块（chunk=900:150）
              └── pgvector
```

## 许可证

MIT
