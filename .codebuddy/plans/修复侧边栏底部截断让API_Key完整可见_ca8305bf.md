---
name: 修复侧边栏底部截断让API Key完整可见
overview: 重构 frontend/src/components/Layout/Sidebar.tsx 的 flex 布局为三段式（顶部 Logo 固定 / 中间导航可滚动 / 底部 API Key 配置+数据信息固定），并对 API Key 区做适度紧凑化，解决 API Key 输入框被视口底部裁剪、滚动条又极细导致用户感知为「被截断」的问题。
todos:
  - id: restructure-sidebar-layout
    content: 重构 Sidebar.tsx 三段式布局并压缩 API Key 区垂直占用
    status: completed
  - id: self-verify-changes
    content: 重读 Sidebar.tsx 并 grep 自检三段式 className 与紧凑化改动落地
    status: completed
    dependencies:
      - restructure-sidebar-layout
---

## 用户需求

修复左侧栏底部内容被截断的 bug：当前在常规视口下，"输入 API Key" 输入框被视口底边裁切，只能看到一点，用户体验为"页面被截断"。

## 核心目标

- 侧边栏底部 API Key 配置区在任何常见视口（1366×768 / 1440×900 / 1920×1080）下完整可见。
- 顶部 Logo 与底部 API Key / 数据信息区视觉上"钉死"，中间导航区在空间不足时可滚动。
- 不破坏现有折叠/展开功能、滚动条样式与色板（紫 #8B5CF6 银河紫体系）。

## 技术栈

- React 18 + TypeScript
- Tailwind CSS（utility-first）
- 现有 Flex 布局模型（不动 Layout.tsx）

## 实施方案

**根因**：`Sidebar.tsx` 的 `<aside>` 虽然有 `overflow-y-auto`，但内联 `scrollbarWidth: 'thin'` + 半透明 `scrollbarColor` 把滚动条做得几乎不可见，叠加 API Key 区内容（select + 2 inputs + 多条帮助文字 ≈ 500-600px）超出常见视口高度，用户感知为"被截断"而非"可滚动"。

**方案（三段式 Flex 布局 + 紧凑化）**：

1. **三段式拆分**：把 aside 内部分成「顶部固定 / 中间可滚动 / 底部固定」三段

- Logo wrapper div：补 `flex-shrink-0` 钉死顶部
- `<nav>`：改为 `flex-1 min-h-0 overflow-y-auto`（中间导航区独占剩余高度并独立滚动）
- API Key 配置 div + 数据信息 div：保持 `flex-shrink-0` 钉死底部，永远完整可见

2. **紧凑 API Key 区**：在不损失可读性的前提下减少垂直占用，确保 768px 视口也能完整显示

- 容器 `py-4 → py-3`、`space-y-2 → space-y-1.5`
- 各 label 的 `mt-2 → mt-1.5`
- select/input 的 `py-2 → py-1.5`
- 帮助文字 `mt-0.5` 保持不变

3. **滚动条策略**：aside 的内联 `scrollbarWidth: 'thin'` 保留作为全局兜底样式；新增的 nav `overflow-y-auto` 自然继承同一滚动条样式，当 nav 内容超出其分配高度时滚动条仍可见。
4. **不改**：Layout.tsx、折叠/展开逻辑、API Key 功能字段与回调、色板（Palette.ts）、字体、ThemeProvider。

## 性能与可靠性

- 单一文件修改，改动面小、风险可控。
- 不引入新依赖、新组件、新状态。
- 折叠态（w-20）下 API Key / 数据信息区因 `!collapsed &&` 守卫不会渲染，不受影响。

## 兼容性

- 折叠态：只显示 Logo + 导航图标，4 个 navItem 高度 ≈ 180px，远小于任何视口，无截断问题。
- 展开态：高度分配变为 Logo 70px（固定）+ nav 180px（固定，可滚动）+ 底部 ~520px（固定后）= ~770px，刚好覆盖 768px 视口且底部完整。

## 涉及文件

```
frontend/
└── src/
    └── components/
        └── Layout/
            └── Sidebar.tsx  [MODIFY] 三段式 flex 拆分 + API Key 区紧凑化
```