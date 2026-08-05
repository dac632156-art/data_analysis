"""LLMLayoutEngine —— 大模型排版决策（输出 选图 + 形状 + 槽位）。

流程：
   候选清单(candidates) ──┐
                          ├─→ LLM 业务判断 ─→ placements[] (slot_id + shape + chart_ref)
   固定蓝图(blueprint) ────┘                         ↓
                                         前端纯函数按 slot_id+shape 路由落位
                                         后端用 sbv×0.6 + llm×0.4 算兜底权重

设计约束（防止 token 爆炸 + 稳定）：
- 只把「候选清单」（几百 token，无完整 option）喂给 LLM
- LLM 在【固定蓝图】的槽位里做单选题：为每张候选图挑一个 shape 槽位，并声明它的 chart_type
- 用 response_format=json_object 锁结构，避免冗余自然语言
- LLM 不可达 / 解析失败时，回退为「按 sbv 排序 + attention_weight 兜底」的规则布局，保证大屏始终可渲染

参考：可视化模板库/同期群分析/智能排版引擎架构改造计划.md
     （蓝图 + 形状-槽位语义绑定 + 降级调度，LLM 只做「把图挂到固定槽位」的单选题）
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 两段式融合权重（仅用于 LLM 不可达 / 未给 shape 时的兜底打分）
SBV_WEIGHT = 0.6
LLM_WEIGHT = 0.4

# ============================================================
# 固定空间蓝图（Bento-box 12 列网格）
# LLM 只能在下列槽位里选；每个槽位有固定的 shape 语义。
# ============================================================
BLUEPRINT = {
    "columns": 12,
    "rows": [
        {
            "row": 1,
            "height": "auto",
            "slots": [
                {"slot_id": "kpi_1", "shape": "kpi", "col_span": 4},
                {"slot_id": "kpi_2", "shape": "kpi", "col_span": 4},
                {"slot_id": "kpi_3", "shape": "kpi", "col_span": 4},
            ],
        },
        {
            "row": 2,
            "height": "2.2fr",
            "slots": [
                {"slot_id": "side_strip_left", "shape": "side_strip", "col_span": 3},
                {"slot_id": "hero_square", "shape": "hero_square", "col_span": 6},
                {"slot_id": "side_strip_right", "shape": "side_strip", "col_span": 3},
            ],
        },
        {
            "row": 3,
            "height": "2fr",
            "slots": [
                {"slot_id": "hero_wide_left", "shape": "hero_wide", "col_span": 6},
                {"slot_id": "side_square", "shape": "side_square", "col_span": 3},
                {"slot_id": "side_tail", "shape": "side_square", "col_span": 3},
            ],
        },
        {
            "row": 4,
            "height": "2.6fr",
            "slots": [
                {"slot_id": "full_wide", "shape": "full_width", "col_span": 12},
            ],
        },
    ],
    "overflow_rows": [
        {"slot_id": "extra_wide_1", "shape": "hero_wide", "col_span": 6},
        {"slot_id": "extra_wide_2", "shape": "hero_wide", "col_span": 6},
    ],
}

# ============================================================
# 形状 → 图表类型映射（LLM 据此声明每张图的 shape）
# ============================================================
SHAPE_HINTS = {
    "kpi":          "指标卡 / 数字卡片（chart_type=metric / kpi）。≥4 个 KPI 时聚拢为 2x2 KPI 组（kpi_grid_*），不要全塞一行。",
    "hero_square":  "中央核心大图，适合饼图/环形图/雷达图 (pie/ring/radar) 或 漏斗 (funnel)",
    "side_strip":   "侧边窄长条图，适合排行图 / 横向柱状 (ranking/hbar/bar)",
    "hero_wide":    "横向宽屏大图，适合折线/双轴/面积/多系列 (line/dual/area)",
    "side_square":  "侧边方块图，适合小饼图/环形/条形 (pie/ring/hbar)",
    "side_tail":    "侧边尾部方块，适合分布/占比类小图 (pie/ring/bar)",
    "full_width":   "整行全宽大图，适合明细表 / 同期群热力 / 超长排行 / 全局双轴趋势 (table/cohort_heatmap/ranking/dual)",
}

# ============================================================
# 排版模式（LLM 按候选数量与候选类型自适应选模式）
# 三种模式直接对应你的三张参考图
# ============================================================
LAYOUT_PATTERNS = """
# 排版模式选择（按候选清单自适应）
# 模式A 「核心聚拢式」：候选里 1 张环形/饼图 + 1 张排行 + 1 张趋势 → 中央大环形 + 两侧窄条 + 底部宽屏
# 模式B 「上图下表式」：候选里有明细表 → 顶部 KPI+主图，下半部全宽明细表
# 模式C 「宽幅压顶式」：候选里有全局双轴/趋势主图 → 这张图单独占顶部 12 列全宽，其他并排挤下方
"""

# ============================================================
# 降级调度规则（shape 槽位无对应图时自动降级）
# ============================================================
DEGRADE_RULES = """
# 降级调度（Degradation）
- 每个 shape 槽位只接收语义匹配的 chart_type；若候选清单里没有匹配类型，按以下规则降级填补：
  - hero_square 缺 pie/ring/radar/funnel → 用 line/area 兜底（仍占中央 6 列）
  - side_strip 缺 ranking/hbar/bar → 用 pie/ring 兜底（窄条里塞小饼）
  - hero_wide 缺 line/dual/area → 用 bar/hbar 兜底
  - full_width 缺 table/cohort → 用 ranking 兜底（长排行全宽）
- KPI 数量自适应：
  - 1~3 个 KPI → 全部挂 kpi_1/kpi_2/kpi_3（横排）
  - 4~6 个 KPI → 聚拢为 2x2 KPI 组（kpi_grid_1/2/3/4），其余不挂
  - ≥7 个 KPI → 聚拢 2x2 + 底部加 KPI 行（kpi_5/6/7…）
- 不允许一个候选图同时挂到多个槽位；也不允许把宽屏图塞进 side_strip（会挤压）。
- 候选清单里多余的图（蓝图槽位已满）按顺序填入 overflow_rows（6-6 等宽宽屏行）。
- 模式选择引导：
  - 候选里同时出现 ring/pie + ranking/hbar + line/area → 优先模式A（hero_square 中央 + 两侧 side_strip）
  - 候选里有 table 且 ≥4 张主图 → 优先模式B（底部 full_width 表 + 上方双轴/雷达平分）
  - 候选里出现 dual（双轴全局趋势）且其他候选 ≥3 张小图 → 优先模式C（dual 全宽 + 下方并排小卡）
"""

# ============================================================
# Few-shot 示例（直接来自你提供的 3 张参考图）
# ============================================================

# 示例1：图1 核心聚拢式（环形中央 + 排行/漏斗两侧 + 趋势折线底部）
FEW_SHOT_USER_1 = json.dumps({
    "candidates": [
        {"slot": "total_revenue", "title": "总营收", "chart_type": "metric"},
        {"slot": "sales_ring",    "title": "销售额拆解", "chart_type": "ring"},
        {"slot": "product_rank",  "title": "产品销量排行", "chart_type": "ranking"},
        {"slot": "sales_funnel",  "title": "销售漏斗", "chart_type": "funnel"},
        {"slot": "dau_trend",     "title": "DAU 趋势", "chart_type": "line"},
    ]
}, ensure_ascii=False)
FEW_SHOT_ASSISTANT_1 = json.dumps({
    "placements": [
        {"slot_id": "kpi_1",            "chart_ref": "total_revenue", "shape": "kpi"},
        {"slot_id": "side_strip_left",  "chart_ref": "product_rank",  "shape": "side_strip"},
        {"slot_id": "hero_square",      "chart_ref": "sales_ring",    "shape": "hero_square"},
        {"slot_id": "side_strip_right", "chart_ref": "sales_funnel",  "shape": "side_strip"},
        {"slot_id": "hero_wide_left",   "chart_ref": "dau_trend",     "shape": "hero_wide"},
    ]
}, ensure_ascii=False)

# 示例2：图2 上图下表式（双轴 + 雷达平分上半 + 全宽明细表垫底）
FEW_SHOT_USER_2 = json.dumps({
    "candidates": [
        {"slot": "total_arr",   "title": "总 ARR",                 "chart_type": "metric"},
        {"slot": "rev_target",  "title": "营收与目标趋势",          "chart_type": "dual"},
        {"slot": "seg_radar",   "title": "客户分层表现",            "chart_type": "radar"},
        {"slot": "team_table",  "title": "销售团队业绩明细",        "chart_type": "table"},
    ]
}, ensure_ascii=False)
FEW_SHOT_ASSISTANT_2 = json.dumps({
    "placements": [
        {"slot_id": "kpi_1",            "chart_ref": "total_arr",   "shape": "kpi"},
        {"slot_id": "hero_wide_left",   "chart_ref": "rev_target",  "shape": "hero_wide"},
        {"slot_id": "hero_wide_right",  "chart_ref": "seg_radar",   "shape": "hero_wide"},
        {"slot_id": "full_wide",        "chart_ref": "team_table",  "shape": "full_width"},
    ]
}, ensure_ascii=False)

# 示例3：图3 宽幅压顶式（双轴趋势全宽顶部 + 漏斗/雷达/热力/2x2KPI 并排下方）
FEW_SHOT_USER_3 = json.dumps({
    "candidates": [
        {"slot": "b2b_trend",     "title": "B2B 销售表现",        "chart_type": "dual"},
        {"slot": "b2b_funnel",    "title": "B2B 销售漏斗",        "chart_type": "funnel"},
        {"slot": "prod_radar",    "title": "产品线指标",          "chart_type": "radar"},
        {"slot": "retention_heat","title": "月度用户留存",        "chart_type": "cohort_heatmap"},
        {"slot": "kpi_revenue",   "title": "Total Revenue",       "chart_type": "metric"},
        {"slot": "kpi_aov",       "title": "Avg. Order Value",    "chart_type": "metric"},
        {"slot": "kpi_new_cust",  "title": "New Customers",       "chart_type": "metric"},
        {"slot": "kpi_growth",    "title": "Order Growth",        "chart_type": "metric"},
    ]
}, ensure_ascii=False)
FEW_SHOT_ASSISTANT_3 = json.dumps({
    "placements": [
        # 顶部：双轴趋势全宽压顶
        {"slot_id": "full_wide",     "chart_ref": "b2b_trend",      "shape": "full_width"},
        # 下方：4 卡并排（漏斗/雷达/热力/2x2 KPI 组）
        {"slot_id": "side_strip_left",  "chart_ref": "b2b_funnel",     "shape": "side_strip"},
        {"slot_id": "side_strip_right", "chart_ref": "prod_radar",     "shape": "side_strip"},
        {"slot_id": "side_square",      "chart_ref": "retention_heat", "shape": "side_square"},
        {"slot_id": "kpi_grid_1",       "chart_ref": "kpi_revenue",    "shape": "kpi"},
        {"slot_id": "kpi_grid_2",       "chart_ref": "kpi_aov",        "shape": "kpi"},
        {"slot_id": "kpi_grid_3",       "chart_ref": "kpi_new_cust",   "shape": "kpi"},
        {"slot_id": "kpi_grid_4",       "chart_ref": "kpi_growth",     "shape": "kpi"},
    ]
}, ensure_ascii=False)

_SYSTEM_PROMPT = """# Role
你是一位精通现代 Bento-box 网格布局与数据叙事的资深可视化排版专家。

# 固定空间蓝图（Blueprint）
下面是一块 12 列网格大屏的固定槽位。你**只能**在这些槽位里挂图，不能自由创建坐标或槽位：

{blueprint}

# 形状语义（Shape）
每个槽位有固定 shape，接收的图表类型如下：
{shape_hints}

# Task
下面是一份「候选图表清单」（每张图含元信息：类型/标题）。
你的任务：为清单里**尽可能多**的图，挑一个**语义匹配**的蓝图槽位挂上去，输出 placements 数组。
- 每张候选图最多挂一个槽位（slot_id 不可重复）。
- chart_ref = 候选图里的 slot 值；shape = 你选的槽位 shape（必须与蓝图一致）。
- 优先把「核心业务图」挂到 hero_square / hero_wide / full_width；KPI 卡挂 kpi_1/kpi_2/kpi_3 或 kpi_grid_1~4（按数量聚拢）。
- 候选图多于蓝图槽位时，多余的按 F 顺序填入 overflow_rows（extra_wide_1 / extra_wide_2 ...）。
- 若候选图类型与所有空槽位都不匹配，宁可留空槽位，也不要把宽屏图硬塞进窄条（参考降级规则）。
- **注意学习以下 3 个示例里的「图文挂位手感」**（这是设计意图的体现）：
  - 示例1（参考图1 核心聚拢式）：环形图（ring）放 hero_square 中央；排行图（ranking）放 side_strip；趋势（line）放 hero_wide 宽屏
  - 示例2（参考图2 上图下表式）：双轴（dual）+ 雷达（radar）平分 hero_wide_left/right；明细表（table）独占 full_wide 整行
  - 示例3（参考图3 宽幅压顶式）：双轴趋势（dual）独占顶部 full_wide 压顶；下方并排 side_strip/side_square/2x2 KPI 组

{layout_patterns}

{degrade_rules}

# Output Format
严格且只输出 JSON 格式，不含任何 Markdown 代码块包裹（不要输出 ```json），禁止任何解释性文本。
必须为清单中【每一个】候选图都给出 placement（遗漏将导致排版引擎崩溃）。
格式示范：
{"placements":[{"slot_id":"<蓝图槽位>","chart_ref":"<候选slot>","shape":"<槽位shape>"}]}
"""


@dataclass
class LayoutItem:
    slot: str
    title: str
    chart_type: str
    analysis_type: str
    suggested_business_value: float
    llm_weight: float
    attention_weight: float          # 融合后的最终权重
    # ★ 阶段B：LLM 直接输出的形状-槽位绑定（无则 None，前端按 attention_weight 兜底路由）
    shape: Optional[str] = None       # kpi / hero_square / side_strip / hero_wide / side_square / full_width
    slot_id: Optional[str] = None     # 蓝图槽位 id
    dims: int = 0
    series_count: int = 0
    row_count: int = 0
    metric_hint: str = ""
    value_hint: str = ""
    is_aggregated: bool = True


@dataclass
class SmartLayoutResponse:
    items: List[LayoutItem]
    model: str
    source: str                     # "llm" | "fallback"
    note: str = ""


class LLMLayoutEngine:
    def __init__(self, api_key: str, base_url: Optional[str], model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = (model or "gpt-3.5-turbo").lower()

    # —— 主入口 ——
    def layout(
        self,
        candidates: List[Dict[str, Any]],
        fallback_profiles: List[Any] = None,
        llm_top_n: int = 12,
    ) -> SmartLayoutResponse:
        """candidates: ProfilingEngine.to_candidate_list_full() 的产出（全量）。
        fallback_profiles: 同批 ChartProfile 列表（全量，携带 sbv），用于融合与兜底。
        llm_top_n: 仅对 Top-N（按 sbv 降序）调用 LLM 精排，其余直接用 sbv 兜底，
                   既保证全量图表都能渲染，又控制 LLM token 消耗。
        """
        if not candidates:
            return SmartLayoutResponse(items=[], model=self.model, source="fallback",
                                       note="候选清单为空")

        # slot → 候选元信息 / profile 映射
        cand_map = {c["slot"]: c for c in candidates}
        prof_map = {}
        if fallback_profiles:
            prof_map = {p.slot: p for p in fallback_profiles}

        # 按 sbv 降序确定哪些候选进入 LLM 精排窗口
        ranked = sorted(candidates, key=lambda c: float(c.get("suggested_business_value", 0.5)), reverse=True)
        llm_slots = {c["slot"] for c in ranked[: max(1, llm_top_n)]}

        # 1) 只对 Top-N 调 LLM（失败则走兜底）
        llm_weights: Dict[str, float] = {}
        placement_map: Dict[str, Dict[str, str]] = {}   # chart_ref(slot) → {slot_id, shape}
        source = "llm"
        try:
            llm_weights, placement_map = self._call_llm(ranked[: max(1, llm_top_n)])
        except Exception as e:  # noqa: BLE001
            logger.warning(f"LLM 排版调用失败，回退规则布局: {e}")
            source = "fallback"

        # 2) 组装全量 items + 两段式融合
        items: List[LayoutItem] = []
        for c in candidates:
            slot = c["slot"]
            sbv = float(cand_map[slot].get("suggested_business_value",
                                           prof_map.get(slot).suggested_business_value
                                           if slot in prof_map else 0.5))
            if source == "llm" and slot in llm_slots:
                lw = float(llm_weights.get(slot, sbv))
            else:
                # 兜底：LLM 不可达 / 超出精排窗口 → 直接用先验分
                lw = sbv
            lw = max(0.0, min(1.0, lw))
            final = round(SBV_WEIGHT * sbv + LLM_WEIGHT * lw, 4)
            prof = prof_map.get(slot)
            # ★ 阶段B：LLM 直接给的形状-槽位绑定
            plc = placement_map.get(slot)
            items.append(LayoutItem(
                slot=slot,
                title=c.get("title", ""),
                chart_type=c.get("chart_type", "bar"),
                analysis_type=c.get("analysis_type", ""),
                suggested_business_value=round(sbv, 4),
                llm_weight=round(lw, 4),
                attention_weight=final,
                shape=plc.get("shape") if plc else None,
                slot_id=plc.get("slot_id") if plc else None,
                dims=int(c.get("dims", 0)),
                series_count=int(c.get("series_count", 0)),
                row_count=int(c.get("row_count", 0)),
                metric_hint=c.get("metric_hint", ""),
                value_hint=c.get("value_hint", ""),
                is_aggregated=bool(c.get("is_aggregated", True)),
            ))

        # 3) 按最终权重降序
        items.sort(key=lambda it: it.attention_weight, reverse=True)
        note = "" if source == "llm" else "LLM 不可用，已回退为后端规则排版"
        return SmartLayoutResponse(items=items, model=self.model, source=source, note=note)

    # —— LLM 调用（openai SDK，与 dashboard.py 现有调用一致） ——
    def _call_llm(
        self, candidates: List[Dict[str, Any]]
    ) -> "tuple[Dict[str, float], Dict[str, Dict[str, str]]]":
        import openai

        client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url or None,
            timeout=30.0,
        )
        system_content = _SYSTEM_PROMPT.format(
            blueprint=json.dumps(BLUEPRINT, ensure_ascii=False, indent=2),
            shape_hints="\n".join(f"- {k}: {v}" for k, v in SHAPE_HINTS.items()),
            layout_patterns=LAYOUT_PATTERNS,
            degrade_rules=DEGRADE_RULES,
        )
        # ★ 塞示例：3 个 few-shot（直接来自你的 3 张参考图），多轮对话让 LLM 学"图文挂位"手感
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": FEW_SHOT_USER_1},
            {"role": "assistant", "content": FEW_SHOT_ASSISTANT_1},
            {"role": "user", "content": FEW_SHOT_USER_2},
            {"role": "assistant", "content": FEW_SHOT_ASSISTANT_2},
            {"role": "user", "content": FEW_SHOT_USER_3},
            {"role": "assistant", "content": FEW_SHOT_ASSISTANT_3},
            {"role": "user", "content": json.dumps(
                {"candidates": candidates}, ensure_ascii=False)},
        ]
        resp = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.4,
            max_tokens=1500,
            timeout=25,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        parsed = json.loads(content)
        placements = parsed.get("placements", []) if isinstance(parsed, dict) else []

        weights: Dict[str, float] = {}
        placement_map: Dict[str, Dict[str, str]] = {}
        for plc in placements:
            if not isinstance(plc, dict):
                continue
            ref = plc.get("chart_ref")
            sid = plc.get("slot_id")
            shape = plc.get("shape")
            if not ref:
                continue
            placement_map[str(ref)] = {"slot_id": sid, "shape": shape}
            # 有形状的图业务权重默认拉高（核心大图），兜底融合时仍可用
            try:
                weights[str(ref)] = float(plc.get("attention_weight", 0.0))
            except (TypeError, ValueError):
                weights[str(ref)] = 0.0
        return weights, placement_map
