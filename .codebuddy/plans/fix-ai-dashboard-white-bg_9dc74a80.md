---
name: fix-ai-dashboard-white-bg
overview: 修复智能驾驶舱白色背景问题：修复 Layout 高度传递链断裂 + 添加后备暗色背景
todos:
  - id: fix-layout-height-chain
    content: 修改 Layout.tsx，main 改为 h-screen flex flex-col，内层 div 加 flex-1
    status: completed
  - id: fix-dashboard-bg
    content: 修改 DashboardPage.tsx 内容区，加 bg-[#020617] 和 overflow-auto
    status: completed
    dependencies:
      - fix-layout-height-chain
  - id: fix-theme-provider
    content: 修改 ThemeProvider.tsx，添加 h-full 确保填满父容器
    status: completed
    dependencies:
      - fix-layout-height-chain
---

## 核心问题

智能驾驶舱（AI 模板）仍然显示白色背景，之前的修改（ThemeProvider 加 bg-[#050816]、DashboardRenderer 强制 darkMode=true）没有生效。

## 根因

CSS 高度链断裂：Layout → main → 内层 div → DashboardPage → flex-1，整条链的 height 都是 auto，导致 flex-1 容器塌陷为 0 高度。ThemeProvider 内的 `min-h-screen bg-[#050816]`（100vh）被父容器的 `overflow-hidden` 裁剪掉，用户只能看到白色/透明区域。

具体链路：

- `Layout.tsx` L10: 外层 div 只有 min-h-screen
- `Layout.tsx` L14: main 只有 min-h-screen（min-height，height=auto）
- `Layout.tsx` L15: max-w-7xl div 无 height 设置
- `DashboardPage.tsx` L530: h-full 解析为 auto（父级 height=auto）
- `DashboardPage.tsx` L592: flex-1 塌陷为 0（flex-basis:0%，无空间可增长）
- `ThemeProvider.tsx` L75: min-h-screen=100vh 被 overflow-hidden 裁剪

## 修复方案

### 修改 1: Layout.tsx — 修复高度传递链

将 main 改为 flex 布局，确保高度向下传递：

```
<main className="ml-64 h-screen p-6 relative z-10 flex flex-col" translate="no">
  <div className="max-w-7xl mx-auto w-full flex-1 page-enter notranslate">
```

关键改动：

- `min-h-screen` → `h-screen`：设置显式 height（而非 min-height），让子元素的 `h-full`/`flex-1` 能正确解析
- 添加 `flex flex-col`：让 main 成为 flex 容器
- 内层 div 添加 `flex-1`：填充 main 的可用空间（扣除 p-6 padding 后的区域）
- 添加 `w-full`：确保宽度填满

### 修改 2: DashboardPage.tsx — 内容区加后备暗色背景

```
<div className="flex-1 overflow-auto bg-[#020617]" ref={screenRef}>
```

关键改动：

- `overflow-hidden` → `overflow-auto`：允许内容超出时滚动，不再裁剪 ThemeProvider
- 添加 `bg-[#020617]`：后备暗色背景（与 Layout 一致），即使 ThemeProvider 未填满也显示暗色

### 修改 3: ThemeProvider.tsx — 背景优先填满父容器

```
<div className={`h-full min-h-screen ${active.background} transition-colors duration-500`}>
```

关键改动：

- 添加 `h-full`：优先填满父容器的高度（父容器现在是 flex-1，有显式高度）
- 保留 `min-h-screen` 作为兜底：如果父容器高度异常，仍保证最小 100vh

### 对其他页面的影响验证

其他页面（Upload、Clean、Analysis）使用内容驱动高度，改为 `h-screen flex-col` 后：

- 短内容页面：flex-1 子元素自动填满剩余空间，不受影响
- 长内容页面：flex-1 允许内容超出（配合 overflow-auto），仍可滚动

### 涉及文件

- [MODIFY] `frontend/src/components/Layout/Layout.tsx` — L14-15：main 改 h-screen flex-col，内层 div 加 flex-1
- [MODIFY] `frontend/src/pages/DashboardPage.tsx` — L592：flex-1 overflow-hidden → flex-1 overflow-auto bg-[#020617]
- [MODIFY] `frontend/src/components/DashboardRenderer/ThemeProvider.tsx` — L75：添加 h-full