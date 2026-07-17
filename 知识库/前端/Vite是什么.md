---
title: Vite是什么
aliases: [Vite, 构建工具, dev server, 前端打包]
tags: [tech/frontend, 构建]
created: 2026-07-17
---

# Vite 是什么

> 配套看 [[前端技术栈]]（前端总览 MOC）和 [[TypeScript是什么]]（Vite 打包时编译 TS）。对称的后端构建见 [[uvicorn是什么]]。

## 一句话定义

**Vite 是「前端构建工具 + 开发服务器」二合一**：开发时给你一个**秒级启动、改代码立刻生效**的本地服务器；上线时把你的 `.tsx`/`.ts`/`.css` 打包成浏览器能直接跑的静态文件。

它解决的核心痛点：老牌打包器（如 webpack）**启动慢、改一下要等好几秒才刷新**——项目越大越忍不了。Vite 用浏览器原生 ES Module（ESM）+ 按需编译，把这俩等待几乎压到 0。

| 它是什么 | 它不是什么 |
|---|---|
| 开发服务器（dev server） | 不是「只在开发时用」——也负责生产打包 |
| 构建/打包工具（底层用 Rollup） | 不是 webpack 的换皮，机制本质不同 |
| 和框架无关，但本项目配 React | 不是 React 专属 |

## 两个核心能力

### 1. 开发时：`vite`（dev server）

跑 `npm run dev` 后：

- **秒级启动**：不预先打包整个项目，而是浏览器请求哪个模块就编译哪个。
- **HMR（热更新 Hot Module Replacement）**：改一个组件，只替换那一个模块，页面不刷新、状态不丢。
- **原生 ESM**：直接把 ES Module 发给浏览器，由浏览器自己处理 `import`，Vite 只做「按需转译」（TS/JSX → JS、CSS 处理）。
- **依赖预构建**：第一次把 `node_modules` 里的第三方包（如 React、ECharts）用 esbuild 快速打包成浏览器友好的 ESM，之后缓存复用。

本项目本地地址：`http://localhost:5173`（见 `frontend/vite.config.ts` 的 `server.port`）。

### 2. 上线时：`vite build` + `vite preview`

- `vite build` 用 **Rollup** 把整个应用打包成 `dist/` 目录下的静态文件（`index.html` + 分割好的 `.js`/`.css`），做了 tree-shaking、压缩、代码分割。
- 这个 `dist/` 不依赖 Vite，可以丢到任意静态服务器 / Nginx / 对象存储 / CI 托管。
- 本项目**开发时**靠 Vite 代理转发 API，但**生产环境**没有 Vite：前端的 `dist/` 由后端或云托管，`/api` 走真实域名（见下方「本项目的体现」）。

## 与 TypeScript 的关系

你写的 `.tsx` 浏览器根本不认识，必须由 Vite 在转译时**把 TS 类型擦除、编译成 JS**。

- 关键点：**Vite 只做「转译」，不做「类型检查」**。它用 esbuild 极快地把 TS 抹掉类型，但**不会报类型错误**（类型错误由 `tsc` 或编辑器负责）。
- 这也解释了为什么「`npm run dev` 能跑，但 `tsc` 一堆红」会同时存在——Vite 跑得快但不拦类型 bug，类型护栏是另一套机制（见 [[TypeScript是什么]]）。

## 本项目的体现（真实代码）

`frontend/vite.config.ts` 里的关键配置：

```ts
export default defineConfig({
  plugins: [react()],                    // 让 Vite 能编译 .tsx
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },  // 写 "@/xxx" 等价于 "src/xxx"
  },
  server: {
    host: '0.0.0.0',
    port: 5173,                          // 本地开发地址
    proxy: {
      '/api': {
        target: 'http://localhost:8001', // 把 /api/* 转发到后端 FastAPI
        changeOrigin: true,
      },
    },
  },
})
```

三件和日常开发强相关的事：

1. **`/api` 代理**：前端代码里只写 `/api/analysis`，Vite 在开发时自动把它转发到后端 `localhost:8001`，所以前端不用写死后端域名、也不踩浏览器跨域（CORS）。这就是 [[前端怎么调后端API]] 的「本地不跨域」秘诀。
2. **`@` 别名**：组件里 `import X from '@/components/Y'` 就是 `src/components/Y`，少写一堆 `../../`。
3. **`react()` 插件**：负责把 JSX/TSX 编译成 JS，否则 Vite 不认识 `<Component/>`。

## 为什么本项目离不开 Vite

- **开发体验**：DataMind AI 前端有 34 个组件 + 大量图表，没有秒级 HMR，改一个样式要等 webpack 重新编译会非常折磨。
- **TS 落地的前提**：Vite 让 TS 写起来「即写即跑」，否则类型语言根本跑不起来（配合 [[TypeScript是什么]] 的类型护栏）。
- **前后端联调无痛**：`/api` 代理让本地前端和 `localhost:8001` 后端像在同一个域名下，省掉跨域配置。

## 相关笔记

- [[前端技术栈]] —— 前端总览 MOC，Vite 在其中属于「构建 / 开发服务器」
- [[TypeScript是什么]] —— Vite 打包时把 TS 编译成 JS（但 Vite 不做类型检查）
- [[React是什么]] —— Vite 配 `@vitejs/plugin-react` 编译 React
- [[前端怎么调后端API]] —— `/api` 代理是 Vite 干的活
- [[uvicorn是什么]] —— 对称的后端「服务器」，Vite 是前端侧的对应物
- [[README]] —— 知识库总索引
