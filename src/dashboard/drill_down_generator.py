"""
Drill Down Generator —— 下钻路径生成引擎

核心职责：
- 从 Widget 的维度信息推断可下钻的层级路径
- 根据层级映射表（地理/产品/时间）生成 DrillDownRule
- 只使用已存在的维度，不创造不存在层级

设计原则：
- 不使用 if-else 硬编码
- 使用 InteractionRuleEngine 评估规则
- 维度层级预定义（GEO/PRODUCT/TIME hierarchy）
- 只生成当前层级 → 下一层级的单步下钻

层级体系：
- 地理：country → province → city → district
- 产品：category → product → sku
- 时间：year → quarter → month → week → day

生产方：DashboardInteractionEngine
消费方：Renderer（绑定 Drill Down UI）
"""

from __future__ import annotations
from typing import List, Dict, Any
import uuid

from src.dashboard.layout_schema import DashboardSchema, WidgetSlot
from src.dashboard.interaction_schema import (
    DrillDownRule, DrillDownLevel, InteractionPriority,
)
from src.dashboard.interaction_rules import (
    InteractionRuleEngine,
    FILTER_FIELD_LABELS,
    _extract_filter_fields,
)


# ============================================================
# Dimension Hierarchies —— 维度层级体系
# ============================================================

GEO_HIERARCHY: List[str] = ["country", "province", "city", "district"]
PRODUCT_HIERARCHY: List[str] = ["category", "product", "sku"]
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

# 层级 → 中文标签
DIMENSION_LABELS: Dict[str, str] = {
    "country": "国家",
    "province": "省份",
    "city": "城市",
    "district": "区县",
    "category": "类别",
    "product": "产品",
    "sku": "SKU",
    "year": "年份",
    "quarter": "季度",
    "month": "月份",
    "week": "周",
    "day": "日期",
}


# ============================================================
# Drill Down Generator
# ============================================================

class DrillDownGenerator:
    """下钻路径生成引擎

    使用方式：
        generator = DrillDownGenerator(rule_engine)
        rules = generator.generate(schema)
    """

    def __init__(self, rule_engine: Optional[InteractionRuleEngine] = None):
        self._rule_engine = rule_engine or InteractionRuleEngine()

    def generate(self, schema: DashboardSchema) -> List[DrillDownRule]:
        """从 DashboardSchema 生成下钻规则

        流程：
        1. 评估 Drill Down 规则（Rule Engine）
        2. 对每个 Widget 推断主维度
        3. 检测维度层级
        4. 生成 current_level → next_level 的 DrillDownRule

        Args:
            schema: DashboardSchema

        Returns:
            DrillDownRule 列表
        """
        rules: List[DrillDownRule] = []

        for w in schema.widgets:
            # 推断维度
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
                    current_label = DIMENSION_LABELS.get(current_level, current_level)
                    next_label = DIMENSION_LABELS.get(next_level, next_level)
                    rules.append(DrillDownRule(
                        id=f"dd_{w.widget_id}_{dimension}",
                        widget_id=w.widget_id,
                        dimension=dimension,
                        current_level=current_level,
                        next_level=next_level,
                        label=f"{current_label} → {next_label}",
                        priority=InteractionPriority.DRILL_DOWN,
                    ))

        return rules

    # ============================================================
    # Dimension Inference
    # ============================================================

    def _infer_dimension(self, widget: WidgetSlot) -> str:
        """推断 Widget 的主维度"""
        fields = _extract_filter_fields(widget)
        metadata = widget.metadata or {}
        analysis_type = metadata.get("analysis_type", "")
        business_topic = metadata.get("business_topic", "")
        text = f"{analysis_type} {business_topic}".lower()

        # 从 filter fields 中检查
        for hierarchy in [GEO_HIERARCHY, PRODUCT_HIERARCHY, TIME_HIERARCHY]:
            for level in hierarchy:
                if level in fields:
                    return level
                for kw in DIMENSION_KEYWORDS.get(level, []):
                    if kw in text:
                        return level

        return ""

    def _detect_dimension_level(self, widget: WidgetSlot, dimension: str) -> str:
        """从 Widget 的 filter fields 和 metadata 中检测维度层级"""
        fields = _extract_filter_fields(widget)
        for f in fields:
            if f in DIMENSION_KEYWORDS:
                return f

        # 从 metadata 推断
        metadata = widget.metadata or {}
        for level in GEO_HIERARCHY + PRODUCT_HIERARCHY + TIME_HIERARCHY:
            for kw in DIMENSION_KEYWORDS.get(level, []):
                if kw in str(metadata).lower():
                    return level

        # fallback: 使用 dimension 本身作为当前层级
        if dimension in GEO_HIERARCHY + PRODUCT_HIERARCHY + TIME_HIERARCHY:
            return dimension

        return ""

    @staticmethod
    def _get_hierarchy_for_dimension(dimension: str) -> List[str]:
        """推断 dimension 属于哪个层级体系"""
        if dimension in GEO_HIERARCHY:
            return GEO_HIERARCHY
        if dimension in PRODUCT_HIERARCHY:
            return PRODUCT_HIERARCHY
        if dimension in TIME_HIERARCHY:
            return TIME_HIERARCHY

        # 关键词推断
        geo_kw = ["省", "市", "区", "province", "city", "region"]
        product_kw = ["产品", "商品", "类", "product", "sku"]
        time_kw = ["年", "月", "日", "time", "date"]

        dim_lower = dimension.lower()
        for kw in geo_kw:
            if kw in dim_lower:
                return GEO_HIERARCHY
        for kw in product_kw:
            if kw in dim_lower:
                return PRODUCT_HIERARCHY
        for kw in time_kw:
            if kw in dim_lower:
                return TIME_HIERARCHY

        return []
