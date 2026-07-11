"""
Semantic Widget Data Model —— 具有完整业务语义的可视化组件数据契约

与旧 Widget 的区别：
- Widget: 纯视觉数据容器（chart_type + data + importance_score）
- SemanticWidget: 具有业务语义的数据容器（business_purpose + visual_role + analytical_role + priority_level + related_widgets）

设计原则：
- 每个 Widget 都有明确的"为什么存在"（business_purpose）
- 每个 Widget 都有明确的"视觉角色"（visual_role）——告诉 Dashboard Planner 它应该放在哪里
- 每个 Widget 都有明确的"分析角色"（analytical_role）——告诉 Dashboard Planner 它解释什么
- Widget 之间有语义关系（related_widgets）——支持 Dashboard Composition Planner 组合编排
- importance_score 从 0-100 整数升级为 0-1 浮点数，综合 5 个维度加权计算
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import uuid


# ============================================================
# Semantic Enumerations —— 标准化业务语义枚举
# ============================================================

class BusinessTopic(str, Enum):
    """业务领域——Widget 所属的业务主题"""
    SALES = "sales"             # 销售
    CUSTOMER = "customer"       # 客户
    PRODUCT = "product"         # 产品
    FINANCE = "finance"         # 财务
    OPERATION = "operation"     # 运营
    GROWTH = "growth"           # 增长
    RISK = "risk"               # 风险
    EFFICIENCY = "efficiency"   # 效率
    QUALITY = "quality"         # 质量
    GENERAL = "general"         # 通用


class VisualRole(str, Enum):
    """视觉角色——Widget 在 Dashboard 中的视觉功能定位

    决定了 Dashboard Planner 如何安排这个 Widget 的展示方式。
    """
    OVERVIEW_METRIC = "overview_metric"     # 核心指标卡（KPI）
    PRIMARY_TREND = "primary_trend"         # 核心趋势（折线图）
    COMPARISON = "comparison"               # 比较分析（分组柱状图）
    RANKING = "ranking"                     # 排名分析（排序柱状图）
    DISTRIBUTION = "distribution"           # 分布分析（直方图/箱线图）
    COMPOSITION = "composition"             # 占比分析（饼图/环形图）
    GEOGRAPHIC = "geographic"               # 区域分析（地图）
    CORRELATION = "correlation"             # 关联分析（散点图）
    DETAIL = "detail"                       # 详细信息（表格）
    WARNING = "warning"                     # 异常监控（异常标记图）
    SUMMARY_CARD = "summary_card"           # 摘要卡片（文字洞察）
    CONCENTRATION = "concentration"         # 集中度分析（帕累托图）


class AnalyticalRole(str, Enum):
    """分析角色——Widget 在业务分析中承担的作用

    告诉 Dashboard Planner 这个 Widget 是"监控"、"解释"、"比较"还是"发现"。
    """
    MONITOR = "monitor"         # 监控——跟踪关键指标变化
    EXPLAIN = "explain"         # 解释——揭示变化原因
    COMPARE = "compare"         # 比较——对比不同维度差异
    DISCOVER = "discover"       # 发现——揭示新模式/异常
    PREDICT = "predict"         # 预测——趋势预测
    EVALUATE = "evaluate"       # 评价——评估表现/效果
    SUMMARIZE = "summarize"     # 概括——汇总全局状态


class PriorityLevel(str, Enum):
    """优先级——基于业务重要性划分的三级优先级

    Hero: 企业核心指标，必须占据 Dashboard 最显著位置
    Major: 关键分析，需要清晰展示但不是最突出
    Minor: 辅助信息，补充背景或提供细节
    """
    HERO = "hero"
    MAJOR = "major"
    MINOR = "minor"


class PreferredSize(str, Enum):
    """推荐尺寸——Widget 在 Dashboard 中的空间占用建议

    extra_large: 全宽大图（核心趋势、关键 KPI）
    large: 大半格（排名分析、比较分析）
    medium: 标准格（辅助图表、指标卡）
    small: 小格（侧边栏信息、文字洞察）
    """
    EXTRA_LARGE = "extra_large"
    LARGE = "large"
    MEDIUM = "medium"
    SMALL = "small"


class RecommendedSection(str, Enum):
    """推荐区域——Widget 应该放在 Dashboard 的哪个区域"""
    OVERVIEW = "overview"               # 概览区（顶部 KPI 行）
    MAIN_ANALYSIS = "main_analysis"     # 主分析区（核心图表区）
    COMPARISON = "comparison"           # 比较区（对比分析区）
    DETAIL = "detail"                   # 详情区（底部表格/辅助信息）
    MONITORING = "monitoring"           # 监控区（异常预警/实时跟踪）


class InteractionCapability(str, Enum):
    """交互能力——Widget 支持的交互方式"""
    DRILL_DOWN = "drill_down"           # 下钻
    CROSS_FILTER = "cross_filter"       # 交叉筛选
    TIME_RANGE = "time_range"           # 时间范围选择
    DIMENSION_SWITCH = "dimension_switch"  # 维度切换
    HOVER_DETAIL = "hover_detail"       # 悬浮详情
    CLICK_LINK = "click_link"           # 点击关联


# ============================================================
# Semantic Filter & Data Source
# ============================================================

@dataclass
class SemanticFilter:
    """语义化筛选器——带有业务含义的筛选配置"""
    field: str = ""                     # 筛选字段名
    label: str = ""                     # 显示标签
    filter_type: str = ""               # 筛选类型：dropdown / date_range / checkbox
    business_meaning: str = ""          # 业务含义："选择要对比的地区维度"
    default_value: Optional[str] = None # 默认值


@dataclass
class SemanticDataSource:
    """语义化数据源引用——比 WidgetDataSource 更明确"""
    package_id: str = ""
    finding_ids: List[str] = field(default_factory=list)
    chart_slot: str = ""
    table_title: str = ""
    kpi_label: str = ""
    data_coverage: float = 0.0          # 数据覆盖度 0-1（有多少数据点可用）


# ============================================================
# Widget Relationship —— Widget 间语义关系
# ============================================================

class RelationType(str, Enum):
    """Widget 间关系类型"""
    EXPLAIN = "explain"         # 解释关系：A 解释 B 的变化原因
    DEPEND = "depend"           # 依赖关系：A 的理解需要先看 B
    COMPLEMENT = "complement"   # 补充关系：A 和 B 从不同角度展示同一主题
    CONTRAST = "contrast"       # 对比关系：A 和 B 展示对立视角
    DRILL = "drill"             # 下钻关系：A 是 B 的细化视图


@dataclass
class WidgetRelation:
    """Widget 间关系描述"""
    target_widget_id: str = ""          # 关联目标 Widget ID
    relation_type: RelationType = RelationType.COMPLEMENT
    description: str = ""               # 关系描述："区域排名解释销售变化来源"


# ============================================================
# Importance Score Detail —— 重要性评分明细
# ============================================================

@dataclass
class ImportanceDetail:
    """重要性评分明细——展示每个维度的贡献

    让 Dashboard Planner 理解为什么某个 Widget 的 importance_score 是 0.9。
    """
    finding_importance: float = 0.0      # BusinessFinding 的重要性贡献 0-1
    metric_value: float = 0.0            # Metric 业务价值贡献 0-1
    analysis_depth: float = 0.0          # 分析深度贡献 0-1
    attention_priority: float = 0.0      # 用户关注度贡献 0-1
    decision_impact: float = 0.0         # 决策影响力贡献 0-1
    weighted_total: float = 0.0          # 加权总分 0-1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_importance": round(self.finding_importance, 4),
            "metric_value": round(self.metric_value, 4),
            "analysis_depth": round(self.analysis_depth, 4),
            "attention_priority": round(self.attention_priority, 4),
            "decision_impact": round(self.decision_impact, 4),
            "weighted_total": round(self.weighted_total, 4),
        }


# ============================================================
# SemanticWidget —— 核心领域模型
# ============================================================

@dataclass
class SemanticWidget:
    """具有完整业务语义的可视化组件

    与 Widget 的核心区别：
    1. Widget 只知道"画什么图"，不知道"为什么画"
    2. SemanticWidget 知道"为什么画"、"画给谁看"、"和什么图关联"

    生产方：SemanticWidgetGenerator
    消费方：Dashboard Composition Planner / Layout Engine / Renderer
    """

    # ========== 标识层 ==========
    id: str = ""                                        # 唯一标识
    title: str = ""                                     # Widget 标题
    description: str = ""                               # 简短描述（2 句话）

    # ========== 图表配置 ==========
    chart_config: Dict[str, Any] = field(default_factory=dict)  # ECharts option 或构造配置

    # ========== 业务语义层（SemanticWidget 核心） ==========
    business_topic: BusinessTopic = BusinessTopic.GENERAL    # 业务领域
    business_purpose: str = ""                                # 业务目的："监控销售额变化趋势"
    visual_role: VisualRole = VisualRole.RANKING              # 视觉角色
    analytical_role: AnalyticalRole = AnalyticalRole.MONITOR  # 分析角色

    # ========== 重要性层 ==========
    importance_score: float = 0.5                             # 重要性评分 0-1
    importance_detail: ImportanceDetail = field(default_factory=ImportanceDetail)
    priority_level: PriorityLevel = PriorityLevel.MAJOR       # 优先级

    # ========== 布局建议层 ==========
    preferred_size: PreferredSize = PreferredSize.MEDIUM      # 推荐尺寸
    recommended_section: RecommendedSection = RecommendedSection.MAIN_ANALYSIS  # 推荐区域

    # ========== 分析角色层 ==========
    analysis_type: str = ""                                   # 原始 analysis_type
    finding_summary: str = ""                                  # 核心发现摘要
    chart_type: Optional[str] = None                           # 图表类型（line/bar/pie 等）

    # ========== Widget 关系层 ==========
    related_widgets: List[WidgetRelation] = field(default_factory=list)

    # ========== 交互能力层 ==========
    supported_filters: List[SemanticFilter] = field(default_factory=list)
    interaction_capabilities: List[InteractionCapability] = field(default_factory=list)

    # ========== 数据源层 ==========
    data_source: SemanticDataSource = field(default_factory=SemanticDataSource)

    # ========== 元数据层 ==========
    metadata: Dict[str, Any] = field(default_factory=dict)
    _raw_package_ref: Optional[str] = None                    # 内部引用（不序列化）

    def __post_init__(self):
        if not self.id:
            self.id = f"{self.business_topic.value}_{self.visual_role.value}_{str(uuid.uuid4())[:6]}"

    # ===== 便捷方法 =====

    def to_dict(self) -> Dict[str, Any]:
        """序列化为前端/下游消费的字典"""
        import dataclasses
        d = dataclasses.asdict(self)
        # 将枚举转为字符串值
        d["business_topic"] = self.business_topic.value
        d["visual_role"] = self.visual_role.value
        d["analytical_role"] = self.analytical_role.value
        d["priority_level"] = self.priority_level.value
        d["preferred_size"] = self.preferred_size.value
        d["recommended_section"] = self.recommended_section.value
        d["interaction_capabilities"] = [c.value for c in self.interaction_capabilities]
        d["related_widgets"] = [
            {
                "target_widget_id": r.target_widget_id,
                "relation_type": r.relation_type.value,
                "description": r.description,
            }
            for r in self.related_widgets
        ]
        d["supported_filters"] = [
            {
                "field": f.field,
                "label": f.label,
                "filter_type": f.filter_type,
                "business_meaning": f.business_meaning,
                "default_value": f.default_value,
            }
            for f in self.supported_filters
        ]
        d["importance_detail"] = self.importance_detail.to_dict()
        d["data_source"] = {
            "package_id": self.data_source.package_id,
            "finding_ids": self.data_source.finding_ids,
            "chart_slot": self.data_source.chart_slot,
            "table_title": self.data_source.table_title,
            "kpi_label": self.data_source.kpi_label,
            "data_coverage": self.data_source.data_coverage,
        }
        d.pop("_raw_package_ref", None)
        return d

    def to_api_dict(self) -> Dict[str, Any]:
        """API 响应格式"""
        return self.to_dict()

    def to_legacy_widget_dict(self) -> Dict[str, Any]:
        """转换为旧 Widget 格式——保证向后兼容"""
        from src.dashboard.models import WidgetSize, DisplayRole, WidgetType

        # priority_level → importance_score (0-100)
        legacy_score = round(self.importance_score * 100)

        # preferred_size mapping: Semantic → Legacy
        size_map = {
            PreferredSize.EXTRA_LARGE: WidgetSize.HERO,
            PreferredSize.LARGE: WidgetSize.LARGE,
            PreferredSize.MEDIUM: WidgetSize.MEDIUM,
            PreferredSize.SMALL: WidgetSize.SMALL,
        }
        legacy_size = size_map.get(self.preferred_size, WidgetSize.MEDIUM)

        # visual_role → display_role mapping
        role_map = {
            VisualRole.OVERVIEW_METRIC: DisplayRole.MAIN,
            VisualRole.PRIMARY_TREND: DisplayRole.MAIN,
            VisualRole.WARNING: DisplayRole.MAIN,
            VisualRole.GEOGRAPHIC: DisplayRole.MAIN,
        }
        legacy_role = role_map.get(self.visual_role, DisplayRole.SECONDARY)

        # visual_role → widget_type mapping
        type_map = {
            VisualRole.OVERVIEW_METRIC: WidgetType.KPI,
            VisualRole.SUMMARY_CARD: WidgetType.SUMMARY,
            VisualRole.DETAIL: WidgetType.TABLE,
        }
        legacy_type = type_map.get(self.visual_role, WidgetType.CHART)

        # interaction_capabilities → drill_down / cross_filter
        has_drill = InteractionCapability.DRILL_DOWN in self.interaction_capabilities
        has_cross = InteractionCapability.CROSS_FILTER in self.interaction_capabilities

        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "widget_type": legacy_type.value,
            "analysis_type": self.analysis_type,
            "business_topic": self.business_topic.value,
            "finding_summary": self.finding_summary,
            "importance_score": legacy_score,
            "chart_type": self.chart_type,
            "chart_config": self.chart_config,
            "preferred_size": legacy_size.value,
            "priority": max(1, round(self.importance_score * 10)),
            "display_role": legacy_role.value,
            "supported_filters": [
                {"field": f.field, "label": f.label, "filter_type": f.filter_type}
                for f in self.supported_filters
            ],
            "drill_down": has_drill,
            "cross_filter": has_cross,
            "metadata": self.metadata,
            "data_source": {
                "package_id": self.data_source.package_id,
                "finding_ids": self.data_source.finding_ids,
                "chart_slot": self.data_source.chart_slot,
                "table_title": self.data_source.table_title,
                "kpi_label": self.data_source.kpi_label,
            },
        }


# ============================================================
# Dependency Graph —— Widget 关系图
# ============================================================

@dataclass
class DependencyGraph:
    """Widget 间依赖关系图

    用于 Dashboard Composition Planner 识别 Widget 组合关系。
    """
    nodes: Dict[str, str] = field(default_factory=dict)       # widget_id → brief description
    edges: List[Dict[str, str]] = field(default_factory=list)  # [{source, target, type, description}]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": self.nodes,
            "edges": self.edges,
        }

    def add_relation(self, source_id: str, target_id: str,
                     relation_type: RelationType, description: str = ""):
        """添加一条关系边"""
        self.edges.append({
            "source": source_id,
            "target": target_id,
            "type": relation_type.value,
            "description": description,
        })
