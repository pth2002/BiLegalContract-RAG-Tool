# Contract Review Frontend - React 前端

合同智能审查工具的前端界面，使用 React + TypeScript + Tailwind CSS 构建。

## 功能模块

### 1. 文档上传 (DocumentUpload)
- 拖拽上传 PDF/DOCX 文件
- 文件格式验证
- 上传进度展示

### 2. 视角切换 (PerspectiveSwitch)
- 甲方视角：关注违约风险、赔偿条款、权益保护
- 乙方视角：关注责任边界、免责条款、付款条件

### 3. 风险卡片 (RiskCard)
- 高/中/低三级风险等级
- 条款原文展示
- 风险描述和修改建议

### 4. 视角对比 (PerspectiveCompare)
- 并排对比两个视角的分析结果
- 差异化展示风险点

### 5. 建议优化 (RefinementInput)
- 自然语言指令优化建议
- 修改建议对比展示

### 6. 导出功能 (ExportButton)
- Markdown 格式报告导出
- 支持自定义导出内容

## 安装与运行

### 前置要求
- Node.js 18+
- npm 或 yarn

### 安装依赖

```bash
cd frontend

# 使用 npm
npm install

# 或使用 yarn
yarn install
```

### 开发模式

```bash
npm run dev
```

前端将在 http://localhost:5173 启动。

### 构建生产版本

```bash
npm run build
```

构建产物将输出到 `dist/` 目录。

## 项目结构

```
frontend/
├── src/
│   ├── components/           # React 组件
│   │   ├── DocumentUpload.tsx    # 文档上传
│   │   ├── PerspectiveSwitch.tsx # 视角切换
│   │   ├── PerspectiveCompare.tsx # 视角对比
│   │   ├── RiskCard.tsx         # 风险卡片
│   │   ├── RiskCardList.tsx     # 风险列表
│   │   ├── RiskDetailModal.tsx   # 风险详情弹窗
│   │   ├── SuggestionDiff.tsx    # 建议对比
│   │   ├── RefinementInput.tsx   # 建议优化输入
│   │   └── ExportButton.tsx      # 导出按钮
│   │
│   ├── services/             # API 服务
│   │   └── api.ts            # API 调用封装
│   │
│   ├── types/                # TypeScript 类型
│   │   └── index.ts          # 类型定义
│   │
│   ├── App.tsx              # 主应用组件
│   └── main.tsx             # 应用入口
│
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

## API 服务

所有 API 调用封装在 `src/services/api.ts` 中：

```typescript
// 上传文档
const response = await api.uploadDocument(file, sessionId);

// 获取视角列表
const { perspectives } = await api.getPerspectives();

// 流式分析
const stream = await api.analyzeDocument(documentId, perspective);

// 优化建议
const refined = await api.refineRisk(riskId, instruction);

// 导出报告
await api.exportReport(documentId, perspective, format);
```

## 类型定义

### 核心类型

```typescript
// 风险等级
type Severity = '高' | '中' | '低';

// 风险类别
type RiskCategory = '经济利益' | '交付风险' | '责任边界' | '知识产权' | '合规要求';

// 视角类型
type PerspectiveType = 'party_a' | 'party_b';

// 风险卡片
interface RiskCard {
  id: string;
  clause_title: string;
  severity: Severity;
  risk_category: RiskCategory;
  original_text: string;
  risk_description: string;
  suggested_revision: string;
}

// 文档
interface Document {
  id: string;
  filename: string;
  file_type: 'pdf' | 'docx';
  file_size: number;
  page_count: number;
  text_content: string;
  analyses: Record<PerspectiveType, DocumentAnalysis>;
}

// 分析结果
interface DocumentAnalysis {
  perspective: PerspectiveType;
  risks: RiskCard[];
  summary: string;
  analyzed_at: string;
  duration_ms: number;
}

// 视角信息
interface PerspectiveInfo {
  id: PerspectiveType;
  name: string;
  description: string;
  focus_areas: string[];
}
```

## Tailwind CSS 配置

自定义颜色和设计令牌：

```javascript
// tailwind.config.js
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        risk: {
          high: '#ef4444',
          medium: '#f59e0b',
          low: '#22c55e',
        }
      }
    }
  },
  plugins: [],
}
```

## 开发命令

| 命令 | 描述 |
|------|------|
| `npm run dev` | 启动开发服务器 |
| `npm run build` | 构建生产版本 |
| `npm run preview` | 预览构建产物 |
| `npm run lint` | 代码检查 |

## 代码风格

- 使用 ESLint 进行代码检查
- TypeScript 严格模式
- React Hooks 最佳实践
- Tailwind CSS 原子化类名

## 依赖说明

| 依赖 | 用途 |
|------|------|
| `react` | UI 框架 |
| `react-dom` | DOM 渲染 |
| `axios` | HTTP 客户端 |
| `framer-motion` | 动画效果 |
| `react-dropzone` | 拖拽上传 |
| `tailwindcss` | 样式框架 |
| `typescript` | 类型安全 |
| `vite` | 构建工具 |
