---
title: TypeScript是什么
aliases: [TypeScript, TS, 类型化JavaScript]
tags: [tech/frontend, 概念]
created: 2026-07-17
---

# TypeScript 是什么（DataMind AI 前端）

> 一句话：**TypeScript 是「加了类型系统的 JavaScript」**。它不替代 JS，而是 JS 的「超集（superset）」——你写的 TS 最终会被编译（转译）成普通 JS 交给浏览器运行。本项目前端全部用 TS 写 React，总入口见 [[前端技术栈]]。

## 一、先搞清楚：TS 不是新语言，是 JS + 类型

| 它是什么 | 它不是什么 |
|---|---|
| JavaScript 的超集（所有合法 JS 都是合法 TS） | 不是一门完全独立的语言 |
| 给变量 / 函数 / 对象**提前声明类型** | 运行时不会报错（类型只在编译期检查） |
| 由 Microsoft 开发维护 | 不是后端语言、不是数据库 |
| 编译后产出纯 JS | 浏览器/Node 不认识 `.ts`，只认 `.js` |

**类比**：JS 像「手写便条，写完才发现有错别字」；TS 像「先填好带格式的表格（姓名:字符串、年龄:数字），填错当场就被打回」。便条本身（JS）是最后真正被寄出去的东西。

## 二、它解决什么痛点？

JS 是「动态弱类型」：变量可以随时变成任何类型，跑起来才知道错没错。

```js
// 普通 JS：这里不会报错，但运行时可能爆炸
let price = "9.9"      // 字符串
let total = price * 3   // "9.9" * 3 = 29.7（JS 偷偷帮你转了，但逻辑已不干净）
let name = price.toUpperCase() // ❌ 运行时才报错：字符串方法被用在可能非字符串上
```

TS 把错误**提前到写代码 / 编译阶段**：

```ts
let price: number = "9.9"  // ❌ 编译期直接报错：string 不能赋给 number
let total: number = price * 3
let name: string = price.toUpperCase()
```

好处一句话：**bug 在「写的时候」就抓出来，而不是「用户点的时候」才崩**。

## 三、三个最小核心概念

1. **类型标注（Annotations）** —— 用 `:类型` 告诉编译器「这玩意儿应该是啥」。常见：`string` / `number` / `boolean` / `any`（关闭检查，慎用）/ `unknown`。
2. **接口 / 类型别名（interface / type）** —— 给「对象长什么样」起个名字，复用且自解释。本项目 `src/types/` 全是这类定义。
3. **泛型（Generics）** —— 类型也能当参数，如 `Array<string>` 表示「字符串数组」。

```ts
interface KpiItem {
  label: string
  value: number
  delta?: number   // ? 表示「可选，可没有」
}

function format(kpi: KpiItem): string {
  return `${kpi.label}: ${kpi.value}`
}
```

> 编译命令：`tsc` 把 `.ts` → `.js`；本项目由 [[Vite是什么]] 在打包时顺手完成（开发时还能热更新 + 实时类型报错）。

## 四、在本项目里 TS 在哪

| 位置 | 作用 |
|---|---|
| `*.tsx` / `*.ts` 全部前端文件 | React 组件、API 封装、工具函数都用 TS 写 |
| `frontend/src/types/` | 全局类型定义（接口返回结构、组件 props 形状） |
| `frontend/tsconfig.json` | 编译配置（严格模式、路径别名 `@/`） |
| 调用后端时 | 用 TS 类型约束「后端 JSON 长啥样」，避免拿到 `{undefined}` 还当对象用 |

**为什么本项目非用 TS 不可**：DataMind AI 要处理大量「分析包 → 图表 option → 报告」的嵌套数据结构，类型能防止「把字符串当数组 map」「少传一个字段导致渲染崩溃」这类高频错误——尤其多人协作和 LLM 返回结构不稳定时，类型是最便宜的护栏。

## 相关笔记

- [[前端技术栈]] —— 前端总入口 MOC（TS 是其中「语言」层）
- [[React是什么]] —— 本项目用 TS 写 React
- [[Vite是什么]] —— 负责把 TS 编译打包
- [[前端怎么调后端API]] —— 用 TS 类型约束后端返回结构
