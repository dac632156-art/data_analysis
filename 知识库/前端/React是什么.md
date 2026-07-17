---
title: React是什么
aliases: [React, React.js, ReactJS, 前端框架]
tags: [tech/frontend, 概念]
created: 2026-07-17
---

# React 是什么（DataMind AI 前端）

> 一句话：React 是一个**「用组件拼出界面」的 JavaScript 库**。它不是一门新语言，也不是包办一切的后端框架，而是专门帮你**把数据变成屏幕上的界面**的那一层。属于前端，总入口见 [[前端技术栈]]。

## 一、先搞清楚：React 是"库"不是"框架全家桶"

| 它是什么 | 它不是什么 |
|---|---|
| 一个 JS 库（library） | 不是一门新语言（还是写 JS / TS） |
| 只管"界面怎么显示" | 不是后端、不是数据库 |
| 由 Meta（Facebook）开源维护 | 不强制你用它的路由 / 请求方案（可自己选） |

**类比**：如果说"做网站"像开餐厅，那 React 只是**后厨里那套「把食材摆盘上桌」的标准流程**，不是整栋餐厅（餐厅 = 前后端全套）。摆盘规则学会了，菜品（数据）由后端提供，详见 [[前端怎么调后端API]]。

## 二、它解决什么痛点？（为什么不用原生 JS）

没有 React 时，你改界面得自己用 `document.getElementById(...).innerHTML = ...` 去翻 DOM 树，页面一复杂就乱套。

React 的核心思想是：**你只管「数据长啥样」，界面自动跟着变**。数据变了 → React 重新算界面 → 屏幕更新。你不用手动去改 DOM。

| 方式 | 你做的事 | 谁改界面 |
|---|---|---|
| 原生 JS | 手动找 DOM 节点、改它的内容 / 样式 | 你自己 |
| React | 改一个变量（state），写"界面 = 函数(数据)" | React 自动 |

## 三、三个最小核心概念

1. **组件（Component）** = 一块可复用的界面"积木"。一个按钮、一个图表、一整个页面都是组件。页面 = 组件套组件。详见 [[组件与JSX是什么]]。
2. **JSX** = 长得像 HTML 的写法，让你在 JS 里直接描述界面长相，如 `<Button>提交</Button>`。
3. **state（状态）** = 组件自己"记着"的数据。state 一变，界面就重画。父传给子的数据叫 props，详见 [[Props与状态是什么]]。

> 组件"出生后 / 数据变了要干点额外的事"（比如发请求）用 `useEffect`，见 [[useEffect是什么]]。

## 四、最小例子（计数器）

```tsx
function Counter() {
  const [count, setCount] = useState(0)  // count 是 state
  return (
    <button onClick={() => setCount(count + 1)}>
      点了 {count} 次
    </button>
  )
}
```

你只改 `count`，"点了 N 次"那行文字**自动**跟着变——不用自己碰 DOM。这就是 React 的"数据驱动视图"。

## 五、在本项目里 React 在哪

- 入口 `src/main.tsx` 把 `<App/>` 挂上页面；
- `src/App.tsx` 用路由决定显示哪个页面（见 [[前端路由是什么]]）；
- `src/pages/` 是各页面，`src/components/` 是可复用组件（34 个文件）；
- 组件里通过 `src/api/` 发请求拿数据（见 [[前端怎么调后端API]]），数据回来后存进 state，界面就刷新了；
- 图表用 ECharts 画在组件里（见 [[前端图表ECharts]]）。

## 相关笔记

- [[前端技术栈]] —— 前端总入口 MOC
- [[组件与JSX是什么]]、[[Props与状态是什么]]、[[useEffect是什么]] —— React 三大机制
- [[Vite是什么]] —— 跑起 React 开发服务器的工具
- [[TypeScript是什么]] —— 本项目用 TS 写 React
- [[前端怎么调后端API]] —— React 组件如何拿后端数据
