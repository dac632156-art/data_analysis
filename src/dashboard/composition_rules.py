"""
Composition Rule Library —— Dashboard 组合策略（Rule Engine + Strategy Pattern）

核心职责：
- 定义不同 Dashboard 类型的标准 Section 组成模式
- 根据 Widget 的 business_topic 分布自动选择合适的组合策略
- 提供可扩展的策略注册机制（不写死）

设计原则：
- 不使用 if-else 选择策略
- 采用 Strategy Pattern + Rule Engine
- 新增 Dashboard 类型只需添加一条 CompositionStrategy 配置
- 策略可组合、可覆盖、可扩展

组合策略定义 Dashboard 的"骨架"：
- Executive: Overview → Trend → Comparison → Detail
- Sales: Overview → Sales Trend → Region → Product
- Finance: Overview → Revenue → Cost → Profit
- Operation: Overview → Efficiency → Process → Exception
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field

from src.dashboard.semantic_models import (
    SemanticWidget, BusinessTopic, VisualRole, PriorityLevel,
)
from src.dashboard.composition_schema import (
    BlueprintSectionRole, BlueprintSection, CompositionCluster,
)


# ============================================================
# Composition Strategy —— 组合策略数据模型
# ============================================================

@dataclass
class CompositionStrategy:
    """Dashboard 组合策略——声明式配置，定义 Dashboard 骨架

    每条策略定义：
    - 匹配条件：什么类型的 Widget 组合应该使用这个策略
    - Section 骨架：Dashboard 应该有哪些区域，按什么顺序排列
    - 每个区域的业务含义

    不包含 Grid 信息。
    """
    name: str = ""                                  # 策略名称："executive" / "sales" / "finance"
    display_name: str = ""                           # 显示名称："高管驾驶舱" / "销售看板"

    # 匹配条件
    dominant_topics: List[str] = field(default_factory=list)   # 主要 business_topic（优先匹配）
    required_visual_roles: List[str] = field(default_factory=list)  # 必需的 visual_role
    min_widget_count: int = 0                       # 最少 Widget 数量

    # Section 骨架（按顺序排列）
    section_order: List[BlueprintSectionRole] = field(default_factory=list)

    # 每个 Section 的业务含义
    section_purpose_map: Dict[str, str] = field(default_factory=dict)

    # 阅读流类型
    flow_type: str = ""                             # "executive" / "analytical" / "monitoring"

    # 分组策略：哪些 topic 应该在同一组
    topic_grouping_rules: Dict[str, List[str]] = field(default_factory=dict)


# ============================================================
# Predefined Composition Strategies —— 预定义组合策略
# ============================================================

COMPOSITION_STRATEGIES: Dict[str, CompositionStrategy] = {
    # ===== 高管驾驶舱 =====
    "executive": CompositionStrategy(
        name="executive",
        display_name="高管驾驶舱",
        dominant_topics=["sales", "finance", "growth"],
        required_visual_roles=["overview_metric", "primary_trend"],
        min_widget_count=4,
        section_order=[
            BlueprintSectionRole.OVERVIEW,
            BlueprintSectionRole.MAIN_ANALYSIS,
            BlueprintSectionRole.COMPARISON,
            BlueprintSectionRole.MONITORING,
            BlueprintSectionRole.DETAIL,
        ],
        section_purpose_map={
            "overview": "展示核心经营指标与全局状态",
            "main_analysis": "展示关键业务趋势与核心发现",
            "comparison": "展示维度对比与排名分析",
            "monitoring": "监测异常指标与风险预警",
            "detail": "补充辅助分析细节",
        },
        flow_type="executive",
        topic_grouping_rules={
            "sales": ["growth", "ranking", "structure"],
            "finance": ["comparison", "concentration"],
        },
    ),

    # ===== 销售看板 =====
    "sales": CompositionStrategy(
        name="sales",
        display_name="销售看板",
        dominant_topics=["sales", "growth"],
        required_visual_roles=["primary_trend", "ranking"],
        min_widget_count=3,
        section_order=[
            BlueprintSectionRole.OVERVIEW,
            BlueprintSectionRole.MAIN_ANALYSIS,
            BlueprintSectionRole.RANKING,
            BlueprintSectionRole.COMPARISON,
            BlueprintSectionRole.DETAIL,
        ],
        section_purpose_map={
            "overview": "展示销售额核心指标",
            "main_analysis": "展示销售趋势变化",
            "ranking": "展示区域/产品销售排名",
            "comparison": "展示结构占比与对比分析",
            "detail": "补充销售细节信息",
        },
        flow_type="analytical",
        topic_grouping_rules={
            "sales": ["growth", "ranking", "structure", "geo"],
        },
    ),

    # ===== 财务看板 =====
    "finance": CompositionStrategy(
        name="finance",
        display_name="财务看板",
        dominant_topics=["finance"],
        required_visual_roles=["overview_metric", "composition"],
        min_widget_count=3,
        section_order=[
            BlueprintSectionRole.OVERVIEW,
            BlueprintSectionRole.MAIN_ANALYSIS,
            BlueprintSectionRole.COMPARISON,
            BlueprintSectionRole.DISTRIBUTION,
            BlueprintSectionRole.DETAIL,
        ],
        section_purpose_map={
            "overview": "展示营收/利润核心指标",
            "main_analysis": "展示收入趋势变化",
            "comparison": "展示成本结构占比对比",
            "distribution": "展示财务分布与集中度",
            "detail": "补充财务辅助信息",
        },
        flow_type="analytical",
        topic_grouping_rules={
            "finance": ["comparison", "concentration", "distribution"],
        },
    ),

    # ===== 运营看板 =====
    "operation": CompositionStrategy(
        name="operation",
        display_name="运营看板",
        dominant_topics=["operation", "efficiency"],
        required_visual_roles=["overview_metric", "ranking"],
        min_widget_count=3,
        section_order=[
            BlueprintSectionRole.OVERVIEW,
            BlueprintSectionRole.MAIN_ANALYSIS,
            BlueprintSectionRole.RANKING,
            BlueprintSectionRole.MONITORING,
            BlueprintSectionRole.DETAIL,
        ],
        section_purpose_map={
            "overview": "展示运营效率核心指标",
            "main_analysis": "展示关键运营趋势",
            "ranking": "展示区域/渠道运营排名",
            "monitoring": "监测异常指标与效率预警",
            "detail": "补充运营辅助信息",
        },
        flow_type="monitoring",
        topic_grouping_rules={
            "operation": ["ranking", "geo", "efficiency"],
        },
    ),

    # ===== 风险监控 =====
    "risk": CompositionStrategy(
        name="risk",
        display_name="风险监控",
        dominant_topics=["risk"],
        required_visual_roles=["warning", "overview_metric"],
        min_widget_count=2,
        section_order=[
            BlueprintSectionRole.OVERVIEW,
            BlueprintSectionRole.MONITORING,
            BlueprintSectionRole.MAIN_ANALYSIS,
            BlueprintSectionRole.DETAIL,
        ],
        section_purpose_map={
            "overview": "展示风险状态概览",
            "monitoring": "监测异常与风险预警",
            "main_analysis": "展示风险趋势与变化",
            "detail": "补充风险细节信息",
        },
        flow_type="monitoring",
        topic_grouping_rules={
            "risk": ["anomaly", "concentration", "distribution"],
        },
    ),

    # ===== 客户看板 =====
    "customer": CompositionStrategy(
        name="customer",
        display_name="客户看板",
        dominant_topics=["customer"],
        required_visual_roles=["overview_metric", "primary_trend"],
        min_widget_count=2,
        section_order=[
            BlueprintSectionRole.OVERVIEW,
            BlueprintSectionRole.MAIN_ANALYSIS,
            BlueprintSectionRole.COMPARISON,
            BlueprintSectionRole.DETAIL,
        ],
        section_purpose_map={
            "overview": "展示客户核心指标",
            "main_analysis": "展示留存/复购趋势",
            "comparison": "展示客户分层对比",
            "detail": "补充客户细节信息",
        },
        flow_type="analytical",
        topic_grouping_rules={
            "customer": ["retention", "growth", "comparison"],
        },
    ),

    # ===== 通用分析（默认） =====
    "general": CompositionStrategy(
        name="general",
        display_name="综合分析",
        dominant_topics=["general"],
        required_visual_roles=[],
        min_widget_count=1,
        section_order=[
            BlueprintSectionRole.OVERVIEW,
            BlueprintSectionRole.MAIN_ANALYSIS,
            BlueprintSectionRole.COMPARISON,
            BlueprintSectionRole.DETAIL,
        ],
        section_purpose_map={
            "overview": "展示核心指标概览",
            "main_analysis": "展示主要趋势与发现",
            "comparison": "展示维度对比分析",
            "detail": "补充辅助信息",
        },
        flow_type="analytical",
        topic_grouping_rules={},
    ),
}

# 默认策略
DEFAULT_STRATEGY = COMPOSITION_STRATEGIES["general"]


# ============================================================
# Strategy Selector —— 策略选择器（Rule Engine）
# ============================================================

class CompositionStrategySelector:
    """组合策略选择器——根据 Widget 属性自动选择最合适的组合策略

    使用 Rule Engine：
    - 每条规则是一个 (条件函数, 策略名) 元组
    - 按优先级评估，首次命中即返回
    - 新增策略只需添加规则，无需修改选择器代码
    """

    def __init__(self):
        self._rules: List[Tuple[Callable, str]] = []
        self._register_default_rules()

    def _register_default_rules(self):
        """注册默认策略选择规则（策略模式）"""
        self._rules = [
            # Rule 1: 有 warning Widget + risk topic → risk
            (self._has_risk_warning, "risk"),
            # Rule 2: dominant topic = customer → customer
            (self._is_customer_dominant, "customer"),
            # Rule 3: dominant topic = finance → finance
            (self._is_finance_dominant, "finance"),
            # Rule 4: dominant topic = operation/efficiency → operation
            (self._is_operation_dominant, "operation"),
            # Rule 5: dominant topic = sales/growth → sales
            (self._is_sales_dominant, "sales"),
            # Rule 6: 有 overview_metric + primary_trend → executive
            (self._has_executive_pattern, "executive"),
            # Rule 7: 有 geographic → executive (with geo)
            (self._has_geo_widgets, "executive"),
        ]

    def select(self, widgets: List[SemanticWidget]) -> CompositionStrategy:
        """根据 Widget 属性选择组合策略

        Args:
            widgets: SemanticWidget 列表

        Returns:
            CompositionStrategy
        """
        # 按规则依次评估
        for condition, strategy_name in self._rules:
            if condition(widgets):
                return COMPOSITION_STRATEGIES.get(strategy_name, DEFAULT_STRATEGY)

        # Fallback: 根据 topic 分布选策略
        strategy = self._select_by_topic_distribution(widgets)
        if strategy:
            return strategy

        # Default
        return DEFAULT_STRATEGY

    def _select_by_topic_distribution(self, widgets: List[SemanticWidget]) -> Optional[CompositionStrategy]:
        """根据 topic 分布选择策略"""
        from collections import Counter
        topic_counts = Counter(w.business_topic.value for w in widgets)
        dominant_topic = topic_counts.most_common(1)[0][0] if topic_counts else "general"

        # 尝试在策略中匹配 dominant_topics
        for name, strategy in COMPOSITION_STRATEGIES.items():
            if dominant_topic in strategy.dominant_topics:
                return strategy

        return None

    # ===== 规则条件函数 =====

    @staticmethod
    def _has_risk_warning(widgets: List[SemanticWidget]) -> bool:
        """有 warning Widget 且 topic = risk"""
        for w in widgets:
            if w.visual_role == VisualRole.WARNING and w.business_topic == BusinessTopic.RISK:
                return True
        # topic 分布中 risk 占比 > 30%
        risk_count = sum(1 for w in widgets if w.business_topic == BusinessTopic.RISK)
        return risk_count > len(widgets) * 0.3

    @staticmethod
    def _is_customer_dominant(widgets: List[SemanticWidget]) -> bool:
        """customer topic 占比最高"""
        from collections import Counter
        topics = Counter(w.business_topic.value for w in widgets)
        if not topics:
            return False
        dominant = topics.most_common(1)[0][0]
        return dominant == "customer"

    @staticmethod
    def _is_finance_dominant(widgets: List[SemanticWidget]) -> bool:
        """finance topic 占比最高"""
        from collections import Counter
        topics = Counter(w.business_topic.value for w in widgets)
        if not topics:
            return False
        dominant = topics.most_common(1)[0][0]
        return dominant == "finance"

    @staticmethod
    def _is_operation_dominant(widgets: List[SemanticWidget]) -> bool:
        """operation/efficiency topic 占比最高"""
        from collections import Counter
        topics = Counter(w.business_topic.value for w in widgets)
        if not topics:
            return False
        dominant = topics.most_common(1)[0][0]
        return dominant in ("operation", "efficiency")

    @staticmethod
    def _is_sales_dominant(widgets: List[SemanticWidget]) -> bool:
        """sales/growth topic 占比最高"""
        from collections import Counter
        topics = Counter(w.business_topic.value for w in widgets)
        if not topics:
            return False
        dominant = topics.most_common(1)[0][0]
        return dominant in ("sales", "growth")

    @staticmethod
    def _has_executive_pattern(widgets: List[SemanticWidget]) -> bool:
        """有 overview_metric + primary_trend 的高管驾驶舱模式"""
        has_overview = any(w.visual_role == VisualRole.OVERVIEW_METRIC for w in widgets)
        has_trend = any(w.visual_role == VisualRole.PRIMARY_TREND for w in widgets)
        return has_overview and has_trend and len(widgets) >= 4

    @staticmethod
    def _has_geo_widgets(widgets: List[SemanticWidget]) -> bool:
        """有 geographic Widget"""
        return any(w.visual_role == VisualRole.GEOGRAPHIC for w in widgets)

    def add_rule(self, condition: Callable, strategy_name: str):
        """扩展：添加自定义策略选择规则"""
        self._rules.append((condition, strategy_name))
