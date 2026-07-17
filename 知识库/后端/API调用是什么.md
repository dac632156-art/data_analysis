---
title: API 调用是什么
aliases: [API, 调用API, 接口调用]
tags: [tech/backend, 核心概念]
created: 2026-07-16
---

# API 调用是什么

## 拆词理解

- **API** = **A**pplication **P**rogramming **I**nterface（应用程序编程接口）
- **调用** = 主动发起一次请求，并等待 / 使用返回结果这个动作

> "调用 API" = 程序之间"点单—上菜"的过程。你点（请求），对方做（处理），把结果端回来（响应）。

## 类比：餐厅模型

| 餐厅 | API |
|---|---|
| 菜单 + 服务员 | API 入口——能点什么菜（接口路径）、每种菜要什么配料（参数）、上菜多久（返回格式） |
| 你点单 | 发起请求 |
| 厨房炒菜 | 后端处理逻辑 |
| 上菜 | 返回结果 |

你不用进厨房（不用知道菜怎么炒），按菜单点（按格式发请求），服务员把菜端出来（返回 JSON）。

## DataMind AI 项目里的两层"调用 API"

### ① 前端 → 后端（内部接口）

前端不知道数据怎么分析的，它只**调用**后端写好的接口。

**例子**：[[PRD_DataMind_AI#4.4.4 接口与依赖说明|PRD 接口说明]]

```ts
// DashboardPage.tsx
const res = await api.generateCards(ds.sessionId);
const result = await api.generateAIReport(ds.sessionId, pk, bu, md, localPackages);
```

`api.generateCards(...)` = 前端调用后端 API：把 `sessionId` 发过去 → 后端跑分析 → 返回"卡片数据"给前端画图。

后端对应入口：

```python
@router.post("/dashboard/cards")
async def api_generate_cards(req: CardsGenerateRequest):
```

### ② 后端 → 外部大模型（LLM API）

DataMind 后端去**调用**大模型厂商（OpenAI / DeepSeek）的 API 来生成 AI 叙事文案。

如果没配 Key 或调用失败 → 降级为规则摘要（见 [[PRD_DataMind_AI#4.4.1 全局公共规则|PRD 全局规则]]）。

## 调用链总览

```
用户浏览器
  │  HTTP POST /api/...  (JSON)
  ▼
DataMind 后端 (FastAPI)
  │  routers → services → src/*
  │
  ├── 内部计算（规则引擎 / 指标 / 图表）← 不含外部依赖
  │
  └── LLM API（外部）← 可选，失败即降级
```

## 与项目内其他概念的关系

- [[FastAPI详解]] —— 本项目后端框架，定义了所有被调用的 API 入口
- [[RESTful API是什么]] —— 本项目接口的设计风格
- [[为什么要写API文档]] —— API 接口为什么需要文档（契约价值）
- [[API的构成与种类]] —— 路由+方法+函数只是 Web API 特征，AI API 角色相反
- [[PRD_DataMind_AI]] —— 产品的接口与依赖说明（4.4.4 节）
