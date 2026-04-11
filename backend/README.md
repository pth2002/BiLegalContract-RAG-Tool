# Contract Review Tool - AI 合同智能审查工具

本地 AI 驱动的合同审查工具，使用 Ollama (Qwen3:8b) 进行智能风险分析。

## 功能特性

### 核心功能
- **文档上传**: 支持 PDF 和 DOCX 格式的合同文件
- **AI 风险分析**: 使用本地大语言模型识别合同中的潜在风险
- **双视角审查**: 支持甲方视角和乙方视角两种分析视角
- **风险详情展示**: 高/中/低三级风险分类，详细的条款分析和修改建议
- **智能建议优化**: 支持自然语言指令优化修改建议
- **报告导出**: 生成 DOCX/Markdown 格式的审查报告

### 技术特点
- **本地部署**: 完全本地运行，无需上传文件到第三方服务
- **隐私安全**: 合同文件仅在本地处理，保护敏感信息
- **实时流式输出**: 使用 Server-Sent Events (SSE) 实时展示分析进度
- **现代化前端**: React + TypeScript + Tailwind CSS

## 项目结构

```
contract/
├── backend/                 # FastAPI 后端
│   ├── src/
│   │   ├── main.py         # FastAPI 应用入口
│   │   ├── api/
│   │   │   └── routes.py   # API 路由定义
│   │   ├── models/         # Pydantic 数据模型
│   │   │   ├── enums.py    # 枚举类型定义
│   │   │   ├── document.py # 文档相关模型
│   │   │   ├── risk.py     # 风险相关模型
│   │   │   └── analysis.py # 分析相关模型
│   │   └── services/       # 业务逻辑服务
│   │       ├── parser_service.py      # 文档解析
│   │       ├── ollama_service.py      # Ollama AI 服务
│   │       ├── analyzer_service.py    # 分析服务
│   │       ├── prompt_service.py      # 提示词服务
│   │       ├── stream_service.py      # SSE 流式服务
│   │       ├── export_service.py      # 导出服务
│   │       └── refine_service.py      # 建议优化服务
│   ├── requirements.txt    # Python 依赖
│   └── pyproject.toml      # 项目配置
│
└── frontend/              # React 前端
    ├── src/
    │   ├── components/     # React 组件
    │   ├── services/       # API 调用服务
    │   ├── types/         # TypeScript 类型定义
    │   └── App.tsx        # 主应用组件
    └── package.json
```

## 快速开始

### 前置要求

- **Python 3.11+**
- **Node.js 18+**
- **Ollama**: 确保已安装并运行 Qwen3:8b 模型

### 安装 Ollama

```bash
# 安装 Ollama (macOS)
brew install ollama

# 启动 Ollama 服务
ollama serve

# 拉取 Qwen3:8b 模型 (约 5GB)
ollama pull qwen3:8b
```

### 后端安装

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或: .\venv\Scripts\activate  # Windows

# 安装依赖 (使用清华镜像)
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 配置环境变量（可选）
cp .env.example .env
# 编辑 .env 文件修改配置

# 启动开发服务器
python -m src.main

# 服务将在 http://localhost:8000 启动
```

### 环境变量配置

项目支持通过 `.env` 文件配置参数。复制 `.env.example` 为 `.env` 并修改：

```bash
cd backend
cp .env.example .env
```

常用配置项：

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `OLLAMA_HOST` | http://localhost:11434 | Ollama 服务地址 |
| `OLLAMA_MODEL` | qwen3:8b | 使用的 AI 模型 |
| `LLM_TEMPERATURE` | 0.1 | 模型温度（0-1）|
| `LOG_LEVEL` | DEBUG | 日志级别 |

### 前端安装

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 前端将在 http://localhost:5173 启动
```

## API 文档

### 端点列表

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/api/perspectives` | 获取分析视角列表 |
| POST | `/api/documents/upload` | 上传合同文档 |
| GET | `/api/documents/{document_id}` | 获取文档信息 |
| DELETE | `/api/documents/{document_id}` | 删除文档 |
| POST | `/api/analyze/stream` | 流式分析文档 (SSE) |
| POST | `/api/risks/{risk_id}/refine` | 优化风险建议 |
| POST | `/api/export` | 导出分析报告 |

### API 详情

#### 获取分析视角

```http
GET /api/perspectives
```

响应示例:
```json
{
  "perspectives": [
    {
      "id": "party_a",
      "name": "甲方视角",
      "description": "从甲方（委托方）利益出发审查合同",
      "focus_areas": ["对方违约风险", "赔偿条款", "权益保护", "履约担保"]
    },
    {
      "id": "party_b",
      "name": "乙方视角",
      "description": "从乙方（受托方）利益出发审查合同",
      "focus_areas": ["责任边界", "免责条款", "付款条件", "终止条款"]
    }
  ]
}
```

#### 上传文档

```http
POST /api/documents/upload
Content-Type: multipart/form-data

file: [文件]
session_id: [会话ID]
```

响应示例:
```json
{
  "document": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "filename": "合同.pdf",
    "file_type": "pdf",
    "file_size": 1048576,
    "page_count": 12,
    "text_content": "合同正文...",
    "uploaded_at": "2026-02-10T10:30:00Z",
    "session_id": "sess_abc123",
    "analyses": {}
  },
  "message": "Document uploaded successfully"
}
```

#### 流式分析

```http
POST /api/analyze/stream
Content-Type: application/json

{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "perspective": "party_a"
}
```

SSE 事件类型:
- `status`: 分析状态更新
- `risk`: 发现新风险
- `summary`: 分析总结
- `done`: 分析完成

#### 优化建议

```http
POST /api/risks/risk_001/refine
Content-Type: application/json

{
  "instruction": "语气更委婉",
  "original_risk_id": "risk_001"
}
```

#### 导出报告

```http
POST /api/export
?document_id=xxx
&perspective=party_a
&format=markdown
&include_risks=true
&include_summary=true
```

## 配置

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OLLAMA_HOST` | Ollama 服务地址 | `http://localhost:11434` |
| `DEFAULT_MODEL` | 默认使用模型 | `qwen3:8b` |

### 模型配置

当前配置使用 Qwen3:8b 模型，具有以下特点:
- 8B 参数规模
- 中文优化
- 适合合同分析任务


### 生产环境

1. 构建前端:
```bash
cd frontend
npm run build
```

2. 配置 Nginx 或其他 Web 服务器提供静态文件

3. 使用 uvicorn 启动后端:
```bash
cd backend
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 常见问题

### Ollama 无法连接

```bash
# 检查 Ollama 服务状态
ollama list

# 启动 Ollama
ollama serve

# 拉取模型
ollama pull qwen3:8b
```

### 文档解析失败

- 确保文件是有效的 PDF 或 DOCX 格式
- PDF 文件大小限制: 2MB
- DOCX 文件大小限制: 5MB
- PDF 页数限制: 20 页

### 内存不足

Qwen3:8b 需要约 6GB 内存运行。如遇内存问题:
- 考虑使用更小的模型如 `qwen3:4b`
- 关闭其他占用内存的程序

## License

MIT License

## Offline Benchmark

可使用离线检索评测脚本对 chunk 策略、召回方式和 rerank pool size 做实验，不影响主业务逻辑：

```bash
cd backend
python -m src.tooling.run_retrieval_benchmark
```

默认会读取 `backend/data/retrieval_benchmark_cases.json`，并输出：

- `data/eval/retrieval_benchmark_report.md`
- `data/eval/retrieval_benchmark_report.json`

可选参数示例：

```bash
python -m src.tooling.run_retrieval_benchmark --chunk-configs 160:40,240:60,320:80
python -m src.tooling.run_retrieval_benchmark --methods dense,lexical,hybrid
python -m src.tooling.run_retrieval_benchmark --rerank-pool-mults 1,2,4
```

## Retrieval V2 Defaults

The current default project behavior uses the second-generation retrieval pipeline.

- Multi-query hybrid retrieval remains the default.
- Coarse recall was expanded before reranking.
- Lexical scoring is now BM25-like rather than simple token overlap.
- Low-value chunk filtering is enabled before and after rerank.

Default retrieval parameters in code/config are:

- `RETRIEVER_TOP_K=8`
- `HYBRID_RETRIEVAL_ENABLED=true`
- `HYBRID_RRF_K=60`
- `COARSE_RECALL_MULT=6`
- `COARSE_RECALL_MAX_PER_QUERY=24`
- `RETRIEVAL_FILTER_ENABLED=true`
- `RETRIEVAL_FILTER_MIN_CHARS=80`
- `RERANK_ENABLED=true`
- `RERANK_MODEL=BAAI/bge-reranker-base`
- `RERANK_BATCH_SIZE=8`
- `RERANK_POOL_MULT=4`

The benchmark and runtime retrieval path are aligned through `src/services/retrieval_service.py`, so the V2 benchmark behavior matches the current default retrieval implementation.

## Upload Policy

The current upload flow no longer enforces hard PDF/DOCX size limits or a fixed PDF page-count limit.

- Short and long contract documents can both be uploaded.
- The main tradeoff for larger files is local parsing, embedding, and retrieval latency.
- Supported upload formats remain PDF and DOCX.
