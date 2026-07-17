---
title: RESTful API 是什么
aliases: [REST, RESTful]
tags: [tech/backend, 核心概念]
created: 2026-07-16
---

# RESTful API 是什么

## 拆词

- **REST** = **Re**presentational **S**tate **T**ransfer（表现层状态转移）—— 一种软件架构风格
- **RESTful API** = 符合 REST 风格的 API

> REST 是"设计哲学"，RESTful API 是"按这个哲学设计出来的接口"。

## 核心思想：一切皆资源（Resource）

把后端要操作的东西看成**资源**，用 URL 定位它，用 HTTP 方法表示"对它的动作"。

```
URL（定位资源） + HTTP 方法（说明动作） = 一次操作
```

| 概念 | 类比 | API 体现 |
|---|---|---|
| **资源** | 名词（卡片、报告） | URL 路径 `/api/dashboard/cards` |
| **动作** | 动词（查、增、删） | HTTP 方法 GET / POST / DELETE |
| **表现** | 资源的某种形式 | 返回的 JSON |

## HTTP 方法 = 动作

| 方法 | 含义 | [[PRD_DataMind_AI\|项目]]例子 |
|---|---|---|
| `GET` | 查询（读取） | `GET /api/health` 查服务健康 |
| `POST` | 新建 / 执行 | `POST /api/dashboard/cards` 生成卡片 |
| `PUT` | 整体更新 | （本项目较少用） |
| `DELETE` | 删除 | `POST /api/dashboard/delete-saved-chart` 删图 |

> 设计原则：GET 只查不改，POST 触发动作/创建。前端看方法名就知道是"读"还是"写"。

## RESTful 的 5 条核心约束

| 约束 | 含义 | 项目体现 |
|---|---|---|
| **① 资源用 URL 定位** | 每个资源有唯一地址 | `/api/data/preview` |
| **② 用 HTTP 方法表动作** | GET查 POST写 | 上面讲过 |
| **③ 无状态（Stateless）** | 每次请求自带全部信息 | 每个请求都带 `session_id` |
| **④ 返回标准格式 JSON** | 统一表现 | 全部返回 JSON |
| **⑤ 统一接口** | 约定一致 | 全部 `prefix="/api"`，`/模块/动作` 结构 |

### 重点③ 无状态

每个请求都必须带上 `session_id`，服务器不"记得"你是谁。好处：
- 服务器简单
- 可水平扩展
- 挂了重启不丢"会话记忆"

## 反例：RPC 风格

不是 RESTful 的接口长这样：

```
POST /api/doCleanMissingReport   ← 动作塞进 URL
POST /api/getHealthStatus
POST /api/createDashboardCards
```

问题：动作全写 URL 里，方法全用 POST，没有"资源"概念。

## 完整请求案例

```
前端                                  FastAPI 后端
  │                                      │
  │  POST /api/dashboard/cards           │
  │  {session_id: "abc123"}              │
  │  ──────────────────────────────────► │
  │                                      │ ① 路由：资源 = cards
  │                                      │ ② 方法：POST = 执行生成
  │                                      │ ③ 无状态：session_id 找回数据
  │                                      │ ④ card_generator.generate()
  │                                      │ ⑤ 返回 JSON
  │  ◄────────────────────────────────── │
  │  {"cards": [...], "success": true}   │
```

## 相关笔记

- [[API调用是什么]] —— 调用 API 的具体行为
- [[FastAPI详解]] —— RESTful 风格的最佳搭档
- [[API的构成与种类]] —— Web API 三件套与 AI API 的异同
- [[PRD_DataMind_AI#4.4.4 接口与依赖说明|PRD 接口与依赖说明]]
