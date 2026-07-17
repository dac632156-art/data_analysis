---
title: 前端怎么调后端API
aliases: [前端怎么调后端API, 前端调后端, axios, 前后端通信]
tags: [tech/frontend, api]
created: 2026-07-17
---

# 前端怎么调后端 API

> 一句话：**前端用 `axios`（一个发 HTTP 请求的 JS 库）把数据打包成请求，发给后端；后端算完返回 JSON，前端再拿来更新界面。** 本项目把这套流程统一封在 `frontend/src/api/` 里。

## 一、为什么需要"调后端"

React 页面运行在**浏览器**里，只能画图、处理点击；真正的"重活"（读 CSV、算统计、跑 AI、生成图表配置）在**后端 Python** 里。前端自己干不了，就得"打电话"给后端：

```
浏览器（React 组件）
  → 发请求（带数据/参数）
  → 后端（FastAPI）算完
  → 返回 JSON
  → 前端用返回的数据更新界面
```

这就是一次「前端调后端 API」。详见 [[API调用是什么]]（从"程序间调用"视角讲）。

## 二、核心工具：axios

- **axios**：浏览器里最常用、发 HTTP 请求的 JS 库（本项目用 `axios 1.18`）。
- 比原生 `fetch` 好用：自动把 JS 对象转成 JSON、自动解析返回、自带拦截器/超时/重试。

本项目所有请求都走一个**统一客户端**：`frontend/src/api/client.ts`，关键代码：

```ts
// api/client.ts
import axios from 'axios';

// 部署时通过环境变量指定后端地址；本地开发走 Vite 的 /api 代理
const API_BASE = import.meta.env.VITE_API_BASE || '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 300000,   // 5 分钟，AI 清洗/报告生成耗时较长
});
```

## 三、本项目怎么封（三层）

不是每个组件自己写 `axios.get`，而是分层：

| 层 | 文件 | 职责 |
|---|---|---|
| 底层客户端 | `api/client.ts` | 创建 axios 实例、统一 baseURL / 超时 / 拦截器 |
| 接口封装 | `api/*.ts`（如 `analysis.ts`、`dashboard.ts`） | 把"上传文件""生成卡片"等业务封装成函数，组件只调 `api.upload(...)` |
| 组件调用 | `pages/**`、`components/**` | 在事件里调封装好的函数，拿到结果写进 React state |

> 好处：组件里看不到 URL 和请求细节，换后端地址只改一处（`client.ts` 或环境变量）。

## 四、请求都发去哪（/api 代理是关键）

这是最容易踩坑的点：

- **本地开发**：前端跑在 Vite 开发服务器（如 `localhost:5173`），后端跑在 `localhost:8001`。两者端口不同 → 直接发 `localhost:8001` 会**跨域报错**。
  - 解决：请求 URL 写成 `/api/xxx`（`baseURL:'/api'`），**Vite 把 `/api/*` 自动代理转发到 `localhost:8001`**（见 [[Vite是什么]]）。
- **生产/部署**：前端打包成静态文件，由后端（或 Render/Vercel）直接托管。此时设环境变量 `VITE_API_BASE` 指向真实后端域名，`/api` 前缀就直接发到那了。

```
本地：  组件 → /api/xxx → Vite 代理 → localhost:8001（后端）
部署：  组件 → /api/xxx → 真实域名/api/xxx（后端，由 VITE_API_BASE 决定）
```

> 注意：**前端路由**只管非 `/api` 的 URL（见 [[前端路由是什么]]）；以 `/api` 开头的请求被代理"截走"，不归路由管。

## 五、两个值得一提的细节（来自 client.ts）

1. **model 名自动小写**：请求拦截器里把 `data.model` 统一转小写，避免「Qwen-Plus」vs「qwen-plus」大小写不匹配导致 `model_not_found`（阿里云百炼 / DeepSeek / OpenAI 的模型 ID 都是小写）。
2. **后端休眠自动重试**：检测到后端无响应（本地偶发 / Render 冷启动）时，等 5 秒再重试一次，提升部署环境稳定性。

## 六、一次完整链路（串起来）

```
用户点"生成分析报告"
  → 页面组件调用 api/ 封装好的 generateAIReport(...)
  → client.ts 发出 POST /api/xxx（走 Vite 代理 → 后端 8001）
  → 后端 FastAPI 路由收到 → 调分析引擎 + AI 大脑算
  → 返回 JSON（报告/图表 option）
  → axios 拿到 → 组件 setState → React 重渲染出报告页
```

> 这是 [[前端路由是什么]]（进页面）、本笔记（调数据）、[[ECharts是什么]]（把数据画成图）三者的合流点。

## 相关笔记

- [[前端技术栈]] —— 前端 MOC，axios 是其中「HTTP 客户端」选型
- [[axios]] —— 若细分（本笔记已涵盖其核心用法）
- [[API调用是什么]] —— 从"程序间调用"通用视角讲 API
- [[Vite是什么]] —— 开发时 `/api` 代理如何转发到后端
- [[前端路由是什么]] —— 与 `/api` 请求的边界划分
- [[ECharts是什么]] —— 拿到的数据最终怎么画成图
- [[FastAPI详解]] / [[后端技术栈]] —— 请求最终到达的后端
- [[代码文件总览]] —— 定位 `api/client.ts`、`api/*.ts`
