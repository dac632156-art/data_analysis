"""
Interaction Schema —— Interaction Engine 输出数据模型

定义 Dashboard 的完整交互规则：筛选器、联动、下钻、高亮。
渲染器（Renderer）读取此 Schema 绑定事件。

设计原则：
- 前端框架无关（不绑定 React/Vue/ECharts）
- 纯数据描述
- 预留 AI 推荐探索路径 / 用户自定义筛选器等扩展接口
"""

from __future__ import annotations
from dataclasses import dataclass, field as dc_field
from typing import List, Dict, Any, Optional
from enum import Enum


# ============================================================
# 枚举
# ============================================================

class FilterType(str, Enum):
    GLOBAL = "global"           # 全局筛选器（影响所有 Widget）
    CROSS = "cross"             # 交叉筛选器（Widget 间联动）
    LOCAL = "local"             # 本地筛选器（仅影响自身）


class FilterScope(str, Enum):
    """筛选器作用范围——决定筛选器影响哪些 Widget"""
    GLOBAL = "global"           # 全局：作用整个 Dashboard
    SECTION = "section"         # Section：只作用某个 Section
    WIDGET = "widget"           # Widget：只作用某个 Widget


class InteractionPriority(int, Enum):
    """交互优先级——Renderer 用于决策"""
    GLOBAL_FILTER = 100
    CROSS_FILTER = 80
    DRILL_DOWN = 60
    HIGHLIGHT = 50
    TOOLTIP = 30


class HighlightType(str, Enum):
    TOP_N = "top_n"
    BOTTOM_N = "bottom_n"
    ANOMALY = "anomaly"
    HIGH_GROWTH = "high_growth"
    THRESHOLD = "threshold"
    TREND_CHANGE = "trend_change"


class DrillDownLevel(str, Enum):
    COUNTRY = "country"
    PROVINCE = "province"
    CITY = "city"
    DISTRICT = "district"
    CATEGORY = "category"
    PRODUCT = "product"
    SKU = "sku"
    YEAR = "year"
    QUARTER = "quarter"
    MONTH = "month"
    WEEK = "week"
    DAY = "day"


# ============================================================
# Filter / Event / DrillDown 规则
# ============================================================

@dataclass
class FilterRule:
    """单条筛选器规则"""
    id: str = ""
    name: str = ""                          # 显示名称："时间范围"
    field: str = ""                         # 数据字段名："time"
    filter_type: FilterType = FilterType.GLOBAL
    scope: FilterScope = FilterScope.GLOBAL  # 作用范围（global/section/widget）
    widget_type: str = "date_range"         # 控件类型：date_range / dropdown / checkbox / slider
    target_widgets: List[str] = dc_field(default_factory=list)  # 受影响的 Widget ID 列表
    target_sections: List[str] = dc_field(default_factory=list)  # 受影响的 Section ID 列表（scope=section 时）
    default_value: Optional[str] = None     # 默认值
    priority: int = InteractionPriority.GLOBAL_FILTER
    metadata: Dict[str, Any] = dc_field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "field": self.field,
            "filter_type": self.filter_type.value,
            "scope": self.scope.value,
            "widget_type": self.widget_type,
            "target_widgets": self.target_widgets,
            "target_sections": self.target_sections,
            "default_value": self.default_value,
            "priority": self.priority,
            "metadata": self.metadata,
        }


@dataclass
class CrossFilterRule:
    """Widget 间联动规则"""
    id: str = ""
    source_widget: str = ""                 # 触发源 Widget ID
    event: str = "click"                    # 触发事件："click" / "hover" / "select"
    field: str = ""                         # 联动字段名："region" / "product"
    field_label: str = ""                   # 显示标签
    targets: List[str] = dc_field(default_factory=list)  # 受影响的目标 Widget ID 列表
    priority: int = InteractionPriority.CROSS_FILTER
    bidirectional: bool = False             # 是否双向联动
    metadata: Dict[str, Any] = dc_field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_widget": self.source_widget,
            "event": self.event,
            "field": self.field,
            "field_label": self.field_label,
            "targets": self.targets,
            "priority": self.priority,
            "bidirectional": self.bidirectional,
            "metadata": self.metadata,
        }


@dataclass
class DrillDownRule:
    """下钻规则"""
    id: str = ""
    widget_id: str = ""                     # 下钻起点 Widget ID
    dimension: str = ""                     # 维度名："region" / "product"
    current_level: str = ""                 # 当前层级："province"
    next_level: str = ""                    # 下一层级："city"
    label: str = ""                         # 显示标签："省份 → 城市"
    priority: int = InteractionPriority.DRILL_DOWN
    metadata: Dict[str, Any] = dc_field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "widget_id": self.widget_id,
            "dimension": self.dimension,
            "current_level": self.current_level,
            "next_level": self.next_level,
            "label": self.label,
            "priority": self.priority,
            "metadata": self.metadata,
        }


@dataclass
class HighlightRule:
    """高亮规则"""
    id: str = ""
    widget_id: str = ""                     # 目标 Widget ID
    rule_type: HighlightType = HighlightType.TOP_N
    params: Dict[str, Any] = dc_field(default_factory=dict)  # {"n": 3, "metric": "销售额"}
    label: str = ""                         # 显示说明："高亮 TOP 3"
    priority: int = InteractionPriority.HIGHLIGHT
    metadata: Dict[str, Any] = dc_field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "widget_id": self.widget_id,
            "rule_type": self.rule_type.value,
            "params": self.params,
            "label": self.label,
            "priority": self.priority,
            "metadata": self.metadata,
        }


# ============================================================
# Widget Linkage —— Widget 间联动关系
# ============================================================

class LinkageType(str, Enum):
    """Widget 联动类型"""
    ONE_TO_ONE = "one_to_one"       # 单向一对一：A → B
    ONE_TO_MANY = "one_to_many"     # 单向一对多：A → B, C, D
    MANY_TO_MANY = "many_to_many"   # 多向多对多：A ↔ B ↔ C


@dataclass
class WidgetLinkageRule:
    """Widget 联动规则——描述 Widget 间如何联动

    与 CrossFilterRule 的区别：
    - CrossFilterRule 是具体的数据联动规则（field + filter）
    - WidgetLinkageRule 是抽象的联动关系描述（哪些 Widget 联动 + 联动类型）
    """
    id: str = ""
    source_widgets: List[str] = dc_field(default_factory=list)   # 联动源 Widget IDs
    target_widgets: List[str] = dc_field(default_factory=list)   # 联动目标 Widget IDs
    linkage_type: LinkageType = LinkageType.ONE_TO_MANY
    business_topic: str = ""                                     # 关联的业务主题
    description: str = ""                                        # 联动描述
    metadata: Dict[str, Any] = dc_field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_widgets": self.source_widgets,
            "target_widgets": self.target_widgets,
            "linkage_type": self.linkage_type.value,
            "business_topic": self.business_topic,
            "description": self.description,
            "metadata": self.metadata,
        }


# ============================================================
# Interaction Schema（最终输出）
# ============================================================

@dataclass
class InteractionSchema:
    """Dashboard 交互规则 Schema——Renderer 事件绑定依据

    v2.0 支持 DashboardInteractionEngine 输出（基于 DashboardSchema WidgetSlot）。
    """

    # ========== 标识 ==========
    id: str = ""
    dashboard_id: str = ""                  # 关联的 DashboardSchema.id
    version: str = "2.0"

    # ========== 筛选器 ==========
    global_filters: List[FilterRule] = dc_field(default_factory=list)
    cross_filters: List[CrossFilterRule] = dc_field(default_factory=list)

    # ========== 下钻 ==========
    drill_downs: List[DrillDownRule] = dc_field(default_factory=list)

    # ========== 高亮 ==========
    highlights: List[HighlightRule] = dc_field(default_factory=list)

    # ========== Widget 联动 ==========
    linkages: List[WidgetLinkageRule] = dc_field(default_factory=list)

    # ========== 元数据 ==========
    metadata: Dict[str, Any] = dc_field(default_factory=dict)

    # ========== 预留扩展 ==========
    user_custom_filters: List[Dict[str, Any]] = dc_field(default_factory=list)
    ai_exploration_paths: List[Dict[str, Any]] = dc_field(default_factory=list)
    multi_page_routing: Dict[str, Any] = dc_field(default_factory=dict)
    permission_filters: Dict[str, Any] = dc_field(default_factory=dict)
    animation: Dict[str, Any] = dc_field(default_factory=dict)
    bookmark: Dict[str, Any] = dc_field(default_factory=dict)
    dashboard_state: Dict[str, Any] = dc_field(default_factory=dict)
    undo: Dict[str, Any] = dc_field(default_factory=dict)
    share_state: Dict[str, Any] = dc_field(default_factory=dict)

    # ===== 便捷方法 =====

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "dashboard_id": self.dashboard_id,
            "version": self.version,
            "global_filters": [f.to_dict() for f in self.global_filters],
            "cross_filters": [c.to_dict() for c in self.cross_filters],
            "drill_downs": [d.to_dict() for d in self.drill_downs],
            "highlights": [h.to_dict() for h in self.highlights],
            "linkages": [l.to_dict() for l in self.linkages],
            "metadata": self.metadata,
            "user_custom_filters": self.user_custom_filters,
            "ai_exploration_paths": self.ai_exploration_paths,
            "multi_page_routing": self.multi_page_routing,
            "permission_filters": self.permission_filters,
            "animation": self.animation,
            "bookmark": self.bookmark,
            "dashboard_state": self.dashboard_state,
            "undo": self.undo,
            "share_state": self.share_state,
        }

    def get_all_target_widgets(self) -> List[str]:
        """获取所有被影响的目标 Widget ID（去重）"""
        ids: set = set()
        for f in self.global_filters:
            ids.update(f.target_widgets)
        for c in self.cross_filters:
            ids.add(c.source_widget)
            ids.update(c.targets)
        for d in self.drill_downs:
            ids.add(d.widget_id)
        for h in self.highlights:
            ids.add(h.widget_id)
        for l in self.linkages:
            ids.update(l.source_widgets)
            ids.update(l.target_widgets)
        return sorted(ids)
