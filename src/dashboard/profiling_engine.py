"""ProfilingEngine —— 候选清单降噪。

把后端从 /dashboard/echarts 链路提取出的「图表配置列表」(configs) 收敛成
仅含元信息的轻量候选清单，供下游 LLM 排版决策使用。

设计目标（防 token 爆炸）：
- 零 LLM token：纯规则遍历，O(n)
- 信息压缩：丢弃完整 ECharts option（数万 token），仅保留 type/行数/维度/
  指标/取值区间/先验分等几百 token 的「指纹」
- 截断：按 suggestedBusinessValue 降序取 Top-N（默认 12），多余图表不参与排版

参考：可视化模板库/同期群分析/智能排版引擎架构改造计划.md
     （profiling 降噪 + 后端先验打分 + Top-N 截断）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_TOP_N = 12


@dataclass
class ChartProfile:
    """单张图的轻量指纹（供 LLM 阅读，不携带完整 option）。"""

    slot: str                       # 稳定槽位 id，用于回查原始 config
    title: str
    chart_type: str
    analysis_type: str = ""
    # 元信息（从 option 中尽量抽取，失败则留空）
    dims: int = 0                   # 维度列数（类别轴基数）
    series_count: int = 0           # 系列数
    row_count: int = 0              # 数据点行数
    metric_hint: str = ""           # 指标列名/语义提示
    value_hint: str = ""            # 取值区间提示（如 "0~12000" / "占比%"）
    is_aggregated: bool = True      # 是否已聚合（True=汇总图，False=原始明细）
    # 先验业务价值分（后端规则算，0~1）
    suggested_business_value: float = 0.0

    def to_candidate(self) -> Dict[str, Any]:
        """转成喂给 LLM 的候选条目（不含先验分本身，仅元信息）。"""
        return {
            "slot": self.slot,
            "title": self.title,
            "chart_type": self.chart_type,
            "analysis_type": self.analysis_type,
            "dims": self.dims,
            "series_count": self.series_count,
            "row_count": self.row_count,
            "metric_hint": self.metric_hint,
            "value_hint": self.value_hint,
            "is_aggregated": self.is_aggregated,
        }


# ===== 业务价值先验规则（借鉴 importance_engine 优先级思路，独立实现避免重依赖） =====

# 指标语义关键词 → 权重档（营收/转化类 > 流量/明细类）
_HIGH_VALUE_METRICS = ("营收", "销售额", "gmv", "利润", "毛利", "净利", "arpu",
                        "转化率", "留存", "复购", "客单价", "roi", "回本")
_MID_VALUE_METRICS = ("订单", "销量", "用户", "活跃", "新增", "访问", "时长",
                      "占比", "分布", "频率")
# 分析类型优先级（参考 AttentionPriorityScorer.TYPE_PRIORITY）
_ANALYSIS_PRIORITY = {
    "growth": 0.95, "rfm": 0.9, "cohort": 0.88, "conversion": 0.85,
    "retention": 0.85, "contribution": 0.8, "trend": 0.78, "correlation": 0.75,
    "anomaly": 0.82, "clv": 0.85, "funnel": 0.8, "proportion": 0.6,
    "distribution": 0.55, "comparison": 0.65, "rank": 0.6,
}
# 图表类型 → 基础价值（汇总型 > 原始明细型）
# ★ 用户反馈：表格类（明细/排行/RFM 分群矩阵）业务价值不低，应保留可见。
#   表格图表从前是 0.5（全类型最低），导致被 layout top_n=12 截断后丢失；
#   现调整为 0.65，与 bar/hbar/ranking 同级（用户体感：明细和排行表同样重要）。
# ★ bar/hbar 0.6 → 0.62（小幅提升，让 bar 不至于被边缘化）
_CHART_BASE_VALUE = {
    "funnel": 0.85, "pie": 0.7, "ring": 0.7, "radar": 0.72,
    "dual_axis": 0.8, "cohort_heatmap": 0.85, "heatmap": 0.7,
    "line": 0.65, "area": 0.65,
    "bar": 0.62, "hbar": 0.62, "ranking": 0.65,
    "table": 0.65,
    "bubble": 0.55, "graph": 0.6, "map": 0.6, "wordcloud": 0.4,
}


def _metric_keyword_score(text: str) -> float:
    """从 title/analysis_type/metric_hint 中匹配指标语义，给 0~0.3 加分。"""
    low = (text or "").lower()
    for kw in _HIGH_VALUE_METRICS:
        if kw in low:
            return 0.30
    for kw in _MID_VALUE_METRICS:
        if kw in low:
            return 0.18
    return 0.05


def _extract_option_meta(option: Any) -> Dict[str, Any]:
    """从 ECharts option 中尽量抽取元信息，失败降级为空。"""
    meta: Dict[str, Any] = {
        "dims": 0, "series_count": 0, "row_count": 0,
        "metric_hint": "", "value_hint": "", "is_aggregated": True,
    }
    if not isinstance(option, dict):
        return meta
    try:
        series = option.get("series") or []
        if isinstance(series, list):
            meta["series_count"] = len(series)
            # 取第一个 series 估算行数
            first = series[0] if series else {}
            data = first.get("data") if isinstance(first, dict) else None
            if isinstance(data, list):
                meta["row_count"] = len(data)
            # 指标提示：seriesName 或第一条数据的 name
            if isinstance(first, dict) and first.get("name"):
                meta["metric_hint"] = str(first["name"])
        # xAxis 维度数
        xaxis = option.get("xAxis")
        if isinstance(xaxis, dict):
            meta["dims"] = 1
        elif isinstance(xaxis, list):
            meta["dims"] = len(xaxis)
        # 取值区间提示（来自 yAxis / 第一条 series）
        yaxis = option.get("yAxis")
        if isinstance(yaxis, dict) and "max" in yaxis:
            meta["value_hint"] = f"max={yaxis['max']}"
        # 是否为原始明细：数据点过多（>500）且无聚合提示 → 视为明细
        if meta["row_count"] and meta["row_count"] > 500:
            meta["is_aggregated"] = False
    except Exception as e:  # noqa: BLE001
        logger.debug(f"option 元信息抽取失败（降级）: {e}")
    return meta


class ProfilingEngine:
    """将图表配置列表收敛为轻量候选清单。"""

    def __init__(self, top_n: int = DEFAULT_TOP_N):
        self.top_n = top_n

    def profile(self, configs: List[Dict[str, Any]]) -> List[ChartProfile]:
        """输入：_extract_chart_configs_from_packages 返回的配置列表。

        输出：按 suggested_business_value 降序、截断至 top_n 的 ChartProfile 列表
        （用于 LLM 精排省 token）。
        """
        profiles = self._build_profiles(configs)
        # 降序 + 截断
        profiles.sort(key=lambda p: p.suggested_business_value, reverse=True)
        return profiles[: self.top_n]

    def profile_full(self, configs: List[Dict[str, Any]]) -> List[ChartProfile]:
        """全量版本：不截断，返回所有图表的 ChartProfile（按 sbv 降序）。

        用于最终 items / charts 的全量渲染——智能排版应展示与经典网格
        相同数量的图表，LLM 只对 Top-N 精排，其余用先验分兜底。
        """
        profiles = self._build_profiles(configs)
        profiles.sort(key=lambda p: p.suggested_business_value, reverse=True)
        return profiles

    def _build_profiles(self, configs: List[Dict[str, Any]]) -> List[ChartProfile]:
        profiles: List[ChartProfile] = []
        for idx, cfg in enumerate(configs):
            if not isinstance(cfg, dict):
                continue
            chart_type = (cfg.get("chart_type") or "bar")
            title = cfg.get("title") or f"{chart_type} 图表"
            analysis_type = cfg.get("analysis_type") or ""
            slot = cfg.get("slot") or f"chart_{idx}"

            meta = _extract_option_meta(cfg.get("option"))

            # —— 先验业务价值分 ——
            # 1) 图表类型基础分
            base = _CHART_BASE_VALUE.get(chart_type, 0.55)
            # 2) 分析类型优先级
            atype = analysis_type.lower()
            atype_score = 0.0
            for k, v in _ANALYSIS_PRIORITY.items():
                if k in atype:
                    atype_score = v
                    break
            # 3) 指标语义加分
            metric_score = _metric_keyword_score(
                f"{title} {analysis_type} {meta.get('metric_hint', '')}"
            )
            # 4) 聚合型加分、明细型减分
            agg_bonus = 0.06 if meta.get("is_aggregated") else -0.08
            # 5) 维度精炼加分（维度少而精 > 超多行明细）
            dim_bonus = 0.04 if (0 < meta.get("dims", 0) <= 3) else 0.0

            sbv = base * 0.5 + atype_score * 0.3 + metric_score + agg_bonus + dim_bonus
            sbv = max(0.0, min(1.0, sbv))

            profiles.append(ChartProfile(
                slot=str(slot),
                title=title,
                chart_type=str(chart_type),
                analysis_type=analysis_type,
                dims=int(meta.get("dims", 0)),
                series_count=int(meta.get("series_count", 0)),
                row_count=int(meta.get("row_count", 0)),
                metric_hint=str(meta.get("metric_hint", "")),
                value_hint=str(meta.get("value_hint", "")),
                is_aggregated=bool(meta.get("is_aggregated", True)),
                suggested_business_value=round(sbv, 4),
            ))
        return profiles

    def to_candidate_list(self, configs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """直接返回可喂给 LLM 的候选清单（JSON 友好），默认 Top-N 截断。"""
        return [p.to_candidate() for p in self.profile(configs)]

    def to_candidate_list_full(self, configs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """全量候选清单（不截断），用于全量 items 渲染。"""
        return [p.to_candidate() for p in self.profile_full(configs)]

    def build_lookup(self, configs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """slot → 原始 config 映射，供下游回查完整 option。"""
        lookup: Dict[str, Dict[str, Any]] = {}
        for idx, cfg in enumerate(configs):
            if not isinstance(cfg, dict):
                continue
            slot = cfg.get("slot") or f"chart_{idx}"
            lookup[str(slot)] = cfg
        return lookup
