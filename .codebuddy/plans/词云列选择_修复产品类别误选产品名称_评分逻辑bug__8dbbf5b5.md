---
name: 词云列选择:修复产品类别误选产品名称(评分逻辑bug)
overview: 词云选列时"产品类别"因DIMENSION_KEYWORDS中"品类"误命中(产品类别含"品类"子串)导致 kw_hits=3,胜过产品名称的 kw_hits=2。改为「最长匹配子串长度」加权 + 移除"品类"歧义词 + 实体命中改为「整列名包含该实体的同义词」加权,让更精确的列(产品名称、产品类别)按列名长度公平比较。
todos:
  - id: remove-ambiguous-keyword
    content: 改 src/column_classifier.py 的 DIMENSION_KEYWORDS,移除「品类」(与「产品类别」歧义且被「产品」覆盖)
    status: completed
---

## Product Overview

修复词云列选择错误:用户点击「哪些产品最畅销?」问题后,前端副标题已正确显示「产品名称词云分析」,但实际词云图统计的是「产品类别」列的词频,而非「产品名称」列的词频。需要让 `select_wordcloud_column` 在两个候选列同时包含问题实体时,优先选列名更精确(完整匹配问题语义实体)且基数更高(更细粒度)的列。

## Core Features

- 数据集「业务数据.csv」含 `产品类别` (nunique=4) 与 `产品名称` (nunique=11) 两列,用户期望选「产品名称」
- 当前 bug:`DIMENSION_KEYWORDS` 含「品类」作为子串命中「产品类别」,导致 `产品类别` kw_hits=3,「产品名称」kw_hits=2,总分 13 > 10,选错列
- 修复后:用「最长匹配子串长度」衡量精确度,「产品名称」(最长 4 字)与「产品类别」(最长 4 字)平手时按 nunique 降序 → 选「产品名称」
- 同时移除「品类」这一会引起歧义误命中的关键词

## Tech Stack

- 后端:Python (pandas + src/column_classifier.py)
- 不涉及前端/CSS/组件库改动,只改后端列选逻辑

## Implementation Approach

- **方法**:`src/column_classifier.py` 中 `DIMENSION_KEYWORDS` 移除「品类」(其语义被「产品」「产品类别」覆盖,且会与「产品类别」形成子串歧义),并把 `select_wordcloud_column` 的评分从「命中数」改为「最长匹配子串长度」,使「产品名称」与「产品类别」平手时由 nunique 降序决定胜者。
- **关键决策**:
- 「品类」移除而非「产品类别」保留更细粒度:中文里「产品名称」与「产品类别」是两个互斥的语义轴,选哪个取决于用户意图(更细粒度的优先)。保留「产品类别」作候选,「产品名称」靠 nunique 胜出。
- 评分函数改 `max(len(kw) for kw in matched_kws)` 而非 `len(matched_kws)`:体现「列名越精确(关键词越长)优先」的直觉。
- 实体命中加分保留(+2),但只有当列名完整包含某实体的同义词(整词匹配)时加分,避免「产品」在两列都加 2 分导致无区分。
- **性能**:纯字符串匹配 + nunique 调用,O(列数 × 关键词数),无新增性能开销。

## Implementation Notes

- 仅改后端 `src/column_classifier.py`,不影响前端、VDS 色板、导出 HTML 链路。
- 排序键保持 `(-exact_score, -nunique)`,并列时高基数列胜出。
- `get_category_columns` 也用了 `DIMENSION_KEYWORDS`,移除「品类」对该函数有副作用:会让 `产品类别` 退到「任何非数值字符串列」的二次过滤分支。但 `get_category_columns` 还有第二条规则(非数值 string 列且 nunique<max(20, len*0.3))兜底,96 行数据下「产品类别」nunique=4 仍会被识别为分类列,无功能影响。

## Directory Structure

```
d:/数据分析项目/
└── src/
    └── column_classifier.py  # [MODIFY] 移除「品类」关键词 + select_wordcloud_column 评分改用最长匹配子串长度
```