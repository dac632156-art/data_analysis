---
title: 数据清洗的AI规则（prompt约束）
aliases: [AI清洗规则, 清洗prompt, clean.py规则, 数据清洗prompt约束]
tags: [tech/backend, 核心概念, prompt工程]
created: 2026-07-18
---

# 数据清洗的 AI 规则（prompt 约束）

> 对应代码：`backend/routers/clean.py` 的 AI 清洗接口（`/api/clean/ai` 一类）。
> 讲清楚三件事：① AI 在这个流程里到底干不干活；② 后端给 AI 定了多少条规则、哪几条是 **prompt 约束**；③ 这些约束在代码里是怎么"兜住"的。

## 一、核心架构：AI 当参谋，不掌刀

数据清洗不是让大模型直接改你的 DataFrame，而是分两层：

```
用户需求文本 ──→  [prompt 约束]  ──→  AI 出"清洗计划 JSON"
                                          │
                                          ▼
                              后端 if/elif 接住 ──→  pandas 函数真正改数据
                                  (确定性代码、有备份、失败回滚)
```

| 角色 | 干的事 | 本质 |
|---|---|---|
| **AI（大模型）** | 读数据摘要 + 用户需求，返回一个「清洗计划 JSON」 | 参谋，只出方案 |
| **后端 pandas 代码** | 按 JSON 里的动作真正执行 `fill_missing` / 异常值 / 类型转换 | 刀斧手，动手 |

所以 prompt 里那堆规则，**约束的是"AI 怎么出方案"，不是"AI 怎么改数据"**。真正动数据的永远是后端写死的 `handle_missing_values` / `handle_outliers` / `convert_column_type`。

> ⚠️ 本系统**不支持删除重复行（去重）**。`drop_duplicate_rows` 函数与 `/clean/drop-duplicates` 路由已于 2026-07-24 移除，prompt 的动作空间也不含 `drop_duplicates`，即使 AI 误返回该 action 也会落 `except` 被跳过，绝不真正去重。

## 二、AI 能从 3 种 action 里挑（动作空间）

AI 返回的 `steps` 数组里每个动作，后端用 `if/elif` 链（见下方）逐一接住执行：

| action | 含义 | 要填的参数 | 后端实际执行函数 |
|---|---|---|---|
| `fill_missing` | 填充缺失值 | `column` + `method`（`fill_mean`/`fill_median`/`fill_mode`/`fill_0`/`fill_unknown`/`drop`） | `handle_missing_values(df, column, method)` |
| `handle_outliers` | 处理异常值 | `column` + `method`（`iqr`/`zscore`）+ `do`（`remove`/`cap`） | `handle_outliers(df, column, method, do)` |
| `convert_type` | 转换列类型 | `column` + `target_type`（`numeric`/`datetime`/`string`/`category`） | `convert_column_type(df, column, target)` |

> 注意 `drop` 被塞进了 `fill_missing` 的 `method` 里——"删某列的缺失行"是伪装成 fill_missing 实现的（代码里若 `change > 0` 说明删了行）。

后端接住动作的代码片段（`clean.py` 约 L329-358）：

```python
# clean.py L329-358（节选）
if action == "fill_missing" and column:
    method = step.get("method", "fill_mean")        # ← method 默认就是 fill_mean
    df_before = df.copy()
    df = handle_missing_values(df, column, method)
    change = len(df_before) - len(df)
    ...
elif action == "handle_outliers" and column:
    method = step.get("method", "iqr")
    do = step.get("do", "remove")
    df = handle_outliers(df, column, method, do)
    ...
elif action == "convert_type" and column:
    target = step.get("target_type", "string")
    df = convert_column_type(df, column, target)
    ...
```

## 三、5 条"注意"——全部是 prompt 约束 🔒

> 🔒 = 在 prompt 文本里给 AI 划的边界（constraint / guardrail）。后端还额外用代码兜底，但"提出约束"这一动作发生在 prompt 层。

| # | 约束原文 | 约束类型 | 后端兜底手段 |
|---|---|---|---|
| 1 | 🔒 "只返回 JSON，不要有任何其他文字" | **输出格式约束**（结构化输出） | `json.loads` 解析；若含 ``` ``` 代码块则抠中间（L308-312） |
| 2 | 🔒 "action 必须是 3 种之一" | **动作空间约束**（限制可选项） | `if/elif` 全不匹配 → 落 `except` → 该步标记失败"跳过"（L360-362） |
| 3 | 🔒 "用户没明确说明，不要随意删除数据" + "严禁删除重复行" | **行为安全约束**（防止危险操作） | 删行类动作（`drop`/`remove`）不可逆，靠约束而非代码拦；去重已被函数/路由/prompt 三层彻底关闭 |
| 4 | 🔒 "步骤不适用数据就别包含" | **条件约束** | 后端执行前会再检查，不适用时 `except` 失败跳过 |
| 5 | 🔒 "优先 fill_mean，分类列用 fill_mode" | **默认偏好约束** | `step.get("method", "fill_mean")` 默认均值；分类列建议众数 |

**逐条解释：**

- **约束 1（格式）**：因为后端 `json.loads(text)` 直接解析（L314），AI 若前后加废话就炸。代码兜底了 ``` ``` 包裹，但"别加废话"是 prompt 层的硬要求。
- **约束 2（动作空间）**：这是**防 AI 乱删列的硬约束**。AI 若返回第 4 种动作（如 `drop_duplicates` / `delete_column`），所有分支不命中 → 该步被标失败跳过，数据不损坏。
- **约束 3（安全）**：针对会减行数的动作（`fill_missing` 的 `drop`、`handle_outliers` 的 `remove`）。删行不可逆，所以默认倾向"填"而非"删"。这是 prompt 在定**行为倾向**，代码没法 100% 拦住（AI 真要删，代码还是会执行），所以靠规则前置约束。**注意：本系统已彻底关闭去重**（`drop_duplicate_rows` 函数删除、`/clean/drop-duplicates` 路由删除、prompt 动作空间不含且明令禁止），AI 即便返回 `drop_duplicates` 也会被 `except` 跳过，不可能真正删除重复行。
- **约束 4（条件）**：比如没缺失值就别硬塞 `fill_missing`。AI 自己判断能减少无效步骤、规避误删。
- **约束 5（默认偏好）**：`method` 默认 `fill_mean`（L330）。数值列缺值用均值/中位数填（比填 0 科学），文本/类别列用众数（分类列算均值没意义）。

## 四、这些约束是怎么"兜住"数据的（安全网）

即使 AI 违反约束，后端也有三道**代码级**兜底，和 prompt 约束**互补**：

| 兜底 | 位置 | 作用 |
|---|---|---|
| **Undo 点** | `manager.push_undo_state`（L326） | 每步前先存撤销点 |
| **DataFrame 备份** | `df_backup = df.copy()`（L327） | 单步失败 `df = df_backup` 恢复（L361） |
| **未知动作跳过** | `except` 分支（L360-362） | 第 5 种 action 或执行报错 → 标失败、不损坏数据 |

> 所以整条链路是「**prompt 约束（前置防呆）+ 确定性代码（真正执行）+ 备份回滚（兜底）**」三层保险。详见 [[路由是什么]]（clean 模块路由在此注册）与 [[数据清洗兜底机制]]（三层兜底详解）。

## 五、概念辨析：约束 vs 调优

这 5 条"注意"本质都是「**给 prompt 加约束**」这一手法（限制输出格式 / 动作 / 行为）。

而「**prompt 调优**」是另一个维度的概念——指反复改 prompt、跑测试、看输出质量再迭代的过程。加约束只是调优过程中常用的手段之一：

```
prompt 调优（过程）
  ├─ 加约束（手法之一）：本笔记的 5 条"注意"
  ├─ 加示例（few-shot）
  ├─ 改措辞：让指令更清晰
  └─ 调 temperature / max_tokens（本接口 temperature=0.2，见 L299）
```

- 这 5 条"注意" = **加约束**（具体手法）✅
- 它是不是"调优过的结果" = 代码看不出来，取决于历史是否迭代过 ❓


## 六、兜底机制
1.防止ai清洗错误：在ai每一次进行操作前，拍一次快照，用户觉得有问题时可以回撤（防止ai乱改，用户不满意；快照是每次修改都拍，可以退回n次操作前）
2.防止ai给用户脏数据：当ai执行操作一半时出现异常，此时数据已经脏了，所以在每次执行前，都会拍最新的快照，有问题时，那上次的快照进行重新清洗（防止清洗一半的脏数据直接返回前端给用户）
3.防止程序卡死：异常跳过——出现异常时，直接跳过异常，然后记录异常，继续循环跳到快照，并将最新快照返回给用户（不跳过的话程序会卡死，前端收不到返回结果）


## 七、相关笔记

- [[路由是什么]] —— `/api/clean/*` 路由在 clean.py 注册，AI 清洗是其中一路
- [[API调用是什么]] —— 后端经 OpenAI SDK 调 LLM 的第二层调用，本 prompt 就塞进 `messages` 发出去
- [[FastAPI详解]] —— 处理函数如何 return dict 自动序列化，AI 计划 JSON 原样回传前端
- [[LLM JSON 字段名漂移]] —— 另一个"AI 输出 JSON 不可控"的坑，与本笔记"约束输出格式"同源
