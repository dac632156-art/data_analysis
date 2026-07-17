---
title: Swagger 文档是什么
aliases: [Swagger, OpenAPI, /docs]
tags: [tech/backend, 工具]
created: 2026-07-16
---

# Swagger 文档是什么

## 两个名字的关系

- **OpenAPI**：接口描述标准（JSON / YAML 格式），描述所有 API 的路径、参数、返回值
- **Swagger**：围绕 OpenAPI 的工具集，常用的是 **Swagger UI**——把描述渲染成可点击、可发请求测试的网页

> "FastAPI 自动生成 Swagger 文档" = FastAPI 自动写 OpenAPI 描述 + 自动渲染成 Swagger UI 网页，不用手写文档。

## 为什么叫"自动"

传统做法（Flask）：手动写文档到 Markdown，或用插件，经常代码改了文档没改，对不上。

FastAPI：你写的代码本身就是"接口声明"：

```python
@router.post("/clean/missing-report")
async def api_missing_report(req: SessionRequest):
```

FastAPI 自动提取：
- 路径 `/clean/missing-report`、方法 `POST`
- 参数 `SessionRequest`（Pydantic）→ 自动知道需要 `session_id: str`
- 函数返回值 → 自动知道响应结构

**代码即文档，二者永远同步。**

## 怎么用

启动后端后，浏览器打开：

```
http://localhost:8001/docs        ← Swagger UI（可点击测试）
http://localhost:8001/redoc       ← ReDoc（另一种排版）
```

`/docs` 页面功能：
- 左侧列出所有 API（按 tag 分组）
- 点开任意接口 → 显示参数说明（必填 / 类型）
- **"Try it out"** 按钮 → 填参数 → 直接发请求 → 看真实返回
- 等于自带接口调试工具，无需 Postman

## 一句话

**自动生成 Swagger 文档 = FastAPI 把代码（路由 + Pydantic 模型）自动翻译成可在网页浏览、可点击测试的接口文档，代码即文档，永不脱节。**

## 相关笔记

- [[FastAPI详解]] —— 本项目后端框架，Swagger 是其特性之一
- [[RESTful API是什么]] —— 被 Swagger 文档化的接口遵循的设计风格
- [[代码即文档]] —— "代码即文档"是 Swagger 文档的来源原理
- [[为什么要写API文档]] —— 自动文档覆盖形状，边界/降级仍需人写
