---
title: LLM JSON 字段名漂移
aliases: [insights与ins不一致, key drift, 模型输出格式不稳定]
tags: [后端, LLM, 调试]
created: 2026-07-18
---

# LLM JSON 字段名漂移

> 当后端用 `json.loads` 解析 LLM 返回的 JSON、并**写死某个字段名**取值时，一旦模型改用另一个近义 key（如 `insights` ↔ `ins`），解析就会失败并回退到原始字符串，前端把整段 JSON 当文本裸显。

## 真实案例（本项目 2026-07-18）

- 现象：「数据洞察报告」与「AI 对话框」返回的文字整段是 `{"ins": "## 数据概览\n本次分析...}` 开头的裸 JSON，Markdown 未渲染。
- 根因：`backend/routers/insights.py` 的 `_parse_ai_result_to_intents` 写死 `data.get("insights", result)`；但 DeepSeek 实际输出 key 为 `ins` → `get` 返回 `None` → 回退到整段原始 JSON 字符串。
- prompt（`src/ai_agent/prompts.py` 的 `INSIGHTS_SYSTEM_PROMPT` / `INSIGHTS_USER_PROMPT_TEMPLATE`）明明示范的是 `insights`，说明**模型没有严格遵守字段名**。

## 为什么"之前没问题、现在爆了"

按可能性排序：

1. **LLM 输出格式本身不稳定（最可能是主因）**：同一 prompt 多次调用可能给出不同 key。之前恰好命中 `insights`，现在命中 `ins`。这是埋了很久的**偶发地雷（flaky bug）**，不是新引入的回归。
2. **模型/供应商端静默升级**：DeepSeek API 在服务端更新模型版本，新版本 JSON 输出习惯变化（更倾向缩写 `ins`），你无感知。
3. **采样随机性**：若调用 `temperature > 0`，像"key 叫 insights 还是 ins"这种非语义格式细节最易漂移。
4. **"之前没问题"是误判/没测到该路径**：可能之前修的是另一个 bug（如 markdown 未渲染），与本次"根本没有 Markdown、只有裸 JSON"并存却被忽略。
5. **输入数据 `{data_summary}` 差异的次要影响**：不同数据集的摘要可能轻微引导模型对 key 命名的联想。
6. **后端进程/部署环境不一致**：若生产后端是常驻进程且一直没重启、代码也没变，则后端逻辑始终一样，只能是 LLM 输出变了。
7. **响应截断（可能性低）**：若 LLM 响应超长被截断，旧兜底会直接返回 raw；但结构完整的 `{"ins": ...}` 更像完整 JSON。

## 排查套路

- 屏幕显示 `{"xxx":` 且 `\n` 是字面量 → 基本可断定为"**原始 JSON 字符串被当文本渲染**"，根因在**后端解析层**，不在前端 `renderMarkdown`。
- 先搜这个字段名从哪里来、前端怎么取、后端怎么构造，确认是 key 不匹配还是序列化问题。
- 看 prompt 实际示范的 key，与代码 `get()` 的 key 是否一致。

## 根治做法（本项目已落地）

**不要依赖模型遵守字段名，在解析层做 key 兼容 + 容错**：

- 洞察文本：`data.get("insights") or data.get("ins")`，皆空再回退 raw。
- intents 同理兼容 `intents` / `intent`。
- 整体 `json.loads` 失败时，用逐字符扫描从原始文本抽取 `"ins"/"insights"` 字符串值并反转义（`\n`→换行、`\"`→引号、`\\`→反斜杠）作为可读 Markdown 返回，形成**双层防护**。
- 不改 prompt（避免引入新漂移），不依赖模型行为。

## 相关

- [[后端技术栈]] · [[代码文件总览]]（定位 `insights.py` / `prompts.py`）
- [[双层防护架构]]（解析层 + sanitize_json 全局兜底）
