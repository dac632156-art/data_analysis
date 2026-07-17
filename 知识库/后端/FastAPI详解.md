---
title: FastAPI 详解
aliases: [FastAPI, 后端框架]
tags: [tech/backend, 框架]
created: 2026-07-16
---

# FastAPI 详解

> 结合 [[PRD_DataMind_AI|DataMind AI]] 项目实际代码讲解。

## FastAPI 是什么

一个**现代 Python Web 框架**，用于构建 RESTful API。

| 特点 | 说明 |
|---|---|
| **快** | 性能接近 Node.js / Go（基于 Starlette + Pydantic） |
| **自动生成 Swagger 文档** | 打开 `/docs` 即可看到所有 API 的可交互文档 |
| **类型安全** | 用 Python 类型注解做请求校验，IDE 自动补全 |
| **异步原生** | 天然支持 `async/await` |

> 类比：Flask 是手动挡，FastAPI 是自动挡——写更少代码，框架做更多事。

## 核心构件

### ① App 实例

```python
# backend/main.py
app = FastAPI(
    title="DataMind AI",
    description="数据分析智能体 API",
    version="1.0.0",
)
```

`app` 是整个后端的**根对象**，负责：
- 注册路由（`app.include_router` / `@app.get`）
- 注册中间件（`app.add_middleware`）
- 注册异常处理器（`@app.exception_handler`）

### ② 路由与路径操作装饰器

```python
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}
```

| 元素              | 说明                                         |     |
| --------------- | ------------------------------------------ | --- |
| `@app.get`      | HTTP 方法（还有 `.post()` `.put()` `.delete()`） |     |
| `"/api/health"` | URL 路径                                     |     |
| 返回 Python dict  | FastAPI **自动转 JSON**                       |     |

### ③ Router（路由模块化）

项目用 `APIRouter` 把 10 个功能模块拆成独立文件：

```python
# backend/routers/clean.py
router = APIRouter()

@router.post("/clean/missing-report")
async def api_missing_report(req: SessionRequest):
```

在 `main.py` 挂载：

```python
app.include_router(upload.router, prefix="/api", tags=["数据上传"])
app.include_router(data.router, prefix="/api", tags=["数据操作"])
# ... 共 10 个 router
```

> `prefix="/api"` 统一加前缀，最终路径 `POST /api/clean/missing-report`

### ③-a 从定义到挂载的完整闭环（以 upload.py 为例）

光看上面的骨架还不够直观，下面用项目里**真实存在**的 `backend/routers/upload.py` 走一遍"一条接口从写出来到能被访问"的全过程。

**第 1 步：在 upload.py 里建一个 router 实例 + 定义接口**

```python
# backend/routers/upload.py  （节选，确为真实代码）
from fastapi import APIRouter, HTTPException, Body
from backend.services.session_manager import manager

router = APIRouter()          # ① 先建一个"分机模块"路由实例

@router.post("/upload/gate")  # ② 在这个 router 上登记一条路由
async def upload_gate(session_id: str = Body(..., embed=True)):
    """预约数据插槽闸门：在真正传文件前调用。"""
    if not session_id:
        raise HTTPException(status_code=400, detail="缺少 session_id")
    return manager.acquire_for_upload(session_id)
```

> 此时 `upload_gate` 只是模块里的一个函数，**没有任何 URL 能访问到它**。它还在"待接线"状态。

**第 2 步：在 main.py 把它"插"到总机 app 上**

```python
# backend/main.py  L51
app.include_router(upload.router, prefix="/api", tags=["数据上传"])
```

这一行 = "把整个 upload 分机模块插到总机 app 上，并统一加 `/api` 区号前缀"。插上之后：

```
router 内路径 "/upload/gate"   +   prefix "/api"   =   POST /api/upload/gate
```

**第 3 步：前端现在能真正调到了**

```typescript
// frontend 调接口时，URL 必须写成 POST /api/upload/gate 才对得上
await client.post("/api/upload/gate", { session_id: "abc123" })
```

> 三层心智模型（沿用 [[路由是什么]] 的"电话总机"比喻）：
> - `APIRouter()` = 一个**分机模块**（按业务拆出来的小路由表）
> - `@router.post("/upload/gate")` = 在该模块上登记"门牌号 → 坐席函数"
> - `app.include_router(...)` = 把整个模块**插到总机 app 上**并统一加 `/api` 前缀，此时里面的函数才真正对外可达

**为什么必须先 `include_router` 才能访问？** 因为 URL 匹配表只存在于 `app` 上。`upload.py` 自己只是个普通 Python 模块，里面的 `@router.xxx` 只是"往 `router` 这个局部登记表里记了一笔"；只有 `app.include_router` 把这笔记录**合并**进 `app` 的全局登记表，请求打到 `app` 时才找得到对应函数。漏挂 = 访问 404。

**项目 10 个 Router 文件**：

```
routers/
├── upload.py       # 上传
├── data.py         # 数据操作
├── clean.py        # 清洗
├── stats.py        # 统计
├── chart.py        # 图表
├── dashboard.py    # 驾驶舱
├── insights.py     # AI 洞察
├── report.py       # 报告
├── analysis.py     # 分析
└── reasoning.py    # 业务推理
```

### ④ Pydantic 模型（请求校验）

定义 Python class 描述请求格式，FastAPI 自动校验传入的 JSON：

```python
from pydantic import BaseModel

class ChartRequest(BaseModel):
    session_id: str          # 必填，字符串
    x: str                   # 必填
    y: str                   # 必填
    chart_type: str = "bar"  # 可选，默认 "bar"
```

FastAPI 自动做：字段存在性校验 → 类型匹配校验 → 默认值补全。不通过返回 **422**。

### ⑤ 依赖注入

FastAPI 把形参中声明的 Pydantic 模型自动从请求体解析注入：

```python
@router.post("/clean/missing-report")
async def api_missing_report(req: SessionRequest):  # req 自动解析
```

## 中间件

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 开发时允许所有域名
    allow_methods=["*"],
    allow_headers=["*"],
)
```

CORS 中间件告诉浏览器"后端允许跨域请求"。前端 `localhost:5173` 才能访问 `localhost:8001`。

## 全局异常处理器

```python
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"{exc.__class__.__name__}: {str(exc)}",
            "traceback": tb if os.getenv("DEBUG") == "1" else None,
        }
    )
```

统一拦截所有未处理异常，返回结构化错误信息，避免前端只看到空白 "Network Error"。

## 请求全链路

```
POST /api/dashboard/cards  {"session_id": "abc123"}
        │
   ① Pydantic 校验 → session_id 是否存在
        │
   ② 路由匹配 → dashboard.py @router.post("/dashboard/cards")
        │
   ③ 处理函数 → card_generator.generate_cards(...)
        │
   ④ 返回 dict → FastAPI 自动 JSON 序列化
        │
   ⑤ 响应返回前端
```

## 为什么选 FastAPI（对比 Flask）

| 对比项 | Flask | FastAPI |
|---|---|---|
| 数据校验 | 手动 `request.json.get(...)` + try/except | Pydantic 自动校验 |
| 文档 | 需装 flasgger | **自动生成** `/docs` |
| 性能 | 同步 | 异步 |
| 响应序列化 | `jsonify(dict)` | 直接 return dict |

## 相关笔记

- [[API调用是什么]] —— 本项目的两层 API 调用
- [[RESTful API是什么]] —— Restful 设计风格
- [[Swagger文档是什么]] —— FastAPI 自动生成的 /docs 接口文档
- [[代码即文档]] —— 为什么"代码即文档"、逐行对应文档
- [[为什么要写API文档]] —— 自动文档覆盖形状，边界/降级仍需人写
- [[API的构成与种类]] —— 三件套只是 Web API 特征，AI API 角色相反
- [[PRD_DataMind_AI]] —— 产品的接口与依赖说明
