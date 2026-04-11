# 基于RAG+Agent的超长合同分析工具

基于 RAG（检索增强生成）的合同智能审查系统，支持中英双语合同分析。系统采用混合检索 + 交叉编码重排 + 多轮 Agentic 推理，并通过 gpt-4o 端到端评测验证生成质量。

---

## 功能特性

- **混合检索**：密集向量（bge-large-zh-v1.5 1024维）+ 词法匹配（BM25）+ RRF 融合，支持语言路由
- **交叉编码重排**：BAAI/bge-reranker-large 精排，pool_mult=4 扩大候选召回
- **Agentic 推理循环**：Critic + Reflection 双自评估，工具注册表（ensure_index / retrieve_context / analyze_risks）
- **多语言支持**：中文 / 英文 / 双语合同，按语言路由检索模型
- **前后端分离**：FastAPI + asyncpg 后端，React / TypeScript / Vite 前端
- **pgvector 向量存储**：ivfflat 索引，本地 JSON 自动降级备用

---

## 评测结果

### 检索层（Recall@5）

| 配置 | zh | en | bilingual | Macro R@5 | P50 延迟 |
|------|----|----|-----------|-----------|---------|
| 基线（rr-base, probes=50） | 0.3222 | 0.5591 | 0.2500 | 0.3804 | 230 ms |
| 最优（rr-large, probes=100） | 0.3556 | 0.6424 | 0.3929 | **0.4534** | 691 ms |

> 基准测试：32 cases（zh=15 / en=10 / bilingual=7），混合检索 chunk=900:150，top-k=8

### 端到端生成层（gpt-4o 评审，1–5 分）

| 维度 | zh (15) | en (10) | bilingual (7) | Macro |
|------|---------|---------|---------------|-------|
| Faithfulness（忠实度） | 4.20 | 5.00 | 3.86 | **4.38** |
| Completeness（完整度） | 3.07 | 4.10 | 3.71 | **3.53** |

**检索命中 vs 未命中对比（32 cases）：**

| 分组 | Faithfulness | Completeness |
|------|-------------|-------------|
| 检索命中（20 cases） | 5.0 | 4.4 |
| 检索未命中（12 cases） | 3.33 | 2.08 |

结论：检索质量是生成质量的决定性因素，Completeness 差距（4.4 vs 2.1）是最强信号。

---

## 系统架构

```
前端 (React/Vite)
    └── FastAPI 后端
         ├── AgentRuntime（Agentic 推理循环）
         │    ├── OrchestratorAgent（任务分解 + 工具调用）
         │    ├── CriticAgent（质量评估）
         │    └── ReflectionAgent（自我反思）
         ├── 检索服务
         │    ├── 密集检索（bge-large-zh-v1.5 + pgvector）
         │    ├── 词法检索（BM25）
         │    └── 重排（bge-reranker-large）
         └── 索引服务
              ├── PDF / DOCX 解析
              ├── 语义分块（chunk=900:150）
              └── upsert → pgvector
```

---

## 快速开始

### 前置条件

- Python 3.10+
- Node.js 18+
- PostgreSQL 15+ with pgvector 扩展
- （可选）GPU：RTX 4060+ 用于本地 embedding 加速（约 10.5x）

### 1. 数据库初始化

```bash
psql -U postgres -c "CREATE USER agent WITH PASSWORD 'your_password';"
psql -U postgres -c "CREATE DATABASE contract_rag OWNER agent;"
psql -U postgres -c "CREATE DATABASE contract_agent OWNER agent;"
psql -U agent -d contract_rag -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 2. 后端配置

```bash
cd backend
cp .env.example .env
# 编辑 .env，填入实际数据库密码和 OPENAI_API_KEY
```

### 3. 下载模型（首次）

```bash
pip install huggingface_hub
python - << 'EOF'
from huggingface_hub import snapshot_download
snapshot_download("BAAI/bge-large-zh-v1.5", local_dir="data/hf_cache/hub/bge-large")
snapshot_download("BAAI/bge-reranker-large", local_dir="data/hf_cache/hub/bge-reranker-large")
EOF
```

### 4. 启动后端

```bash
cd backend
pip install -r requirements.txt
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:5173` 上传合同文件开始分析。

---

## 运行评测

### 检索层 benchmark

```bash
cd backend
python -m src.tooling.run_retrieval_benchmark
```

### 端到端 benchmark（需要 OpenAI API Key）

```bash
cd backend
python src/tooling/run_e2e_benchmark.py \
    --api-key sk-your-key \
    --cases-file data/retrieval_benchmark_cases_v2.json \
    --output-dir benchmarks/
```

---

## 环境变量说明

参见 [`backend/.env.example`](backend/.env.example)。关键参数：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PGVECTOR_PROBES` | 100 | ivfflat 查询探针数，影响召回率与延迟 |
| `RERANK_POOL_MULT` | 4 | 重排候选扩倍数（top-k × pool_mult） |
| `RETRIEVER_TOP_K` | 8 | 最终返回 chunks 数量 |
| `RERANK_MODEL` | BAAI/bge-reranker-large | 交叉编码重排模型 |
| `HF_HUB_OFFLINE` | 1 | 离线模式，避免运行时联网 |

---

## 项目结构

```
contract/
├── backend/
│   ├── src/
│   │   ├── agents/          # AgentRuntime, OrchestratorAgent, Critic, Reflection
│   │   ├── services/        # vector_store, indexing, reranking, db
│   │   ├── tooling/         # run_e2e_benchmark.py, run_retrieval_benchmark.py
│   │   └── main.py          # FastAPI 入口
│   ├── benchmarks/          # 评测结果（md + json）
│   ├── data/
│   │   └── retrieval_benchmark_cases_v2.json  # 32 cases 基准测试集
│   └── .env.example
└── frontend/
    └── src/                 # React + TypeScript + Vite
```

---

## 许可证

MIT
