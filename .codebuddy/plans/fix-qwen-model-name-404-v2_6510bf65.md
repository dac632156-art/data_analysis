---
name: fix-qwen-model-name-404-v2
overview: 修复阿里云百炼 qwen3.7-plus 模型返回 404 model_not_found 的问题。经确认 qwen3.7-plus 是百炼有效模型ID，问题可能来自：1) 旧域名 dashscope.aliyuncs.com 不支持新模型需换新域名; 2) API Key 未开通该模型; 3) 默认配置仍指向旧版 qwen-plus。修复方案：更新默认模型配置、增强提示信息、后端错误处理优化。
todos:
  - id: update-qwen-default-model
    content: 更新 DataContext.tsx 中 qwen 默认 model 为 qwen3.7-plus，修正 client.ts 拦截器注释
    status: completed
  - id: enhance-sidebar-hints
    content: 增强 Sidebar.tsx 模型名提示，补充可用模型列表和权限提醒
    status: completed
    dependencies:
      - update-qwen-default-model
  - id: enhance-backend-error
    content: 增强后端 4 个 router 的 model_not_found 错误提示，返回明确中文引导
    status: completed
---

## 产品概述

修复用户在使用阿里云百炼 `Qwen3.7-Plus` 模型时遇到 404 `model_not_found` 错误的问题。用户确认百炼平台确实有此模型。

## 核心功能

- 更新 AI_PROVIDERS 中阿里云通义千问的默认模型为 `qwen3.7-plus`（跟上百炼最新版本）
- 后端对 model_not_found 错误给出更明确的中文提示，区分"模型不存在"和"没有访问权限"
- 侧边栏补充各服务商可用模型名参考和权限开通提醒
- 修正前端拦截器注释中的错误示例

## 技术栈

- 前端：React + TypeScript（项目现有技术栈）
- 后端：Python + FastAPI + OpenAI SDK（项目现有技术栈）
- 修改范围：前端 3 文件 + 后端 1 文件

## 实现方案

### 根因确认

经官方文档（2026-06-30）确认：`qwen3.7-plus` 是百炼有效模型 ID，百炼的 `model_not_found` 错误同时覆盖"模型不存在"和"没有访问权限"两种情况。用户遇到 404 最可能的原因是：

1. AI_PROVIDERS 默认 qwen 模型为旧版 `qwen-plus`，未跟上最新版本
2. 用户的 API Key 可能未在百炼控制台开通 `qwen3.7-plus` 模型权限
3. 百炼新旧域名差异：旧域名 `dashscope.aliyuncs.com` 对新模型可能有延迟或限制

### 修改策略

1. **前端 DataContext.tsx**：将 qwen 默认 model 从 `qwen-plus` 升级为 `qwen3.7-plus`
2. **前端 client.ts**：修正拦截器注释中的错误示例，保留小写转换逻辑
3. **前端 Sidebar.tsx**：在模型名输入框下方增加可用模型名参考 + 权限开通提醒
4. **后端多个 router**：在 AI 调用失败时捕获 `model_not_found` / 404 错误，返回更明确的中文提示，引导用户检查模型名和权限

### 关键设计决策

- 保留前端拦截器的小写转换逻辑（百炼模型 ID 确实是小写格式如 `qwen3.7-plus`）
- 不移除旧版 `qwen-plus`，用户仍可通过自定义模型名输入框回退到旧版
- 后端错误增强只针对 OpenAI SDK 抛出的 404/model_not_found 类错误，不影响其他错误类型

## 实现细节

### 修改文件清单

```
d:/数据分析项目/
├── frontend/src/contexts/DataContext.tsx       # [MODIFY] AI_PROVIDERS 中 qwen 默认 model 从 qwen-plus → qwen3.7-plus
├── frontend/src/api/client.ts                 # [MODIFY] 修正拦截器注释（qwen3.7-plus 是正确格式，不是错误示例）
├── frontend/src/components/Layout/Sidebar.tsx # [MODIFY] 补充可用模型名参考和权限提醒文案
├── backend/routers/report.py                  # [MODIFY] 捕获 model_not_found 错误，返回明确中文提示
├── backend/routers/insights.py                # [MODIFY] 同 report.py，增强 model_not_found 错误提示
├── backend/routers/data.py                    # [MODIFY] 同上，compute 接口也需要增强错误提示
├── backend/routers/clean.py                   # [MODIFY] 同上，ai-clean 接口也需要增强错误提示
```

### 核心逻辑 — 后端 model_not_found 错误增强

在各 router 的 AI 调用 try-catch 中，对 `openai.NotFoundError` 或错误消息包含 `model_not_found` 的情况，返回更明确的中文提示：

- 提示用户检查模型名是否正确（并列出常用模型名）
- 提示用户在百炼控制台检查是否开通了该模型的访问权限
- 提示用户尝试使用新域名（WorkspaceId 版）

### 核心逻辑 — Sidebar 提示增强

在"模型名称"输入框下方增加提示：

- 阿里云可用：qwen3.7-plus / qwen3.7-max / qwen-plus / qwen-max / qwen-turbo
- 提醒：新模型需在百炼控制台开通权限，否则会报 model_not_found