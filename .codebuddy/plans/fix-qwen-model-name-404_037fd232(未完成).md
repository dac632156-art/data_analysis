---
name: fix-qwen-model-name-404
overview: 修复阿里云百炼 API 返回 404 model_not_found 的问题：前端拦截器将 Qwen3.7-Plus 转小写为 qwen3.7-plus，但阿里云不存在此模型。需在拦截器中添加模型名映射校正逻辑。
todos:
  - id: add-model-normalize
    content: 在 client.ts 拦截器中添加 normalizeModelName 函数并调用
    status: pending
  - id: update-sidebar-hint
    content: 在 Sidebar.tsx 模型名输入框提示中补充可用模型名参考
    status: pending
---

## 核心需求

修复阿里云百炼 API 返回 404 `model_not_found` 的问题。用户在侧边栏"模型名称"输入框填写了 `Qwen3.7-Plus`（或其他带版本号的模型名），经前端拦截器小写化后变成 `qwen3.7-plus`，而阿里云百炼不存在该模型 ID，导致 API 报错。

## 功能内容

在前端 API 拦截器中，小写化之后追加模型名映射校正步骤，将带版本号的 qwen 模型名（如 `qwen3.7-plus`、`qwen2.5-max`）自动映射为阿里云百炼当前有效的模型 ID（`qwen-plus`、`qwen-max`、`qwen-turbo`）。同时在侧边栏提示文案中补充常用模型名列表，减少用户误填。

## 视觉效果

侧边栏"模型名称"输入框下方提示文案增加一行可用模型名参考，帮助用户正确填写。

## 技术栈

- 前端：React + TypeScript（项目现有技术栈）
- 修改范围：纯前端，不涉及后端

## 实现方案

在 `frontend/src/api/client.ts` 的请求拦截器中，在现有 `toLowerCase()` 之后追加一个 `normalizeModelName()` 函数调用。该函数用正则剥离 qwen 系列模型名中的版本号（如 `3.7`、`2.5`、`3`），将 `qwen3.7-plus` 映射为 `qwen-plus`，`qwen2.5-max` 映射为 `qwen-max` 等。对于非 qwen 的模型名不做处理，保持小写原值。

同时在 `Sidebar.tsx` 的提示文案中补充各服务商常用模型名列表。

### 修改文件清单

```
d:/数据分析项目/
├── frontend/src/api/client.ts       # [MODIFY] 在拦截器中添加 normalizeModelName() 映射函数，toLowerCase() 之后调用
├── frontend/src/components/Layout/Sidebar.tsx  # [MODIFY] 在"模型名称"输入框下方增加可用模型名参考提示
```

### 核心代码逻辑（normalizeModelName）

```typescript
function normalizeModelName(model: string): string {
  // qwen 系列：剥离版本号，qwen3.7-plus → qwen-plus, qwen2.5-max → qwen-max
  const qwenMatch = model.match(/^qwen[\d.]*-(plus|max|turbo|long)$/);
  if (qwenMatch) return `qwen-${qwenMatch[1]}`;
  // qwen 系列无后缀的版本号形式：qwen3.7 → qwen-plus（默认映射）
  if (/^qwen[\d.]+$/.test(model)) return 'qwen-plus';
  return model; // 其他模型名不做处理
}
```

### 实现要点

- 拦截器逻辑：`config.data.model = normalizeModelName(config.data.model.toLowerCase())`
- 正则只处理 qwen 系列，不影响 deepseek-chat、glm-4-flash 等其他模型名
- Sidebar 提示增加一行如"阿里云可用：qwen-plus / qwen-max / qwen-turbo"
- 注释更新：修正原有注释中 `qwen3.7-plus` 的错误示例（阿里云实际模型 ID 是 `qwen-plus`，不是 `qwen3.7-plus`）