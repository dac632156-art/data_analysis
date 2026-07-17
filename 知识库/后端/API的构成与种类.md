---
title: API 的构成与种类
aliases: [API构成, API种类, Web API三件套]
tags: [tech/backend, 核心概念]
created: 2026-07-16
---

# API 的构成与种类

## 你项目里"一个接口"的三件套

在 FastAPI 里定义一个接口 = 路由 + HTTP方法 + 处理函数：

```python
@app.post("/api/dashboard/cards")   # 路由 + HTTP方法
async def api_generate_cards(req):  # 处理函数
```

| 组成 | 是什么 | 项目例子 |
|---|---|---|
| 路由 | URL 路径 | `/api/dashboard/cards` |
| HTTP 方法 | GET/POST/... | POST |
| 处理函数 | 收到请求后执行的代码 | `api_generate_cards` |

## "路由+方法+函数"只是 Web API 的特征，不是所有 API

API = 任何"程序间可调用的接口"，范围比 Web API 大得多：

| API 种类 | 有路由/HTTP方法吗 | 例子 |
|---|---|---|
| **Web API（REST）** | 有（URL + HTTP方法） | 本项目的 FastAPI 接口 |
| **SDK / 库 API** | 没有，就是函数调用 | `pandas.read_csv()`、`openai.OpenAI()` |
| **操作系统 API** | 没有，是系统调用 | 文件读写 `open()` |
| **RPC / gRPC** | 没有 URL，函数签名走网络 | 微服务间调用 |

> "路由+方法+函数"是 **RESTful Web API 的实现三件套**，不是"API"的定义。

## AI 的 API 也是这样吗

**形式上是的**——AI API（OpenAI / DeepSeek）本质也是 Web API：端点 URL + HTTP POST + 服务端处理函数。

以本项目调 DeepSeek 为例（`src/ai_agent/agent.py`）：

```python
self.client = openai.OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com",   # 端点根
)
response = self.client.chat.completions.create(   # 底层 = POST /v1/chat/completions
    model="deepseek-chat",
    messages=[...],
    temperature=0.3,
)
```

| 组成 | AI API 里对应 |
|---|---|
| 路由（端点） | `POST https://api.deepseek.com/v1/chat/completions` |
| HTTP 方法 | POST |
| 处理函数 | DeepSeek 服务端的模型推理（厂商的，看不到） |

### 关键区别：你是调用方，不是定义方

| 维度 | 本项目的 API（FastAPI） | AI 的 API（DeepSeek） |
|---|---|---|
| 谁定义三件套 | **你** | **厂商** |
| 谁调用 | 前端调你 | **你**调厂商 |
| 鉴权 | 本期无 | 需 API Key |
| 请求体 | 业务 JSON | messages（对话） |
| 响应 | 业务结果 | token（可流式） |
| 计费 | 无 | 按 token 计费 |

> 形式一样（URL + HTTP方法 + 处理函数），**角色相反**：一个是服务提供方，一个是服务消费方。

## 相关笔记

- [[路由是什么]] —— 三件套里"路径+方法"两件套的详解（本项目 50+ 条路由全景）
- [[API调用是什么]] —— 调用 API 的行为（含"后端调 LLM"这层）
- [[FastAPI详解]] —— 本项目 Web API 三件套的实现
- [[RESTful API是什么]] —— Web API 的设计风格
- [[为什么要写API文档]] —— 接口契约为什么重要
