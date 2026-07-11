"""
Interaction Rule Engine —— 交互规则引擎（Strategy Pattern + Rule Engine）

核心职责：
- 定义交互生成规则（不是 if-else 硬编码）
- 每条规则是声明式配置：(条件, 规则类型, 生成策略)
- 新增交互类型只需添加规则，无需修改引擎代码

设计原则：
- 不使用 if-else 硬编码
- Rule Engine：规则按优先级评估，首次命中执行
- Strategy Pattern：每种交互类型有独立的生成策略
- 规则注册、发现、执行分离

生产方：DashboardInteractionEngine
消费方：Global/Cross/Drill/Highlight Generator
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field

from src.dashboard.layout_schema import DashboardSchema, WidgetSlot


# ============================================================
# Interaction Rule —— 交互规则定义
# ============================================================

@dataclass
class InteractionRule:
    """交互生成规则——声明式配置

    每条规则定义一个交互生成的触发条件和行为。

    例如：
    - Rule: 多个 Widget 共享 Region → 自动生成 Cross Filter
    - Rule: 多个 Widget 共享 Time → 自动生成 Global Time Filter
    - Rule: Widget 是 ranking 类型的 bar → 生成 TOP 3 Highlight
    """
    rule_id: str = ""                               # 规则 ID
    rule_type: str = ""                              # 规则类型：global_filter / cross_filter / drill_down / highlight / linkage
    condition: str = ""                              # 条件描述（便于理解，不参与逻辑）
    condition_fn: Optional[Callable] = None          # 条件函数（Callable[[DashboardSchema], bool]）
    action: str = ""                                 # 动作描述
    priority: int = 0                                # 规则优先级（越高越先评估）
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# Predefined Rules —— 预定义交互规则
# ============================================================

# --- Global Filter 规则 ---
GLOBAL_FILTER_RULES: List[InteractionRule] = [
    InteractionRule(
        rule_id="gf_time_global",
        rule_type="global_filter",
        condition=">= 2 Widget 共享 time 字段",
        condition_fn=lambda schema: _count_widgets_with_field(schema, "time") >= 2,
        action="生成全局时间筛选器",
        priority=100,
    ),
    InteractionRule(
        rule_id="gf_region_global",
        rule_type="global_filter",
        condition=">= 2 Widget 共享 region 字段",
        condition_fn=lambda schema: _count_widgets_with_field(schema, "region") >= 2,
        action="生成全局地区筛选器",
        priority=90,
    ),
    InteractionRule(
        rule_id="gf_product_global",
        rule_type="global_filter",
        condition=">= 3 Widget 共享 product 字段",
        condition_fn=lambda schema: _count_widgets_with_field(schema, "product") >= 3,
        action="生成全局产品筛选器（>=3 Widget 才全局）",
        priority=80,
    ),
    InteractionRule(
        rule_id="gf_channel_global",
        rule_type="global_filter",
        condition=">= 2 Widget 共享 channel 字段",
        condition_fn=lambda schema: _count_widgets_with_field(schema, "channel") >= 2,
        action="生成全局渠道筛选器",
        priority=70,
    ),
    InteractionRule(
        rule_id="gf_category_global",
        rule_type="global_filter",
        condition=">= 2 Widget 共享 category 字段",
        condition_fn=lambda schema: _count_widgets_with_field(schema, "category") >= 2,
        action="生成全局分类筛选器",
        priority=60,
    ),
]

# --- Cross Filter 规则 ---
CROSS_FILTER_RULES: List[InteractionRule] = [
    InteractionRule(
        rule_id="cf_clickable_bar_pie",
        rule_type="cross_filter",
        condition="bar/pie Widget 与同 field Widget 共存",
        condition_fn=lambda schema: _has_clickable_chart_with_shared_field(schema),
        action="生成 click 交叉筛选（bar/pie → 同 field Widget）",
        priority=50,
    ),
    InteractionRule(
        rule_id="cf_clickable_map",
        rule_type="cross_filter",
        condition="map Widget 与同 region Widget 共存",
        condition_fn=lambda schema: _has_map_with_shared_region(schema),
        action="生成 click 交叉筛选（map → 同 region Widget）",
        priority=40,
    ),
]

# --- Drill Down 规则 ---
DRILL_DOWN_RULES: List[InteractionRule] = [
    InteractionRule(
        rule_id="dd_geo_hierarchy",
        rule_type="drill_down",
        condition="Widget 含 province/city 地理维度",
        condition_fn=lambda schema: _has_geo_dimension(schema),
        action="生成地理层级下钻（province → city）",
        priority=30,
    ),
    InteractionRule(
        rule_id="dd_product_hierarchy",
        rule_type="drill_down",
        condition="Widget 含 category/product 产品维度",
        condition_fn=lambda schema: _has_product_dimension(schema),
        action="生成产品层级下钻（category → product）",
        priority=20,
    ),
    InteractionRule(
        rule_id="dd_time_hierarchy",
        rule_type="drill_down",
        condition="Widget 含 year/month 时间维度",
        condition_fn=lambda schema: _has_time_dimension(schema),
        action="生成时间层级下钻（year → quarter → month）",
        priority=10,
    ),
]

# --- Highlight 规则 ---
HIGHLIGHT_RULES: List[InteractionRule] = [
    InteractionRule(
        rule_id="hl_ranking_top3",
        rule_type="highlight",
        condition="Widget 是 ranking/bar 类型",
        condition_fn=lambda schema: _has_ranking_widget(schema),
        action="生成 TOP 3 高亮",
        priority=50,
    ),
    InteractionRule(
        rule_id="hl_anomaly_mark",
        rule_type="highlight",
        condition="Widget 是 scatter/anomaly 类型",
        condition_fn=lambda schema: _has_anomaly_widget(schema),
        action="生成异常标记高亮",
        priority=40,
    ),
    InteractionRule(
        rule_id="hl_growth_mark",
        rule_type="highlight",
        condition="Widget 是 line/trend 类型",
        condition_fn=lambda schema: _has_trend_widget(schema),
        action="生成高增长点高亮",
        priority=30,
    ),
    InteractionRule(
        rule_id="hl_kpi_threshold",
        rule_type="highlight",
        condition="Widget 是 KPI 类型",
        condition_fn=lambda schema: _has_kpi_widget(schema),
        action="生成阈值监控高亮",
        priority=20,
    ),
]

# --- Linkage 规则 ---
LINKAGE_RULES: List[InteractionRule] = [
    InteractionRule(
        rule_id="lg_topic_linkage",
        rule_type="linkage",
        condition=">= 2 Widget 同 business_topic",
        condition_fn=lambda schema: _has_shared_topic(schema),
        action="生成同一业务主题的 Widget 联动",
        priority=60,
    ),
]


ALL_INTERACTION_RULES: List[InteractionRule] = (
    GLOBAL_FILTER_RULES + CROSS_FILTER_RULES +
    DRILL_DOWN_RULES + HIGHLIGHT_RULES + LINKAGE_RULES
)


# ============================================================
# Rule Engine —— 规则执行引擎
# ============================================================

class InteractionRuleEngine:
    """交互规则引擎——评估规则并触发交互生成

    使用方式：
        engine = InteractionRuleEngine()
        matched = engine.evaluate_rules(schema, rule_type="global_filter")
        # matched 是命中的规则列表，交给 Generator 执行
    """

    def __init__(self, rules: Optional[List[InteractionRule]] = None):
        self._rules = rules or ALL_INTERACTION_RULES
        self._custom_rules: List[InteractionRule] = []

    def evaluate_rules(
        self,
        schema: DashboardSchema,
        rule_type: Optional[str] = None,
    ) -> List[InteractionRule]:
        """评估规则，返回命中的规则列表

        Args:
            schema: DashboardSchema（包含 widgets、sections、groups）
            rule_type: 只评估指定类型的规则（None = 全类型）

        Returns:
            命中的规则列表（按 priority 降序排列）
        """
        all_rules = self._rules + self._custom_rules

        # 按类型过滤
        if rule_type:
            all_rules = [r for r in all_rules if r.rule_type == rule_type]

        # 按优先级降序排序
        all_rules.sort(key=lambda r: r.priority, reverse=True)

        # 评估条件
        matched: List[InteractionRule] = []
        for rule in all_rules:
            if rule.condition_fn and rule.condition_fn(schema):
                matched.append(rule)

        return matched

    def add_rule(self, rule: InteractionRule) -> None:
        """扩展：添加自定义交互规则"""
        self._custom_rules.append(rule)


# ============================================================
# Condition Helper Functions —— 规则条件辅助函数
# ============================================================

def _extract_filter_fields(widget: WidgetSlot) -> List[str]:
    """从 WidgetSlot 的 supported_filters 提取 field 名列表"""
    fields = []
    for f in widget.supported_filters:
        if isinstance(f, dict):
            fields.append(f.get("field", ""))
        elif isinstance(f, str):
            fields.append(f)
    return [f for f in fields if f]


def _count_widgets_with_field(schema: DashboardSchema, field_name: str) -> int:
    """统计有多少 Widget 支持某个 filter field"""
    count = 0
    for w in schema.widgets:
        fields = _extract_filter_fields(w)
        if field_name in fields:
            count += 1
    return count


def _has_clickable_chart_with_shared_field(schema: DashboardSchema) -> bool:
    """是否有可点击图表且与其他 Widget 共享 filter field"""
    for w in schema.widgets:
        if w.chart_type in ("bar", "pie", "map", "scatter"):
            fields = _extract_filter_fields(w)
            non_time_fields = [f for f in fields if f != "time"]
            if non_time_fields:
                for other in schema.widgets:
                    if other.widget_id != w.widget_id:
                        other_fields = _extract_filter_fields(other)
                        shared = set(non_time_fields) & set(other_fields)
                        if shared:
                            return True
    return False


def _has_map_with_shared_region(schema: DashboardSchema) -> bool:
    """是否有 map Widget 且与其他 Widget 共享 region"""
    for w in schema.widgets:
        if w.chart_type == "map":
            fields = _extract_filter_fields(w)
            if "region" in fields:
                for other in schema.widgets:
                    if other.widget_id != w.widget_id:
                        other_fields = _extract_filter_fields(other)
                        if "region" in other_fields:
                            return True
    return False


def _has_geo_dimension(schema: DashboardSchema) -> bool:
    """是否有 Widget 含地理维度"""
    geo_keywords = ["province", "city", "region", "country", "district"]
    for w in schema.widgets:
        fields = _extract_filter_fields(w)
        metadata = w.metadata or {}
        text = f"{metadata.get('analysis_type', '')} {metadata.get('business_topic', '')}".lower()
        for kw in geo_keywords:
            if kw in fields or kw in text:
                return True
    return False


def _has_product_dimension(schema: DashboardSchema) -> bool:
    """是否有 Widget 含产品维度"""
    product_keywords = ["category", "product", "sku"]
    for w in schema.widgets:
        fields = _extract_filter_fields(w)
        metadata = w.metadata or {}
        text = f"{metadata.get('analysis_type', '')} {metadata.get('business_topic', '')}".lower()
        for kw in product_keywords:
            if kw in fields or kw in text:
                return True
    return False


def _has_time_dimension(schema: DashboardSchema) -> bool:
    """是否有 Widget 含时间维度（除 time 通用筛选外）"""
    time_keywords = ["year", "quarter", "month", "week", "day"]
    for w in schema.widgets:
        fields = _extract_filter_fields(w)
        metadata = w.metadata or {}
        text = f"{metadata.get('analysis_type', '')} {metadata.get('business_topic', '')}".lower()
        for kw in time_keywords:
            if kw in fields or kw in text:
                return True
    return False


def _has_ranking_widget(schema: DashboardSchema) -> bool:
    """是否有 ranking 类型的 Widget"""
    for w in schema.widgets:
        metadata = w.metadata or {}
        if w.chart_type == "bar" or "ranking" in (metadata.get("visual_role", "") or w.widget_type):
            return True
    return False


def _has_anomaly_widget(schema: DashboardSchema) -> bool:
    """是否有 anomaly 类型的 Widget"""
    for w in schema.widgets:
        metadata = w.metadata or {}
        if w.chart_type == "scatter" or "anomaly" in (metadata.get("visual_role", "") or ""):
            return True
    return False


def _has_trend_widget(schema: DashboardSchema) -> bool:
    """是否有 trend 类型的 Widget"""
    for w in schema.widgets:
        metadata = w.metadata or {}
        if w.chart_type == "line" or "trend" in (metadata.get("visual_role", "") or ""):
            return True
    return False


def _has_kpi_widget(schema: DashboardSchema) -> bool:
    """是否有 KPI 类型的 Widget"""
    for w in schema.widgets:
        if w.widget_type == "kpi":
            return True
    return False


def _has_shared_topic(schema: DashboardSchema) -> bool:
    """是否有 >= 2 Widget 共享同一 business_topic"""
    topics: Dict[str, int] = {}
    for w in schema.widgets:
        metadata = w.metadata or {}
        topic = metadata.get("business_topic", "")
        if topic:
            topics[topic] = topics.get(topic, 0) + 1
    return any(count >= 2 for count in topics.values())


# ============================================================
# Filter Field Label Mapping —— 字段 → 显示标签
# ============================================================

FILTER_FIELD_LABELS: Dict[str, str] = {
    "time": "时间范围",
    "region": "地区",
    "province": "省份",
    "city": "城市",
    "product": "产品",
    "category": "分类",
    "channel": "渠道",
    "brand": "品牌",
    "metric": "指标",
    "customer": "客户",
}

# ============================================================
# Filter Field → Widget Type Mapping —— 字段 → 控件类型
# ============================================================

FILTER_FIELD_WIDGET_TYPES: Dict[str, str] = {
    "time": "date_range",
    "year": "dropdown",
    "quarter": "dropdown",
    "month": "dropdown",
    "region": "dropdown",
    "province": "dropdown",
    "city": "dropdown",
    "product": "dropdown",
    "category": "dropdown",
    "channel": "dropdown",
    "brand": "dropdown",
    "customer": "dropdown",
    "metric": "checkbox",
}
