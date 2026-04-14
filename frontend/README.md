# Frontend — Contract Review UI

React + TypeScript + Tailwind CSS，配合后端 API 提供合同审查交互界面。

## 功能

- 拖拽上传 PDF/DOCX 合同
- 甲方/乙方双视角风险分析（SSE 流式输出） 
- 高/中/低三级风险卡片展示
- 自然语言优化修改建议
- 导出 Markdown 审查报告

## 运行

```bash
npm install
npm run dev
# → http://localhost:5173
```

需要后端运行在 `http://localhost:8000`，详见 [backend/README.md](../backend/README.md)。
