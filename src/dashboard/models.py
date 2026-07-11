"""
Widget Domain Model —— 标准化 Business Widget 数据结构

Widget 是全系统唯一的"可视化大屏组件"数据契约。
消费方：前端 Dashboard / AI 大屏渲染引擎
生产方：WidgetGenerator（唯一入口，通过 FindingFactory 保证一致性）
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import uuid


# ============================================================
# Widget 类型枚举
# ============================================================

class WidgetType(str, Enum):
    """Widget 可视化类型——决定前端渲染方式"""
    CHART = "chart"         # 图表（ECharts）
    KPI = "kpi"             # 指标卡片
    TABLE = "table"         # 数据表格
    MAP = "map"             # 地图
    INSIGHT = "insight"     # 洞察卡片
    SUMMARY = "summary"     # 摘要卡片


class WidgetSize(str, Enum):
    """Widget 尺寸——决定大屏布局网格占用"""
    HERO = "hero"           # 全宽（占 2 行 × 2 列）
    LARGE = "large"         # 大半格（1 行 × 1 列，突出显示）
    MEDIUM = "medium"       # 标准格（1 行 × 1 列）
    SMALL = "small"         # 小格（1 行 × 半列，侧边栏）


class DisplayRole(str, Enum):
    """Widget 在 Dashboard 中的展示角色"""
    MAIN = "main"           # 主展示区（核心图表）
    SECONDARY = "secondary" # 辅助展示区
    SIDEBAR = "sidebar"     # 侧边栏
    FOOTER = "footer"       # 底部栏


# ============================================================
# Filter 配置
# ============================================================

@dataclass
class WidgetFilter:
    """Widget 支持的筛选器定义"""
    field: str = ""                     # 筛选字段名："time" / "region" / "product"
    label: str = ""                     # 显示标签："时间" / "地区" / "产品"
    filter_type: str = ""               # 筛选类型："dropdown" / "date_range" / "checkbox"


# ============================================================
# Data Source 配置
# ============================================================

@dataclass
class WidgetDataSource:
    """Widget 数据来源引用——不持有原始数据，只保存引用标识"""
    package_id: str = ""                # AnalysisPackage.id
    finding_ids: List[str] = field(default_factory=list)  # 关联的 BusinessFinding.id
    chart_slot: str = ""                # 关联的 ChartData.slot
    table_title: str = ""               # 关联的 TableData.title
    kpi_label: str = ""                 # 关联的 KPIItem.label


# ============================================================
# Widget Domain Model
# ============================================================

@dataclass
class Widget:
    """标准化 Business Widget——可视化大屏的最小组成单元

    唯一输入来源：AnalysisPackage。
    生产方：WidgetGenerator.generate()。
    消费方：前端 Dashboard 渲染引擎 / AI 大屏自动生成。
    """

    # ========== 标识 ==========
    id: str = ""                                    # 唯一标识（UUID）
    title: str = ""                                 # Widget 标题："销售增长趋势"
    description: str = ""                           # 简短描述（2 句话以内）
    widget_type: WidgetType = WidgetType.CHART      # Widget 类型

    # ========== 业务信息（从 AnalysisPackage 提取） ==========
    analysis_type: str = ""                         # "growth" / "ranking" / "geo" / ...
    business_topic: str = ""                        # 业务主题："销售增长" / "客户留存" / ...
    finding_summary: str = ""                       # 核心发现一句话摘要
    importance_score: int = 50                      # 重要性评分 0-100

    # ========== 可视化信息 ==========
    chart_type: Optional[str] = None                # "line" / "bar" / "pie" / "map" / None
    chart_config: Dict[str, Any] = field(default_factory=dict)  # 前端可直接消费的图表配置
    data_source: WidgetDataSource = field(default_factory=WidgetDataSource)

    # ========== 布局信息（自动推断） ==========
    preferred_size: WidgetSize = WidgetSize.MEDIUM  # 推荐尺寸
    priority: int = 1                               # 排序优先级 1-10
    display_role: DisplayRole = DisplayRole.SECONDARY

    # ========== 交互信息 ==========
    supported_filters: List[WidgetFilter] = field(default_factory=list)  # 支持的筛选器
    drill_down: bool = False                        # 是否支持下钻
    cross_filter: bool = False                      # 是否支持交叉筛选

    # ========== 元数据 ==========
    metadata: Dict[str, Any] = field(default_factory=dict)  # 扩展元数据
    _raw_package_ref: Optional[str] = None           # 内部引用：AnalysisPackage.id（不序列化）

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]

    # ===== 便捷方法 =====

    def to_dict(self) -> Dict[str, Any]:
        """序列化为前端消费的字典"""
        import dataclasses
        d = dataclasses.asdict(self)
        d["widget_type"] = self.widget_type.value
        d["preferred_size"] = self.preferred_size.value
        d["display_role"] = self.display_role.value
        d["supported_filters"] = [
            {"field": f.field, "label": f.label, "filter_type": f.filter_type}
            for f in self.supported_filters
        ]
        d.pop("_raw_package_ref", None)
        return d

    def to_api_dict(self) -> Dict[str, Any]:
        """API 响应格式（与 to_dict 相同，提供语义化别名）"""
        return self.to_dict()
