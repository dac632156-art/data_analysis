"""
Interaction Engine —— Widget + DashboardSchema → InteractionSchema

根据 Widget 之间的数据维度、业务关系、支持字段，
自动生成 Dashboard 的完整交互规则。

设计原则：
- 不读取 DataFrame
- 不重新分析数据
- 前端框架无关（输出纯数据描述）
- 循环依赖检测
- 冲突合并
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional, Set, Tuple
import uuid
import time

from src.dashboard.interaction_schema import (
    InteractionSchema,
    FilterRule, FilterType,
    CrossFilterRule,
    DrillDownRule,
    HighlightRule, HighlightType,
    InteractionPriority,
)
from src.dashboard.layout_schema import (
    DashboardSchema, WidgetSlot, BusinessGroup,
)


# ============================================================
# 维度层级映射（用于 Drill Down）
# ============================================================

# 地理层级
GEO_HIERARCHY: List[str] = ["country", "province", "city", "district"]
# 产品层级
PRODUCT_HIERARCHY: List[str] = ["category", "product", "sku"]
# 时间层级
TIME_HIERARCHY: List[str] = ["year", "quarter", "month", "week", "day"]

# 字段名 → 层级识别关键词
DIMENSION_KEYWORDS: Dict[str, List[str]] = {
    "country": ["国家", "country"],
    "province": ["省份", "省", "province", "州"],
    "city": ["城市", "市", "city", "town"],
    "district": ["区县", "区", "district", "county"],
    "category": ["类别", "分类", "category", "类目"],
    "product": ["产品", "商品", "product", "item"],
    "sku": ["sku", "单品", "条码"],
    "year": ["年", "year"],
    "quarter": ["季度", "季", "quarter", "q"],
    "month": ["月", "month"],
    "week": ["周", "星期", "week"],
    "day": ["日", "天", "day"],
}


# ============================================================
# Filter 字段名 → 中文标签映射
# ============================================================

FILTER_LABELS: Dict[str, str] = {
    "time": "时间范围",
    "region": "地区",
    "product": "产品",
    "category": "分类",
    "channel": "渠道",
    "brand": "品牌",
    "metric": "指标",
}


# ============================================================
# Interaction Engine
# ============================================================

class InteractionEngine:
    """Dashboard 交互引擎

    使用方式：
        engine = InteractionEngine()
        ischema = engine.build(widget_dicts, dashboard_schema)
    """

    def __init__(self):
        self._widgets: List[Dict[str, Any]] = []
        self._schema: Optional[DashboardSchema] = None
        self._widget_index: Dict[str, Dict[str, Any]] = {}

    def build(
        self,
        widgets: List[Dict[str, Any]],
        schema: DashboardSchema,
    ) -> InteractionSchema:
        """构建完整的 InteractionSchema

        Args:
            widgets: Widget dict 列表（含 id, title, supported_filters, chart_type,
                     business_topic, metadata 等）
            schema: DashboardSchema

        Returns:
            InteractionSchema
        """
        self._widgets = widgets or []
        self._schema = schema
        self._widget_index = {w.get("id", ""): w for w in self._widgets if w.get("id")}

        ischema = InteractionSchema(
            id=f"interact_{uuid.uuid4().hex[:8]}",
            dashboard_id=schema.id,
            version="1.0",
        )

        # Phase 1: Global Filter 生成
        ischema.global_filters = self._generate_global_filters()

        # Phase 2: Cross Filter 生成
        raw_cross = self._generate_cross_filters()

        # Phase 3: 冲突检测 + 合并
        ischema.cross_filters = self._resolve_cross_conflicts(raw_cross)

        # Phase 4: Drill Down 生成
        ischema.drill_downs = self._generate_drill_downs()

        # Phase 5: Highlight 生成
        ischema.highlights = self._generate_highlights()

        # Phase 6: 元数据
        ischema.metadata = {
            "total_widgets": len(self._widgets),
            "global_filter_count": len(ischema.global_filters),
            "cross_filter_count": len(ischema.cross_filters),
            "drill_down_count": len(ischema.drill_downs),
            "highlight_count": len(ischema.highlights),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

        return ischema

    # ============================================================
    # Phase 1: Global Filter Generator
    # ============================================================

    def _generate_global_filters(self) -> List[FilterRule]:
        """全局筛选器生成

        规则：只有多个 Widget 共同支持的字段，才成为 Global Filter。
        """
        # 统计每个 filter field 被哪些 widget 支持
        field_widgets: Dict[str, Set[str]] = {}

        for w in self._widgets:
            wid = w.get("id", "")
            filters = w.get("supported_filters", [])
            for f in filters:
                field = self._extract_field(f)
                if not field:
                    continue
                if field not in field_widgets:
                    field_widgets[field] = set()
                field_widgets[field].add(wid)

        # 筛选：≥ 2 个 Widget 共同支持的字段
        rules: List[FilterRule] = []
        for field, widget_ids in field_widgets.items():
            if len(widget_ids) >= 2:
                label = FILTER_LABELS.get(field, field)
                widget_type = self._infer_filter_widget_type(field)
                rules.append(FilterRule(
                    id=f"gf_{field}",
                    name=label,
                    field=field,
                    filter_type=FilterType.GLOBAL,
                    widget_type=widget_type,
                    target_widgets=sorted(widget_ids),
                    priority=InteractionPriority.GLOBAL_FILTER,
                ))

        # 按覆盖 widget 数量降序
        rules.sort(key=lambda r: len(r.target_widgets), reverse=True)
        return rules

    # ============================================================
    # Phase 2: Cross Filter Generator
    # ============================================================

    def _generate_cross_filters(self) -> List[CrossFilterRule]:
        """Widget 间联动生成

        策略：按 filter field 分组 Widget。
        同一 field 下，Widget A 有分类维度 + Widget B 也支持同样的分类
        → A 点击时联动 B。
        """
        # 收集每个 Widget 的 filter fields
        widget_fields: Dict[str, Set[str]] = {}
        for w in self._widgets:
            wid = w.get("id", "")
            fields: Set[str] = set()
            for f in w.get("supported_filters", []):
                field = self._extract_field(f)
                if field:
                    fields.add(field)
            if fields:
                widget_fields[wid] = fields

        # 构建联动对
        rules: List[CrossFilterRule] = []
        widget_ids = list(widget_fields.keys())

        for i, source_id in enumerate(widget_ids):
            source_fields = widget_fields[source_id]
            for target_id in widget_ids[i + 1:]:
                target_fields = widget_fields[target_id]
                # 找出共有字段（排除 time，time 不适合做 cross filter）
                common = source_fields & target_fields - {"time"}
                for field in common:
                    source_w = self._widget_index.get(source_id, {})
                    if self._is_clickable_chart(source_w):
                        label = FILTER_LABELS.get(field, field)
                        rules.append(CrossFilterRule(
                            id=f"cf_{source_id}_{field}",
                            source_widget=source_id,
                            event="click" if source_w.get("chart_type") in ("bar", "pie", "map") else "hover",
                            field=field,
                            field_label=label,
                            targets=[target_id],
                            priority=InteractionPriority.CROSS_FILTER,
                            bidirectional=field != "time",
                        ))

        return rules

    # ============================================================
    # Phase 3: 冲突检测 + 合并
    # ============================================================

    def _resolve_cross_conflicts(
        self,
        raw: List[CrossFilterRule],
    ) -> List[CrossFilterRule]:
        """检测循环依赖 + 合并重复联动

        1. 同 source+field → 合并 targets
        2. A→B 且 B→A 且 bidirectional → 保留一条（双向）
        3. 检测 A→B→A 循环
        """
        # Step 1: 合并同 source+field
        merged: Dict[Tuple[str, str], CrossFilterRule] = {}
        for r in raw:
            key = (r.source_widget, r.field)
            if key in merged:
                existing = merged[key]
                for t in r.targets:
                    if t not in existing.targets:
                        existing.targets.append(t)
            else:
                merged[key] = CrossFilterRule(
                    id=r.id,
                    source_widget=r.source_widget,
                    event=r.event,
                    field=r.field,
                    field_label=r.field_label,
                    targets=list(r.targets),
                    priority=r.priority,
                    bidirectional=r.bidirectional,
                    metadata=r.metadata,
                )

        # Step 2: 合并双向 A→B 和 B→A
        result: List[CrossFilterRule] = []
        seen_pairs: Set[Tuple[str, str]] = set()
        rule_list = list(merged.values())

        for r in rule_list:
            for t in r.targets:
                pair = (min(r.source_widget, t), max(r.source_widget, t))
                if pair not in seen_pairs:
                    seen_pairs.add(pair)

        # Step 3: 循环检测
        graph: Dict[str, List[str]] = {}
        for r in rule_list:
            if r.source_widget not in graph:
                graph[r.source_widget] = []
            graph[r.source_widget].extend([t for t in r.targets if t != r.source_widget])

        for r in rule_list:
            # 简单循环检测：A→B 同时 B→A
            cyclic = False
            for t in r.targets:
                if t in graph:
                    if r.source_widget in graph[t]:
                        cyclic = True
                        break

            if cyclic:
                # 保持双向标记，但不重复添加
                r.bidirectional = True
                result.append(r)
            else:
                result.append(r)

        return result

    # ============================================================
    # Phase 4: Drill Down Generator
    # ============================================================

    def _generate_drill_downs(self) -> List[DrillDownRule]:
        """下钻生成

        从 Widget 的 metadata 中查找维度信息，根据层级映射表生成下钻路径。
        只使用已存在的数据，不创造不存在层级。
        """
        rules: List[DrillDownRule] = []

        for w in self._widgets:
            wid = w.get("id", "")
            metadata = w.get("metadata", {}) or {}
            filters = w.get("supported_filters", [])

            # 从 metadata 或 supported_filters 推断维度
            dimension = self._infer_dimension(w)
            if not dimension:
                continue

            current_level = self._detect_dimension_level(w, dimension)
            if not current_level:
                continue

            # 查找下一层级
            hierarchy = self._get_hierarchy_for_dimension(dimension)
            if current_level in hierarchy:
                idx = hierarchy.index(current_level)
                if idx + 1 < len(hierarchy):
                    next_level = hierarchy[idx + 1]
                    label = f"{FILTER_LABELS.get(current_level, current_level)} → {FILTER_LABELS.get(next_level, next_level)}"
                    rules.append(DrillDownRule(
                        id=f"dd_{wid}_{dimension}",
                        widget_id=wid,
                        dimension=dimension,
                        current_level=current_level,
                        next_level=next_level,
                        label=label,
                        priority=InteractionPriority.DRILL_DOWN,
                    ))

        return rules

    def _detect_dimension_level(
        self,
        widget: Dict[str, Any],
        dimension: str,
    ) -> str:
        """从 Widget 的 filter/supported_filters 中检测维度层级"""
        filters = widget.get("supported_filters", [])
        for f in filters:
            field = self._extract_field(f)
            if field and field in DIMENSION_KEYWORDS:
                return field
        # 从 metadata 查找
        metadata = widget.get("metadata", {}) or {}
        for level in GEO_HIERARCHY + PRODUCT_HIERARCHY + TIME_HIERARCHY:
            for kw in DIMENSION_KEYWORDS.get(level, []):
                if kw in str(metadata).lower():
                    return level
        return ""

    @staticmethod
    def _get_hierarchy_for_dimension(dimension: str) -> List[str]:
        """推断 dimension 属于哪个层级体系"""
        if dimension in GEO_HIERARCHY or any(
            kw in dimension.lower() for kw in ["省", "市", "区", "province", "city", "region"]
        ):
            return GEO_HIERARCHY
        if dimension in PRODUCT_HIERARCHY or any(
            kw in dimension.lower() for kw in ["产品", "商品", "类", "product", "sku"]
        ):
            return PRODUCT_HIERARCHY
        if dimension in TIME_HIERARCHY or any(
            kw in dimension.lower() for kw in ["年", "月", "日", "time", "date"]
        ):
            return TIME_HIERARCHY
        return []

    # ============================================================
    # Phase 5: Highlight Generator
    # ============================================================

    def _generate_highlights(self) -> List[HighlightRule]:
        """高亮规则生成

        根据 Widget 的业务类型自动推荐高亮：
        - ranking → TOP 3
        - anomaly → 异常标记
        - growth → 高增长
        - concentration → 阈值
        """
        rules: List[HighlightRule] = []

        for w in self._widgets:
            wid = w.get("id", "")
            chart_type = w.get("chart_type", "") or ""
            analysis_type = w.get("analysis_type", "") or ""
            score = w.get("importance_score", 50)

            # ranking / bar → TOP 3
            if chart_type == "bar" or "ranking" in analysis_type or "排名" in w.get("business_topic", ""):
                rules.append(HighlightRule(
                    id=f"hl_{wid}_top3",
                    widget_id=wid,
                    rule_type=HighlightType.TOP_N,
                    params={"n": 3, "metric": w.get("metadata", {}).get("metric", "value")},
                    label="高亮 TOP 3",
                    priority=InteractionPriority.HIGHLIGHT + (10 if score >= 70 else 0),
                ))

            # anomaly / scatter → 异常标记
            if chart_type == "scatter" or "anomaly" in analysis_type:
                rules.append(HighlightRule(
                    id=f"hl_{wid}_anomaly",
                    widget_id=wid,
                    rule_type=HighlightType.ANOMALY,
                    params={"threshold": 3.0, "method": "zscore"},
                    label="标记异常点",
                    priority=InteractionPriority.HIGHLIGHT + (15 if score >= 80 else 0),
                ))

            # growth / line → 高增长 + 趋势拐点
            if chart_type == "line" or "growth" in analysis_type:
                rules.append(HighlightRule(
                    id=f"hl_{wid}_growth",
                    widget_id=wid,
                    rule_type=HighlightType.HIGH_GROWTH,
                    params={"threshold_pct": 10},
                    label="标记高增长点",
                    priority=InteractionPriority.HIGHLIGHT,
                ))
                rules.append(HighlightRule(
                    id=f"hl_{wid}_trend",
                    widget_id=wid,
                    rule_type=HighlightType.TREND_CHANGE,
                    params={},
                    label="标记趋势拐点",
                    priority=InteractionPriority.HIGHLIGHT - 5,
                ))

            # kpi → 阈值高亮
            if w.get("widget_type") == "kpi":
                rules.append(HighlightRule(
                    id=f"hl_{wid}_threshold",
                    widget_id=wid,
                    rule_type=HighlightType.THRESHOLD,
                    params={"good_above": None, "warn_below": None},
                    label="阈值监控",
                    priority=InteractionPriority.HIGHLIGHT,
                ))

        return rules

    # ============================================================
    # 工具方法
    # ============================================================

    @staticmethod
    def _extract_field(filter_item) -> str:
        """从 supported_filters 条目中提取 field"""
        if isinstance(filter_item, str):
            return filter_item
        if isinstance(filter_item, dict):
            return filter_item.get("field", "")
        return ""

    @staticmethod
    def _infer_filter_widget_type(field: str) -> str:
        """推断 Filter 控件类型"""
        if field == "time":
            return "date_range"
        return "dropdown"

    @staticmethod
    def _infer_dimension(widget: Dict[str, Any]) -> str:
        """推断 Widget 的主维度"""
        metadata = widget.get("metadata", {}) or {}
        analysis_type = metadata.get("analysis_type", "")
        business_topic = widget.get("business_topic", "")
        text = f"{analysis_type} {business_topic}".lower()

        for hierarchy in [GEO_HIERARCHY, PRODUCT_HIERARCHY, TIME_HIERARCHY]:
            for level in hierarchy:
                for kw in DIMENSION_KEYWORDS.get(level, []):
                    if kw in text:
                        return level
        return ""

    @staticmethod
    def _is_clickable_chart(widget: Dict[str, Any]) -> bool:
        """判断 Widget 是否支持点击交互（作为 cross filter 的 source）"""
        ct = widget.get("chart_type", "") or ""
        # 只有特定图表类型支持点选联动
        return ct in ("bar", "pie", "map", "scatter")


# ============================================================
# 快捷函数
# ============================================================

def generate_interactions(
    widgets: List[Dict[str, Any]],
    schema: DashboardSchema,
) -> InteractionSchema:
    """快捷函数：Widget + DashboardSchema → InteractionSchema"""
    engine = InteractionEngine()
    return engine.build(widgets, schema)
