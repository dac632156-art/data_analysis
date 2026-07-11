"""
Dashboard Blueprint Schema —— Composition Planner 的输出数据模型

核心区别：
- Layout Schema (layout_schema.py): 包含 x/y/w/h Grid 信息，是 Renderer 的输入
- Blueprint Schema: 只包含内容组织信息（Section/Group/Flow/Graph），不含任何布局参数

设计原则：
- Blueprint 不包含 x, y, w, h, Grid, Margin, Gap
- Blueprint 是 Composition Planner 的唯一输出
- Blueprint 是 Layout Engine 的输入（Layout Engine 从 Blueprint 读取 Section/Widget 信息）
- 预留 Theme / Responsive / Animation / Dark Mode / Mobile 接口（当前不实现）

生产方：DashboardCompositionPlanner
消费方：Layout Engine（后续升级为读取 Blueprint）
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import uuid
import time


# ============================================================
# Section Role —— Blueprint Section 角色枚举
# ============================================================

class BlueprintSectionRole(str, Enum):
    """Blueprint Section 角色——比 Layout Schema 的 SectionRole 更丰富

    扩展了原有 SectionRole，增加了 composition planner 识别的业务区域角色。
    """
    OVERVIEW = "overview"               # 概览区——核心 KPI + 总览指标
    MAIN_ANALYSIS = "main_analysis"     # 主分析区——核心趋势/关键发现
    COMPARISON = "comparison"           # 比较区——排名/结构/对比分析
    DISTRIBUTION = "distribution"       # 分布区——分布/集中度分析
    RANKING = "ranking"                 # 排名区——TOP 排名分析
    GEOGRAPHIC = "geographic"           # 地理区——地图/区域分析
    MONITORING = "monitoring"           # 监控区——异常/风险预警
    DETAIL = "detail"                   # 详情区——辅助表格/细节信息


# ============================================================
# Blueprint Section —— Dashboard 内容区域
# ============================================================

@dataclass
class BlueprintSection:
    """Dashboard Blueprint Section——内容组织区域

    不包含 y_start, y_end 等 Grid 信息。
    只描述：这个区域叫什么、为什么存在、放哪些 Widget。
    """
    id: str = ""                                    # Section ID
    role: BlueprintSectionRole = BlueprintSectionRole.MAIN_ANALYSIS
    title: str = ""                                  # 区域标题："核心指标概览"
    purpose: str = ""                                # 区域目的："展示核心经营指标"
    priority: int = 0                                # 区域优先级（1=最高）
    widget_ids: List[str] = field(default_factory=list)  # 区域内 Widget ID 列表（按 importance 降序）

    # 区域摘要（由 Planner 自动计算）
    dominant_visual_role: str = ""                   # 区域内最多的 visual_role
    dominant_business_topic: str = ""                # 区域内最多的 business_topic
    avg_importance: float = 0.0                      # 区域内 Widget 平均 importance_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role.value,
            "title": self.title,
            "purpose": self.purpose,
            "priority": self.priority,
            "widget_ids": self.widget_ids,
            "dominant_visual_role": self.dominant_visual_role,
            "dominant_business_topic": self.dominant_business_topic,
            "avg_importance": round(self.avg_importance, 4),
        }


# ============================================================
# Widget Group —— 业务主题分组
# ============================================================

@dataclass
class WidgetGroup:
    """Widget 业务主题分组——同一 business_topic 的 Widget 聚合

    用于 Composition Planner 识别 Dashboard 的业务领域组成。
    """
    id: str = ""                                    # 分组 ID
    topic: str = ""                                  # business_topic 值
    title: str = ""                                  # 分组标题："销售分析"
    widget_ids: List[str] = field(default_factory=list)
    visual_roles: List[str] = field(default_factory=list)   # 分组内的 visual_role 集合
    analytical_roles: List[str] = field(default_factory=list)  # 分组内的 analytical_role 集合
    avg_importance: float = 0.0                      # 分组平均 importance_score
    priority_level: str = ""                         # 分组整体优先级 (hero/major/minor)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "title": self.title,
            "widget_ids": self.widget_ids,
            "visual_roles": self.visual_roles,
            "analytical_roles": self.analytical_roles,
            "avg_importance": round(self.avg_importance, 4),
            "priority_level": self.priority_level,
        }


# ============================================================
# Composition Graph —— Widget 组合关系图
# ============================================================

@dataclass
class CompositionEdge:
    """组合关系边——描述 Widget 间在 Dashboard 组成中的关系"""
    source: str = ""                 # 源 Widget ID
    target: str = ""                 # 目标 Widget ID
    relation_type: str = ""          # 关系类型：explain/depend/complement/contrast/drill
    description: str = ""            # 关系描述

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation_type": self.relation_type,
            "description": self.description,
        }


@dataclass
class CompositionCluster:
    """Widget 组合簇——围绕核心 Widget 的关联 Widget 集合

    用于 Layout Engine 理解哪些 Widget 应该放在一起。
    """
    core_widget_id: str = ""         # 核心 Widget（importance_score 最高）
    cluster_type: str = ""           # 簇类型：trend_cluster / ranking_cluster / structure_cluster 等
    member_ids: List[str] = field(default_factory=list)  # 簇内 Widget IDs
    description: str = ""            # 簇描述："销售趋势 + 区域排名 + 产品结构"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "core_widget_id": self.core_widget_id,
            "cluster_type": self.cluster_type,
            "member_ids": self.member_ids,
            "description": self.description,
        }


@dataclass
class CompositionGraph:
    """Dashboard 组合关系图

    从 Widget related_widgets 和 business_topic 聚合构建。
    用于 Layout Engine 决定 Widget 组合布局。
    """
    nodes: Dict[str, str] = field(default_factory=dict)          # widget_id → brief
    edges: List[CompositionEdge] = field(default_factory=list)
    clusters: List[CompositionCluster] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": self.nodes,
            "edges": [e.to_dict() for e in self.edges],
            "clusters": [c.to_dict() for c in self.clusters],
        }


# ============================================================
# Reading Flow —— Dashboard 阅读顺序
# ============================================================

@dataclass
class FlowStep:
    """阅读流步骤——描述用户浏览 Dashboard 的推荐顺序"""
    section_id: str = ""             # 对应的 Section ID
    role: str = ""                   # Section 角色
    title: str = ""                  # 显示标题
    purpose: str = ""                # 这个步骤的业务目的
    order: int = 0                   # 步骤序号（1-based）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_id": self.section_id,
            "role": self.role,
            "title": self.title,
            "purpose": self.purpose,
            "order": self.order,
        }


@dataclass
class ReadingFlow:
    """Dashboard 阅读流——定义用户从上到下浏览 Dashboard 的推荐路径

    不是 Widget 顺序，而是 Section 顺序。
    例如：Overview → Main → Comparison → Detail
    """
    steps: List[FlowStep] = field(default_factory=list)
    flow_type: str = ""              # 流类型：executive / analytical / monitoring 等

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flow_type": self.flow_type,
            "steps": [s.to_dict() for s in self.steps],
        }


# ============================================================
# Visual Hierarchy —— 信息层级
# ============================================================

@dataclass
class VisualHierarchy:
    """Dashboard 信息层级——定义 Hero/Major/Minor 的分布

    只定义层级关系，不定义位置（x/y）。
    """
    hero_widgets: List[str] = field(default_factory=list)     # Hero Widget IDs
    major_widgets: List[str] = field(default_factory=list)    # Major Widget IDs
    minor_widgets: List[str] = field(default_factory=list)    # Minor Widget IDs

    hero_count: int = 0
    major_count: int = 0
    minor_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hero_widgets": self.hero_widgets,
            "major_widgets": self.major_widgets,
            "minor_widgets": self.minor_widgets,
            "hero_count": self.hero_count,
            "major_count": self.major_count,
            "minor_count": self.minor_count,
        }


# ============================================================
# Blueprint Metadata
# ============================================================

@dataclass
class BlueprintMetadata:
    """Blueprint 元数据"""
    id: str = ""
    title: str = "数据分析驾驶舱"
    created_at: str = ""
    version: str = "2.0"                     # v2 = Composition Planner 版本

    # 统计信息
    widget_count: int = 0
    section_count: int = 0
    group_count: int = 0

    # 主题分布
    topic_distribution: Dict[str, int] = field(default_factory=dict)   # {topic: widget_count}
    dominant_topic: str = ""                                            # 最多的 business_topic
    composition_strategy: str = ""                                      # 使用的组合策略名

    # 来源
    source_type: str = "semantic_widgets"     # 输入来源
    generator: str = "DashboardCompositionPlanner v1.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "version": self.version,
            "widget_count": self.widget_count,
            "section_count": self.section_count,
            "group_count": self.group_count,
            "topic_distribution": self.topic_distribution,
            "dominant_topic": self.dominant_topic,
            "composition_strategy": self.composition_strategy,
            "source_type": self.source_type,
            "generator": self.generator,
        }


# ============================================================
# Dashboard Blueprint —— Composition Planner 最终输出
# ============================================================

@dataclass
class DashboardBlueprint:
    """Dashboard Blueprint——Composition Planner 的唯一输出

    不包含 Grid 信息（x, y, w, h, margin, gap）。
    Layout Engine 后续读取 Blueprint 中的 Section 和 Widget 信息来生成 Grid。

    设计原则：
    - Blueprint 是"内容设计"，Layout Engine 是"排版设计"
    - Blueprint 决定"Dashboard 应该由哪些区域组成"
    - Layout Engine 决定"每个区域在屏幕上占据什么位置"
    """

    # ========== 标识与元数据 ==========
    metadata: BlueprintMetadata = field(default_factory=BlueprintMetadata)

    # ========== 内容组织 ==========
    sections: List[BlueprintSection] = field(default_factory=list)
    groups: List[WidgetGroup] = field(default_factory=list)

    # ========== 关系与组合 ==========
    composition_graph: CompositionGraph = field(default_factory=CompositionGraph)

    # ========== 阅读流 ==========
    reading_flow: ReadingFlow = field(default_factory=ReadingFlow)

    # ========== 信息层级 ==========
    visual_hierarchy: VisualHierarchy = field(default_factory=VisualHierarchy)

    # ========== 预留扩展接口（当前不实现） ==========
    theme: Dict[str, Any] = field(default_factory=dict)
    responsive: Dict[str, Any] = field(default_factory=dict)
    animation: Dict[str, Any] = field(default_factory=dict)
    dark_mode: Dict[str, Any] = field(default_factory=dict)
    mobile: Dict[str, Any] = field(default_factory=dict)

    # ===== 序列化 =====

    def to_dict(self) -> Dict[str, Any]:
        """完整序列化"""
        return {
            "metadata": self.metadata.to_dict(),
            "sections": [s.to_dict() for s in self.sections],
            "groups": [g.to_dict() for g in self.groups],
            "composition_graph": self.composition_graph.to_dict(),
            "reading_flow": self.reading_flow.to_dict(),
            "visual_hierarchy": self.visual_hierarchy.to_dict(),
            "theme": self.theme,
            "responsive": self.responsive,
            "animation": self.animation,
            "dark_mode": self.dark_mode,
            "mobile": self.mobile,
        }

    def get_section_by_role(self, role: BlueprintSectionRole) -> Optional[BlueprintSection]:
        """按角色查找 Section"""
        for sec in self.sections:
            if sec.role == role:
                return sec
        return None

    def get_widget_section(self, widget_id: str) -> Optional[BlueprintSection]:
        """查找 Widget 所在 Section"""
        for sec in self.sections:
            if widget_id in sec.widget_ids:
                return sec
        return None

    def get_widget_group(self, widget_id: str) -> Optional[WidgetGroup]:
        """查找 Widget 所在 Group"""
        for grp in self.groups:
            if widget_id in grp.widget_ids:
                return grp
        return None
