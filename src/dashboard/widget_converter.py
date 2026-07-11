"""
Widget Converter —— 旧 Widget → SemanticWidget 双向转换层

核心职责：
- 将旧 Widget 转换为 SemanticWidget（升级路径）
- 将 SemanticWidget 转换为旧 Widget dict（兼容路径）
- 保证双向无损转换

设计原则：
- 旧 Widget 的所有字段在 SemanticWidget 中都有对应
- SemanticWidget 的新字段在旧 Widget 中用默认值/推断值填充
- 旧代码可以继续使用 Widget，新代码使用 SemanticWidget
- 两种格式可以自由互转

使用场景：
1. 系统升级时：旧 WidgetGenerator 生成 Widget → 通过 Converter 升级为 SemanticWidget
2. 前端兼容时：SemanticWidget → 通过 Converter 降级为 Widget dict → 前端无需修改
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional

from src.dashboard.models import (
    Widget, WidgetType, WidgetSize, DisplayRole,
    WidgetFilter, WidgetDataSource,
)
from src.dashboard.semantic_models import (
    SemanticWidget, BusinessTopic, VisualRole, AnalyticalRole,
    PriorityLevel, PreferredSize, RecommendedSection,
    InteractionCapability, ImportanceDetail,
    SemanticFilter, SemanticDataSource,
    RelationType, WidgetRelation,
)


# ============================================================
# Widget → SemanticWidget 转换
# ============================================================

# 旧 Widget 字段 → 新 SemanticWidget 字段 映射表

_WIDGET_TYPE_TO_VISUAL_ROLE: Dict[str, VisualRole] = {
    WidgetType.CHART.value: VisualRole.RANKING,
    WidgetType.KPI.value: VisualRole.OVERVIEW_METRIC,
    WidgetType.TABLE.value: VisualRole.DETAIL,
    WidgetType.MAP.value: VisualRole.GEOGRAPHIC,
    WidgetType.INSIGHT.value: VisualRole.SUMMARY_CARD,
    WidgetType.SUMMARY.value: VisualRole.SUMMARY_CARD,
}

_CHART_TYPE_TO_VISUAL_ROLE: Dict[str, VisualRole] = {
    "line": VisualRole.PRIMARY_TREND,
    "bar": VisualRole.RANKING,
    "pie": VisualRole.COMPOSITION,
    "scatter": VisualRole.CORRELATION,
    "map": VisualRole.GEOGRAPHIC,
}

_BUSINESS_TOPIC_KEYWORD_MAP: Dict[str, BusinessTopic] = {
    "销售": BusinessTopic.SALES,
    "增长": BusinessTopic.GROWTH,
    "客户": BusinessTopic.CUSTOMER,
    "留存": BusinessTopic.CUSTOMER,
    "排名": BusinessTopic.SALES,
    "对比": BusinessTopic.GENERAL,
    "结构": BusinessTopic.GENERAL,
    "集中度": BusinessTopic.RISK,
    "分布": BusinessTopic.GENERAL,
    "异常": BusinessTopic.RISK,
    "地理": BusinessTopic.OPERATION,
}

_ANALYSIS_TYPE_TO_ANALYTICAL_ROLE: Dict[str, AnalyticalRole] = {
    "growth": AnalyticalRole.MONITOR,
    "ranking": AnalyticalRole.COMPARE,
    "comparison": AnalyticalRole.COMPARE,
    "structure": AnalyticalRole.EXPLAIN,
    "concentration": AnalyticalRole.EVALUATE,
    "distribution": AnalyticalRole.EXPLAIN,
    "correlation": AnalyticalRole.DISCOVER,
    "geo": AnalyticalRole.DISCOVER,
    "anomaly": AnalyticalRole.DISCOVER,
    "proportion": AnalyticalRole.EXPLAIN,
    "retention": AnalyticalRole.MONITOR,
}

_DISPLAY_ROLE_TO_SECTION: Dict[str, RecommendedSection] = {
    DisplayRole.MAIN.value: RecommendedSection.MAIN_ANALYSIS,
    DisplayRole.SECONDARY.value: RecommendedSection.COMPARISON,
    DisplayRole.SIDEBAR.value: RecommendedSection.DETAIL,
    DisplayRole.FOOTER.value: RecommendedSection.DETAIL,
}

_SIZE_MAP: Dict[str, PreferredSize] = {
    WidgetSize.HERO.value: PreferredSize.EXTRA_LARGE,
    WidgetSize.LARGE.value: PreferredSize.LARGE,
    WidgetSize.MEDIUM.value: PreferredSize.MEDIUM,
    WidgetSize.SMALL.value: PreferredSize.SMALL,
}

_SIZE_MAP_REVERSE: Dict[str, WidgetSize] = {v: k for k, v in _SIZE_MAP.items()}


class WidgetConverter:
    """Widget → SemanticWidget 双向转换器"""

    # ============================================================
    # Widget → SemanticWidget (升级)
    # ============================================================

    def upgrade(self, widget: Widget) -> SemanticWidget:
        """将旧 Widget 转换为 SemanticWidget

        旧字段映射策略：
        - importance_score: 0-100 → 0-1 (除以 100)
        - widget_type → visual_role (通过映射表 + chart_type 优先)
        - business_topic → 从关键词推断
        - analytical_role → 从 analysis_type 推断
        - priority_level → 从 importance_score 推断
        - preferred_size → 直接映射
        - recommended_section → 从 display_role 映射
        """

        # ----- importance_score: 0-100 → 0-1 -----
        importance_score = widget.importance_score / 100.0

        # ----- visual_role: chart_type 优先，widget_type 降级 -----
        visual_role = VisualRole.RANKING  # 默认
        if widget.chart_type and widget.chart_type in _CHART_TYPE_TO_VISUAL_ROLE:
            visual_role = _CHART_TYPE_TO_VISUAL_ROLE[widget.chart_type]
        elif widget.widget_type.value in _WIDGET_TYPE_TO_VISUAL_ROLE:
            visual_role = _WIDGET_TYPE_TO_VISUAL_ROLE[widget.widget_type.value]

        # ----- business_topic: 从关键词推断 -----
        business_topic = BusinessTopic.GENERAL
        for kw, topic in _BUSINESS_TOPIC_KEYWORD_MAP.items():
            if kw in widget.business_topic:
                business_topic = topic
                break

        # ----- analytical_role: 从 analysis_type 推断 -----
        analytical_role = AnalyticalRole.MONITOR  # 默认
        for atype, role in _ANALYSIS_TYPE_TO_ANALYTICAL_ROLE.items():
            if atype in widget.analysis_type:
                analytical_role = role
                break

        # ----- priority_level: 从 importance_score 推断 -----
        if importance_score >= 0.85:
            priority_level = PriorityLevel.HERO
        elif importance_score >= 0.55:
            priority_level = PriorityLevel.MAJOR
        else:
            priority_level = PriorityLevel.MINOR

        # ----- preferred_size: 直接映射 -----
        preferred_size = _SIZE_MAP.get(widget.preferred_size.value, PreferredSize.MEDIUM)

        # ----- recommended_section: 从 display_role 映射 -----
        recommended_section = _DISPLAY_ROLE_TO_SECTION.get(
            widget.display_role.value, RecommendedSection.MAIN_ANALYSIS
        )

        # ----- business_purpose: 推断 -----
        business_purpose = self._infer_business_purpose(
            widget.analysis_type, widget.business_topic, widget.finding_summary
        )

        # ----- interaction_capabilities: 推断 -----
        interaction_capabilities = []
        if widget.drill_down:
            interaction_capabilities.append(InteractionCapability.DRILL_DOWN)
        if widget.cross_filter:
            interaction_capabilities.append(InteractionCapability.CROSS_FILTER)
        interaction_capabilities.append(InteractionCapability.HOVER_DETAIL)

        # ----- ImportanceDetail: 从 importance_score 推断 -----
        importance_detail = ImportanceDetail(
            weighted_total=importance_score,
            finding_importance=importance_score * 0.3,
            metric_value=importance_score * 0.2,
            analysis_depth=importance_score * 0.15,
            attention_priority=importance_score * 0.2,
            decision_impact=importance_score * 0.15,
        )

        # ----- SemanticFilter: 从 WidgetFilter 转换 -----
        semantic_filters = [
            SemanticFilter(
                field=f.field,
                label=f.label,
                filter_type=f.filter_type,
                business_meaning=f"筛选{f.label}维度",
            )
            for f in widget.supported_filters
        ]

        # ----- SemanticDataSource: 从 WidgetDataSource 转换 -----
        data_source = SemanticDataSource(
            package_id=widget.data_source.package_id,
            finding_ids=widget.data_source.finding_ids,
            chart_slot=widget.data_source.chart_slot,
            table_title=widget.data_source.table_title,
            kpi_label=widget.data_source.kpi_label,
        )

        return SemanticWidget(
            id=widget.id,
            title=widget.title,
            description=widget.description,
            chart_config=widget.chart_config,
            business_topic=business_topic,
            business_purpose=business_purpose,
            visual_role=visual_role,
            analytical_role=analytical_role,
            importance_score=importance_score,
            importance_detail=importance_detail,
            priority_level=priority_level,
            preferred_size=preferred_size,
            recommended_section=recommended_section,
            analysis_type=widget.analysis_type,
            finding_summary=widget.finding_summary,
            chart_type=widget.chart_type,
            supported_filters=semantic_filters,
            interaction_capabilities=interaction_capabilities,
            data_source=data_source,
            metadata=widget.metadata,
        )

    def upgrade_batch(self, widgets: List[Widget]) -> List[SemanticWidget]:
        """批量升级 Widget 列表"""
        semantic_widgets = [self.upgrade(w) for w in widgets]

        # 建立 Widget 间关系
        if len(semantic_widgets) >= 2:
            from src.dashboard.relationship_engine import RelationshipEngine
            engine = RelationshipEngine()
            graph = engine.build_relationships(semantic_widgets)
            semantic_widgets = engine.attach_relationships(semantic_widgets, graph)

        return semantic_widgets

    # ============================================================
    # SemanticWidget → Widget (降级)
    # ============================================================

    def downgrade(self, semantic_widget: SemanticWidget) -> Dict[str, Any]:
        """将 SemanticWidget 降级为旧 Widget 格式 dict

        注意：返回的是 dict 而非 Widget 对象，因为旧代码通常消费 dict。
        """
        return semantic_widget.to_legacy_widget_dict()

    def downgrade_batch(self, semantic_widgets: List[SemanticWidget]) -> List[Dict[str, Any]]:
        """批量降级 SemanticWidget 列表"""
        return [self.downgrade(w) for w in semantic_widgets]

    # ============================================================
    # 辅助方法
    # ============================================================

    def _infer_business_purpose(self, analysis_type: str,
                                 business_topic: str,
                                 finding_summary: str) -> str:
        """推断 business_purpose"""
        # 优先用 finding_summary
        if finding_summary:
            return f"分析{business_topic}：{finding_summary}"

        # 从 analysis_type 推断
        purpose_map = {
            "growth": "监控指标变化趋势，发现增长与衰退信号",
            "ranking": "识别维度排名与集中度差异",
            "comparison": "对比不同维度的指标差异与提升度",
            "structure": "揭示各维度在总量中的占比构成",
            "concentration": "评估集中度风险与帕累托效应",
            "distribution": "展示指标的分布特征与统计规律",
            "correlation": "发现指标间的相关关系",
            "geo": "识别指标在区域维度的地理分布差异",
            "anomaly": "检测异常离群点，发出预警信号",
            "proportion": "揭示各部分在总体中的占比构成",
            "retention": "监控客户留存率与忠诚度变化",
        }

        for atype, purpose in purpose_map.items():
            if atype in analysis_type:
                return purpose

        return f"展示{business_topic}分析结果"


# ============================================================
# 快捷转换函数
# ============================================================

def widget_to_semantic(widget: Widget) -> SemanticWidget:
    """快捷函数：Widget → SemanticWidget"""
    return WidgetConverter().upgrade(widget)


def semantic_to_widget_dict(semantic_widget: SemanticWidget) -> Dict[str, Any]:
    """快捷函数：SemanticWidget → Widget dict"""
    return semantic_widget.to_legacy_widget_dict()


def widget_batch_to_semantic(widgets: List[Widget]) -> List[SemanticWidget]:
    """快捷函数：Widget[] → SemanticWidget[]"""
    return WidgetConverter().upgrade_batch(widgets)
