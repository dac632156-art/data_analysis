---
name: fix-cleanpage-blackscreen
overview: 修复数据清洗页面点击执行后黑屏崩溃的问题，加 ErrorBoundary + 防御性编程
todos:
  - id: fix-layout-boundary
    content: Layout.tsx：在 <Outlet /> 外层包裹 ErrorBoundary，全局兜底防止单页面崩溃导致整站黑屏
    status: completed
  - id: fix-cleanpage-guard
    content: CleanPage.tsx：AI 清洗成功分支增加 res.preview 和 res.columns 的空值防护
    status: completed
  - id: push-and-verify
    content: 提交推送并验证：生产环境访问清洗页面点击执行，确认不再黑屏
    status: completed
    dependencies:
      - fix-layout-boundary
      - fix-cleanpage-guard
---

## 问题描述

上线平台（Vercel + Render）中，数据清洗页面点击 AI 清洗"执行"按钮后，整个页面黑屏。

## 根因分析

1. **CleanPage 缺少 ErrorBoundary 保护**：UploadPage 有 ErrorBoundary，CleanPage 没有。任何未捕获异常向上冒泡到 Layout，React 卸载整个组件树，只剩深色背景（#020617）= 黑屏。
2. **两处空值防护缺失**（CleanPage.tsx 第 90-91 行）：`setPreview(res.preview)` 接收 undefined 时 DataTable 执行 `Object.keys(undefined[0])` 抛出 TypeError；`res.columns.length` 在 columns 为 undefined 时同样崩溃。
3. **Layout 全局缺少 ErrorBoundary**：Layout 的 `<Outlet />` 无错误边界，任一个页面崩溃导致整站黑屏。

## 修复范围

- Layout.tsx：在 `<Outlet />` 外层包裹 ErrorBoundary，全局兜底
- CleanPage.tsx：AI 清洗成功分支增加空值防护
- 仅修改 2 个文件，改动极小，不影响其他功能

## 技术方案

### 修复策略

**两层防护**：Layout 全局兜底 + CleanPage 局部加固。

- **第一层（全局）**：Layout 的 `<Outlet />` 包裹 ErrorBoundary。即使某个页面组件渲染时崩溃，也只显示红色错误卡片，不会整站黑屏。用户可以从侧边栏切到其他页面恢复正常。
- **第二层（局部）**：CleanPage 中修复第 90-91 行的空值访问，从源头消除已知崩溃点。

### 文件修改

| 文件 | 改动 | 说明 |
| --- | --- | --- |
| `frontend/src/components/Layout/Layout.tsx` | `<Outlet />` 外包裹 `<ErrorBoundary>` | 全局兜底，防止单页面崩溃导致整站黑屏 |
| `frontend/src/pages/CleanPage.tsx` | 第 90-91 行加空值防护 | `res.preview` 和 `res.columns` 防空，避免 TypeError |


### 不改动的地方

- ErrorBoundary 组件本身已实现完善（显示错误信息 + 重试按钮）
- 后端 API 返回格式正确，不需要改后端
- DataTable 组件不做改动（通过上层防护解决）
- 其他页面暂不加 ErrorBoundary（Layout 全局兜底已足够）