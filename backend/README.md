# Backend — Contract Review RAG

总后端，包含完整的检索、重排、Agent 推理和离线评测管线。

## 目录结构

```
backend/
├── src/
│   ├── main.py                  # FastAPI 入口
│   ├── api/routes.py            # REST + SSE 路由
│   ├── agents/                  # Agentic 推理
│   │   ├── agent_runtime.py     # 推理循环主控
│   │   ├── orchestrator_agent.py
│   │   ├── critic_agent.py      # 质量评估
│   │   ├── reflection_agent.py  # 自我反思
│   │   └── vector_memory.py     # 向量记忆
│   ├── services/                # 核心服务
│   │   ├── parser_service.py    # PDF/DOCX → DocumentBlock
│   │   ├── chunking_service.py  # 语义分块（中文 500:100 / 英文 900:150）
│   │   ├── embedding_service.py # bge-large-zh-v1.5，支持模型切换
│   │   ├── indexing_service.py  # pgvector 索引
│   │   ├── retrieval_service.py # multi-query + hybrid + RRF + 语种路由
│   │   ├── reranking_service.py # cross-encoder 重排
│   │   └── vector_store_service.py  # pgvector 读写 + ivfflat probes 调优
│   └── tooling/                 # 离线评测工具
│       ├── run_retrieval_benchmark.py  # 检索层 benchmark
│       └── run_e2e_benchmark.py        # 端到端 LLM-as-Judge
├── benchmarks/                  # 评测报告（md + json）
├── data/
│   └── retrieval_benchmark_cases_v2.json  # 32-case 评测集
├── .env.example
├── requirements.txt
└── pyproject.toml
```

## 环境搭建

### 1. 数据库

需要 PostgreSQL 15+ 和 pgvector 扩展：

```bash
psql -U postgres -c "CREATE USER agent WITH PASSWORD 'agent123';"
psql -U postgres -c "CREATE DATABASE contract_rag OWNER agent;"
psql -U postgres -c "CREATE DATABASE contract_agent OWNER agent;"
psql -U agent -d contract_rag -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 2. Python 依赖

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 3. 配置

```bash
cp .env.example .env
# 编辑 .env，填入数据库密码和 API Key
```

关键配置项见 `.env.example`，核心参数：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | pgvector 连接串 | — |
| `RERANK_MODEL` | 重排模型 | `BAAI/bge-reranker-large` |
| `PGVECTOR_PROBES` | ivfflat 扫描范围 | `100` |
| `RETRIEVER_TOP_K` | 最终返回 top-k | `8` |
| `RERANK_POOL_MULT` | 重排候选池倍数 | `4` |

### 4. 启动

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

## API 端点

| 方法 | 路径 | 描述 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/api/documents/upload` | 上传合同（PDF/DOCX） |
| `POST` | `/api/analyze/stream` | 流式分析（SSE） |
| `POST` | `/api/risks/{id}/refine` | 自然语言优化建议 |
| `POST` | `/api/export` | 导出报告（DOCX/Markdown） |

完整 API 文档启动后访问 `http://localhost:8000/docs`。

## 运行评测

### 检索层 benchmark

```bash
python -m src.tooling.run_retrieval_benchmark
# 输出 → benchmarks/retrieval_benchmark_report.{md,json}
```

可选参数：
```bash
--chunk-configs 500:100,900:150
--methods dense,lexical,hybrid
--rerank-pool-mults 1,2,4
```

### 端到端 benchmark

```bash
python src/tooling/run_e2e_benchmark.py \
    --cases-file data/retrieval_benchmark_cases_v2.json \
    --output-dir benchmarks/
```

## License

MIT
