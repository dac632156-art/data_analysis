"""
Dashboard Schema —— Layout Engine 输出数据模型

定义整个 Dashboard 的完整结构：布局、Widget 槽位、分组、交互、元数据。
渲染器（Renderer）的唯一输入。

设计原则：
- 不依赖前端框架（纯数据模型）
- 所有尺寸/位置为抽象网格单位（12 列栅格）
- 预留 Theme / Responsive / Dark Mode 接口
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import uuid
import time


# ============================================================
# 枚举
# ============================================================

class SectionRole(str, Enum):
    HEADER = "header"
    HERO = "hero"
    MAIN = "main"
    SECONDARY = "secondary"
    SIDEBAR = "sidebar"
    FOOTER = "footer"


# ============================================================
# Widget 槽位
# ============================================================

@dataclass
class WidgetSlot:
    """Widget 在 Grid 中的槽位——描述位置和尺寸

    Grid 支持 12 或 24 列栅格系统，行高自适应。
    新版（Blueprint Layout Engine）使用 24 列栅格，提供更精细的布局控制。
    """
    widget_id: str = ""                     # Widget.id
    title: str = ""                         # Widget.title
    description: str = ""                   # Widget.description（图表含义的简短说明）
    widget_type: str = ""                   # chart / kpi / table / map / insight

    # Grid 位置（0-based）
    x: int = 0                              # 起始列
    y: int = 0                              # 起始行
    w: int = 4                              # 列宽
    h: int = 3                              # 行高（行数）

    # 视觉层级
    size_class: str = "medium"              # hero / large / medium / small
    importance_score: int = 50
    visual_weight: int = 50                 # 0-100，用于视觉平衡
    z_index: int = 0                        # 层叠顺序（Renderer 用于堆叠控制）

    # 分组
    section_id: str = ""                    # 所属 Section
    group_id: str = ""                      # 所属 Business Group

    # 数据
    chart_type: Optional[str] = None
    chart_config: Dict[str, Any] = field(default_factory=dict)
    supported_filters: List[Dict[str, str]] = field(default_factory=list)  # [{field, label, filter_type}]

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "title": self.title,
            "description": self.description,
            "widget_type": self.widget_type,
            "position": {"x": self.x, "y": self.y, "w": self.w, "h": self.h},
            "size_class": self.size_class,
            "importance_score": self.importance_score,
            "z_index": self.z_index,
            "section_id": self.section_id,
            "group_id": self.group_id,
            "chart_type": self.chart_type,
            "chart_config": self.chart_config,
            "supported_filters": [
                {"field": f.get("field", f) if isinstance(f, dict) else f,
                 "label": f.get("label", f) if isinstance(f, dict) else f,
                 "filter_type": f.get("filter_type", "dropdown") if isinstance(f, dict) else "dropdown"}
                for f in self.supported_filters
            ],
            "metadata": self.metadata,
        }


# ============================================================
# Section / Business Group
# ============================================================

@dataclass
class DashboardSection:
    """Dashboard 分区"""
    id: str = ""
    role: SectionRole = SectionRole.MAIN
    title: str = ""
    y_start: int = 0
    y_end: int = 0
    widget_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role.value,
            "title": self.title,
            "y_start": self.y_start,
            "y_end": self.y_end,
            "widget_ids": self.widget_ids,
        }


@dataclass
class BusinessGroup:
    """业务主题分组"""
    id: str = ""
    topic: str = ""                         # "销售增长" / "区域分析" / "产品排名"
    widget_ids: List[str] = field(default_factory=list)
    importance: int = 0                     # 分组综合重要性（组内 Widget score 均值）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "widget_ids": self.widget_ids,
            "importance": self.importance,
        }


# ============================================================
# Layout 配置
# ============================================================

@dataclass
class LayoutConfig:
    """单次 Dashboard 的布局配置（从 Layout Library 加载）"""
    name: str = ""                          # "executive" / "wide" / "compact" / "geo"
    columns: int = 12                       # 栅格列数
    section_order: List[str] = field(default_factory=list)  # section 顺序
    hero_cols: int = 0                      # Hero 区占的列数（0=自适应）

    # Widget 尺寸映射：WidgetSize → (w, h)
    size_grid: Dict[str, tuple] = field(default_factory=dict)

    # 间距
    section_gap: int = 2                    # Section 间距（行）
    widget_gap: int = 0                     # Widget 内边距（行）
    page_margin: int = 1                    # 页面边距（行）

    # 平衡
    max_section_weight: int = 24            # 单个 Section 最大视觉重量（左右平衡用，12 列 × 2）
    rebalance_enabled: bool = True          # 是否启用视觉平衡
    fill_rows: bool = True                  # 行内补满：每行列宽和=columns，无空洞（默认开启）

    # 交互
    default_filter: Optional[str] = None    # 默认全局筛选器
    cross_filter_groups: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LayoutConfig":
        size_grid = {}
        for k, v in data.get("size_grid", {}).items():
            size_grid[k] = tuple(v) if isinstance(v, list) else v
        return cls(
            name=data.get("name", ""),
            columns=data.get("columns", 12),
            section_order=data.get("section_order", []),
            hero_cols=data.get("hero_cols", 0),
            size_grid=size_grid,
            section_gap=data.get("section_gap", 2),
            widget_gap=data.get("widget_gap", 0),
            page_margin=data.get("page_margin", 1),
            max_section_weight=data.get("max_section_weight", 24),
            rebalance_enabled=data.get("rebalance_enabled", True),
            fill_rows=data.get("fill_rows", True),
            default_filter=data.get("default_filter"),
            cross_filter_groups=data.get("cross_filter_groups", []),
        )


# ============================================================
# Dashboard Schema（最终输出）
# ============================================================

@dataclass
class DashboardSchema:
    """完整的 Dashboard Schema——Renderer 唯一输入

    v2.0 支持 Blueprint Layout Engine 输出（24列栅格 + strategy + blueprint_id）。
    """

    # ========== 标识 ==========
    id: str = ""
    title: str = "数据分析驾驶舱"
    created_at: str = ""
    version: str = "2.0"

    # ========== 元数据 ==========
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ========== Blueprint 引用 ==========
    blueprint_id: str = ""                     # 来源 Blueprint ID（Blueprint Layout Engine 生成时填写）

    # ========== 布局 ==========
    layout: LayoutConfig = field(default_factory=LayoutConfig)
    layout_strategy: str = ""                  # 布局策略名（executive/sales/compact/wide 等）

    # ========== Widget 槽位 ==========
    widgets: List[WidgetSlot] = field(default_factory=list)

    # ========== 分区 ==========
    sections: List[DashboardSection] = field(default_factory=list)

    # ========== 业务分组 ==========
    groups: List[BusinessGroup] = field(default_factory=list)

    # ========== 交互 ==========
    interactions: Dict[str, Any] = field(default_factory=dict)

    # ========== 预留扩展 ==========
    theme: Dict[str, Any] = field(default_factory=dict)
    responsive: Dict[str, Any] = field(default_factory=dict)
    dark_mode: bool = False
    mobile: Dict[str, Any] = field(default_factory=dict)

    # ===== 便捷方法 =====

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "version": self.version,
            "metadata": self.metadata,
            "blueprint_id": self.blueprint_id,
            "layout": {
                "strategy": self.layout_strategy,
                "grid": str(self.layout.columns),
                "name": self.layout.name,
                "columns": self.layout.columns,
                "section_order": self.layout.section_order,
                "section_gap": self.layout.section_gap,
                "widget_gap": self.layout.widget_gap,
                "page_margin": self.layout.page_margin,
            },
            "widgets": [w.to_dict() for w in self.widgets],
            "sections": [s.to_dict() for s in self.sections],
            "groups": [g.to_dict() for g in self.groups],
            "interactions": self.interactions,
            "theme": self.theme,
            "responsive": self.responsive,
            "dark_mode": self.dark_mode,
            "mobile": self.mobile,
        }

    def get_widgets_by_section(self, role: SectionRole) -> List[WidgetSlot]:
        section_ids = {s.id for s in self.sections if s.role == role}
        return [w for w in self.widgets if w.section_id in section_ids]

    def get_widgets_by_group(self, topic: str) -> List[WidgetSlot]:
        group_ids = {g.id for g in self.groups if g.topic == topic}
        return [w for w in self.widgets if w.group_id in group_ids]

    def get_hero_widgets(self) -> List[WidgetSlot]:
        return self.get_widgets_by_section(SectionRole.HERO)

    def merge_interactions(self, ischema) -> DashboardSchema:
        """将完整的 InteractionSchema 合并到 DashboardSchema.interactions

        替换 Layout Engine 生成的轻量交互为 Interaction Engine 的完整规则。
        这样 Renderer 能消费到 cross_filters / drill_downs / highlights。
        """
        self.interactions = ischema.to_dict()
        return self
