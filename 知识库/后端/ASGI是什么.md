---
title: ASGI 是什么
aliases: [ASGI, 异步服务器网关接口]
tags: [tech/backend, 核心概念]
created: 2026-07-17
---

# ASGI 是什么

> 结合 [[后端技术栈|DataMind AI 后端]] 实际代码讲解。建议先读 [[uvicorn是什么]] / [[FastAPI详解]]。

## 一句话定义

**ASGI = Asynchronous Server Gateway Interface（异步服务器网关接口）**，是 Python 定义「Web 服务器怎么把请求交给 Python 应用、应用怎么把响应还回去」的一份**标准协议**。FastAPI、uvicorn 都遵守这套协议，所以二者能无缝对接。

## 为什么要有它（从 WSGI 说起）

| 标准 | 全称 | 年代 | 能力 | 能跑 FastAPI 吗 |
|---|---|---|---|---|
| **WSGI** | Web Server Gateway Interface（同步） | 2003 | 一次请求 = 一个同步函数调用，处理完才返回 | ❌ 不支持异步 |
| **ASGI** | Async Server Gateway Interface（异步） | 2018 | 支持 `async/await`、WebSocket、长连接、后台任务 | ✅ 原生支持 |

WSGI 时代（Flask / Django 早期）请求是**同步阻塞**的：一个请求没处理完，线程就卡住。但现代应用需要 WebSocket（实时推送）、需要异步调 LLM（等待期间不占线程）——WSGI 做不到，于是 ASGI 作为「异步版 WSGI」诞生。

## ASGI 体系里的两个角色

ASGI 只管「接口长什么样」，具体干活分两方：

| 角色 | 是什么 | 本项目对应 |
|---|---|---|
| **ASGI 应用（Application）** | 写业务逻辑的框架，按 ASGI 规范暴露一个 `app` 可调用对象 | **FastAPI**（底层基于 Starlette，Starlette 实现 ASGI 接口） |
| **ASGI 服务器（Server）** | 真正监听端口、收 HTTP、按 ASGI 协议把请求喂给应用 | **uvicorn**（还有 hypercorn、daphne） |

> 关键结论：**FastAPI 是「ASGI 应用」，uvicorn 是「ASGI 服务器」**。这就是 [[uvicorn是什么]] 里说的「FastAPI 不能直接跑、必须靠 uvicorn 托管」的根本原因——FastAPI 只实现了 ASGI 应用那一半，网络进出那一半由 uvicorn（ASGI 服务器）补上。

## 类比

把 Python Web 生态想成「电器 + 插座 + 插头标准」：

- **ASGI** = 插头标准（规定插座和应用怎么插）
- **uvicorn** = 插座（接网线，监听端口）
- **FastAPI** = 电器（按标准做，一插就能用）

WSGI 是老插头标准，老电器（Flask）能用，但新电器（FastAPI，要异步）必须用新标准 ASGI，配新插座 uvicorn。

## 常见误解

| 误解 | 正解 |
|---|---|
| ASGI 是个软件/服务器 | ❌ 它是**协议/接口规范**，不是具体程序 |
| gunicorn 是 ASGI 服务器 | ⚠️ gunicorn 本质 WSGI 进程管理器；它能「带 uvicorn worker」跑 ASGI，但自己不是 ASGI 服务器 |
| 用了 FastAPI 就自动是异步 | ⚠️ FastAPI 支持异步，但要你写 `async def` + 配 ASGI 服务器（uvicorn）才能真正异步起来 |

## 相关笔记

- [[后端技术栈]] —— 后端知识聚合页（MOC），含技术栈总表
- [[uvicorn是什么]] —— 本项目用的 ASGI 服务器
- [[FastAPI详解]] —— 本项目用的 ASGI 应用（基于 Starlette）
- [[路由是什么]] —— 请求经 uvicorn 交给 FastAPI 后，由路由匹配处理函数
