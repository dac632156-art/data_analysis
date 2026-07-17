---
title: uvicorn 是什么
aliases: [uvicorn, ASGI服务器, 服务器]
tags: [tech/backend, 运行时]
created: 2026-07-17
---

# uvicorn 是什么

> 结合 [[后端技术栈|DataMind AI 后端]] 实际代码讲解。建议先读 [[FastAPI详解]]。

## 一句话定义

**uvicorn = 一个高性能 Python ASGI 服务器**，专门用来启动并托管 FastAPI（等 ASGI 框架）应用。

类比：FastAPI 是「餐厅后厨（做菜逻辑）」，uvicorn 是「餐厅大门 + 服务员（迎客、上菜、走网络）」。没有 uvicorn，FastAPI 应用根本起不来。

## 为什么需要它（WSGI 的历史坑）

| 服务器类型 | 代表 | 能否跑 FastAPI |
|---|---|---|
| WSGI（旧，同步） | gunicorn / uWSGI | 不能跑异步 FastAPI |
| **ASGI（新，异步）** | **uvicorn** | ✅ 原生支持 `async/await` |
[[同步与异步是什么]]

FastAPI 基于 Starlette（异步），必须用 ASGI 服务器。uvicorn 内部用 `uvloop`（加速事件循环）+ `httptools`（解析 HTTP），性能接近 Node.js / Go。

## 本项目里的真实用法

### ① 本地开发（`backend/main.py` 末尾）

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
```

`"main:app"` = 「main 模块里的 app 对象」，uvicorn 找到它并托管；`reload=True` 改代码自动重启。

### ② 生产部署（`backend/Procfile`，Render 读取）

```
web: cd .. && uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

Render 用这行命令启动，`$PORT` 由平台注入（不再是本地写死的 8001）。

> 注意：生产环境**不能**加 `reload=True`——那是开发热重载，会拖性能且不稳定。

## 在本项目请求链路里的位置

```
浏览器  →  uvicorn（监听端口，解析 HTTP）  →  FastAPI app（路由/校验）  →  业务函数
        ←  uvicorn（打包成 HTTP 响应）     ←  FastAPI 返回 dict
```

uvicorn 管「网络进出」，FastAPI 管「业务规则」。详见 [[后端技术栈]] 的请求链路图。

另外，项目里所有异常日志都打到 `uvicorn.error` 这个 logger（`backend/main.py`、`backend/routers/upload.py` 都有 `_logging.getLogger("uvicorn.error")`），这样本地控制台和 Render 日志面板都能统一看到后端报错。

## 常见误解

| 误解 | 正解 |
|---|---|
| FastAPI 自带服务器，能直接跑 | ❌ FastAPI 只是框架，必须靠 uvicorn（或 hypercorn）托管 |
| 和 gunicorn 是一回事 | 角色不同：gunicorn 是「进程管理器」（管多进程），uvicorn 是「ASGI worker」（真跑异步）。生产常用 `gunicorn + uvicorn worker`，本项目为简化直接用单 uvicorn |
| `reload` 生产也能开 | ❌ 那是开发热重载，生产必须关 |

## 相关笔记

- [[后端技术栈]] —— 后端知识聚合页（MOC），含技术栈总表与分层架构
- [[FastAPI详解]] —— 被 uvicorn 托管的 Web 框架
- [[路由是什么]] —— uvicorn 把请求交给 FastAPI 后，由路由匹配到处理函数
- [[API调用是什么]] —— 若处理函数内要调 LLM，会经 uvicorn 再发第二层请求
- [[项目架构全景图]] —— 后端 API 在「全系统三层架构」中的位置
