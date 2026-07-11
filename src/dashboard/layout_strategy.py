"""
Layout Strategy Selection —— 布局策略选择引擎（Strategy Pattern）

核心职责：
- 根据 Dashboard Blueprint 的 composition_strategy、widget 分布、section 结构
- 自动选择最佳 Layout Strategy
- 定义每种策略的布局风格参数

设计原则：
- 不使用 if-else 选择策略
- 采用 Strategy Pattern + Rule Engine
- 新增策略只需添加 LayoutStrategy 配置 + 选择规则
- 策略定义只包含"布局风格"，不包含具体坐标

每种 Layout Strategy 定义：
- grid_columns: 栅格列数
- hero_layout: Hero Widget 的布局方式
- major_layout: Major Widget 的布局方式
- minor_layout: Minor Widget 的布局方式
- section_gap, widget_gap, page_margin
- visual_balance_mode: 视觉平衡模式

生产方：LayoutStrategySelector
消费方：DashboardLayoutEngine
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field

from src.dashboard.composition_schema import (
    DashboardBlueprint, BlueprintSectionRole,
)


# ============================================================
# Layout Strategy —— 布局策略数据模型
# ============================================================

@dataclass
class LayoutStrategy:
    """Dashboard 布局策略——声明式配置，定义布局风格

    不包含具体坐标（x/y/w/h），只定义布局风格参数。
    具体坐标由 Grid System + Widget Placement 计算。
    """
    name: str = ""                                  # 策略名称："executive" / "sales" / "compact"
    display_name: str = ""                           # 显示名称："高管布局" / "销售布局"
    description: str = ""                            # 策略描述

    # 匹配条件（用于自动选择）
    match_composition_strategies: List[str] = field(default_factory=list)  # 匹配的组合策略名
    match_section_roles: List[str] = field(default_factory=list)           # 匹配的 section 角色

    # Grid 系统
    grid_columns: int = 24                          # 栅格列数（新版 24 列）
    page_margin: int = 1                            # 页面边距（行）
    section_gap: int = 2                            # Section 间距（行）
    widget_gap: int = 1                             # Widget 间距（行）
    card_padding: int = 0                           # 卡片内边距（行，预留）

    # Hero 布局规则
    hero_width_percent: float = 1.0                 # Hero 占满一行（1.0 = 100%）
    hero_height: int = 5                            # Hero 行高（行数）
    hero_max_count: int = 2                         # Hero 最多几个（超过的降级为 Major）

    # Major 布局规则
    major_width_percent: float = 0.5                # Major 占半行（0.5 = 50%）
    major_height: int = 4                           # Major 行高
    major_per_row: int = 2                          # 每行放几个 Major Widget

    # Minor 布局规则
    minor_width_percent: float = 0.33               # Minor 占 1/3 行
    minor_height: int = 3                           # Minor 行高
    minor_per_row: int = 3                          # 每行放几个 Minor Widget

    # 视觉平衡
    visual_balance_mode: str = "auto"               # auto / left_heavy / center / balanced
    rebalance_enabled: bool = True                  # 是否启用视觉平衡调整

    # Section 布局风格
    section_layout_mode: str = "stacked"            # stacked（竖向堆叠） / mixed（混合布局）

    # 预留扩展
    responsive: Dict[str, Any] = field(default_factory=dict)  # desktop/tablet/mobile 参数
    theme: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# Predefined Layout Strategies —— 预定义布局策略
# ============================================================

LAYOUT_STRATEGIES: Dict[str, LayoutStrategy] = {
    # ===== 高管布局（Hero 优先） =====
    "executive": LayoutStrategy(
        name="executive",
        display_name="高管布局",
        description="管理层驾驶舱布局——Hero 占满全行，Major 左右对称，Minor 自动填充",
        match_composition_strategies=["executive"],
        match_section_roles=["overview", "main_analysis", "comparison"],
        grid_columns=24,
        hero_width_percent=1.0,
        hero_height=5,
        hero_max_count=2,
        major_width_percent=0.5,
        major_height=4,
        major_per_row=2,
        minor_width_percent=0.33,
        minor_height=3,
        minor_per_row=3,
        visual_balance_mode="balanced",
        section_layout_mode="mixed",
        responsive={
            "desktop": {"columns": 24, "mode": "grid"},
            "tablet": {"columns": 12, "mode": "grid"},
            "mobile": {"columns": 1, "mode": "stacked"},
        },
    ),

    # ===== 销售布局（趋势优先 + 排名 + 比较） =====
    "sales": LayoutStrategy(
        name="sales",
        display_name="销售布局",
        description="销售看板布局——趋势占宽幅，排名+比较左右分列",
        match_composition_strategies=["sales"],
        match_section_roles=["overview", "main_analysis", "ranking", "comparison"],
        grid_columns=24,
        hero_width_percent=1.0,
        hero_height=5,
        hero_max_count=2,
        major_width_percent=0.5,
        major_height=4,
        major_per_row=2,
        minor_width_percent=0.25,
        minor_height=3,
        minor_per_row=4,
        visual_balance_mode="left_heavy",
        section_layout_mode="mixed",
        responsive={
            "desktop": {"columns": 24, "mode": "grid"},
            "tablet": {"columns": 12, "mode": "grid"},
            "mobile": {"columns": 1, "mode": "stacked"},
        },
    ),

    # ===== 财务布局（结构占比优先） =====
    "finance": LayoutStrategy(
        name="finance",
        display_name="财务布局",
        description="财务看板布局——核心指标+趋势占大幅，成本/利润占比左右分列",
        match_composition_strategies=["finance"],
        match_section_roles=["overview", "main_analysis", "comparison", "distribution"],
        grid_columns=24,
        hero_width_percent=1.0,
        hero_height=5,
        hero_max_count=1,
        major_width_percent=0.5,
        major_height=4,
        major_per_row=2,
        minor_width_percent=0.33,
        minor_height=3,
        minor_per_row=3,
        visual_balance_mode="balanced",
        section_layout_mode="mixed",
    ),

    # ===== 紧凑布局（Widget 数少） =====
    "compact": LayoutStrategy(
        name="compact",
        display_name="紧凑布局",
        description="Widget 数量较少时——保持留白，不强行填满",
        match_composition_strategies=["general"],
        match_section_roles=["overview", "main_analysis"],
        grid_columns=24,
        hero_width_percent=1.0,
        hero_height=5,
        hero_max_count=1,
        major_width_percent=0.5,
        major_height=4,
        major_per_row=2,
        minor_width_percent=0.5,
        minor_height=3,
        minor_per_row=2,
        visual_balance_mode="center",
        section_layout_mode="stacked",
    ),

    # ===== 宽幅布局（趋势为主） =====
    "wide": LayoutStrategy(
        name="wide",
        display_name="宽幅布局",
        description="趋势/折线图为主的布局——趋势图占全宽，其他图表左右分布",
        match_composition_strategies=["executive", "sales"],
        match_section_roles=["overview", "main_analysis"],
        grid_columns=24,
        hero_width_percent=1.0,
        hero_height=6,
        hero_max_count=1,
        major_width_percent=0.667,
        major_height=4,
        major_per_row=2,
        minor_width_percent=0.333,
        minor_height=3,
        minor_per_row=3,
        visual_balance_mode="balanced",
        section_layout_mode="mixed",
    ),

    # ===== 地理布局（地图优先） =====
    "geo": LayoutStrategy(
        name="geo",
        display_name="地理布局",
        description="有地图 Widget 时——地图占大幅，辅助图表左右分列",
        match_composition_strategies=["executive", "sales"],
        match_section_roles=["overview", "main_analysis", "geographic"],
        grid_columns=24,
        hero_width_percent=1.0,
        hero_height=5,
        hero_max_count=1,
        major_width_percent=0.667,
        major_height=5,
        major_per_row=2,
        minor_width_percent=0.333,
        minor_height=3,
        minor_per_row=3,
        visual_balance_mode="left_heavy",
        section_layout_mode="mixed",
    ),

    # ===== 运营布局（监控优先） =====
    "operation": LayoutStrategy(
        name="operation",
        display_name="运营布局",
        description="运营看板布局——监控/效率指标突出，排名+异常左右分列",
        match_composition_strategies=["operation", "risk"],
        match_section_roles=["overview", "main_analysis", "ranking", "monitoring"],
        grid_columns=24,
        hero_width_percent=1.0,
        hero_height=5,
        hero_max_count=2,
        major_width_percent=0.5,
        major_height=4,
        major_per_row=2,
        minor_width_percent=0.25,
        minor_height=3,
        minor_per_row=4,
        visual_balance_mode="balanced",
        section_layout_mode="mixed",
    ),

    # ===== 通用布局（默认 fallback） =====
    "general": LayoutStrategy(
        name="general",
        display_name="通用布局",
        description="通用分析布局——Hero 全行，Major 左右，Minor 三列",
        match_composition_strategies=["general"],
        match_section_roles=["overview", "main_analysis", "comparison", "detail"],
        grid_columns=24,
        hero_width_percent=1.0,
        hero_height=5,
        hero_max_count=2,
        major_width_percent=0.5,
        major_height=4,
        major_per_row=2,
        minor_width_percent=0.33,
        minor_height=3,
        minor_per_row=3,
        visual_balance_mode="auto",
        section_layout_mode="stacked",
    ),
}

DEFAULT_LAYOUT_STRATEGY = LAYOUT_STRATEGIES["general"]


# ============================================================
# Layout Strategy Selector —— 布局策略选择器（Rule Engine）
# ============================================================

class LayoutStrategySelector:
    """布局策略选择器——根据 Blueprint 自动选择最佳 Layout Strategy

    使用 Rule Engine：
    - 每条规则是一个 (条件函数, 策略名) 元组
    - 按优先级评估，首次命中即返回
    - 新增策略只需添加规则，无需修改选择器代码
    """

    def __init__(self):
        self._rules: List[Tuple[Callable, str]] = []
        self._register_default_rules()

    def _register_default_rules(self):
        """注册默认选择规则（策略模式）"""
        self._rules = [
            # Rule 1: 有地理 Widget → geo
            (self._has_geographic_section, "geo"),
            # Rule 2: operation/risk 组合策略 → operation
            (self._is_operation_blueprint, "operation"),
            # Rule 3: finance 组合策略 → finance
            (self._is_finance_blueprint, "finance"),
            # Rule 4: sales 组合策略 → sales
            (self._is_sales_blueprint, "sales"),
            # Rule 5: executive 组合策略 → executive
            (self._is_executive_blueprint, "executive"),
            # Rule 6: Widget 很少 → compact
            (self._is_compact_blueprint, "compact"),
            # Rule 7: 大量 trend Widget → wide
            (self._is_wide_blueprint, "wide"),
        ]

    def select(self, blueprint: DashboardBlueprint) -> LayoutStrategy:
        """根据 Blueprint 选择最佳 Layout Strategy

        Args:
            blueprint: DashboardBlueprint

        Returns:
            LayoutStrategy
        """
        # 按规则依次评估
        for condition, strategy_name in self._rules:
            if condition(blueprint):
                return LAYOUT_STRATEGIES.get(strategy_name, DEFAULT_LAYOUT_STRATEGY)

        # Fallback: 根据 composition_strategy 匹配
        composition = blueprint.metadata.composition_strategy
        for name, strategy in LAYOUT_STRATEGIES.items():
            if composition in strategy.match_composition_strategies:
                return strategy

        # Default
        return DEFAULT_LAYOUT_STRATEGY

    # ===== 规则条件函数 =====

    @staticmethod
    def _has_geographic_section(blueprint: DashboardBlueprint) -> bool:
        """有地理 Section"""
        for sec in blueprint.sections:
            if sec.role == BlueprintSectionRole.GEOGRAPHIC:
                return True
        return False

    @staticmethod
    def _is_operation_blueprint(blueprint: DashboardBlueprint) -> bool:
        """operation/risk 组合策略"""
        return blueprint.metadata.composition_strategy in ("operation", "risk")

    @staticmethod
    def _is_finance_blueprint(blueprint: DashboardBlueprint) -> bool:
        """finance 组合策略"""
        return blueprint.metadata.composition_strategy == "finance"

    @staticmethod
    def _is_sales_blueprint(blueprint: DashboardBlueprint) -> bool:
        """sales 组合策略"""
        return blueprint.metadata.composition_strategy == "sales"

    @staticmethod
    def _is_executive_blueprint(blueprint: DashboardBlueprint) -> bool:
        """executive 组合策略"""
        return blueprint.metadata.composition_strategy == "executive"

    @staticmethod
    def _is_compact_blueprint(blueprint: DashboardBlueprint) -> bool:
        """Widget 数量 ≤ 3 → compact"""
        return blueprint.metadata.widget_count <= 3

    @staticmethod
    def _is_wide_blueprint(blueprint: DashboardBlueprint) -> bool:
        """大量 trend Widget → wide"""
        from src.dashboard.semantic_models import VisualRole
        # 需要从 blueprint 的 visual hierarchy 检查
        # 简化：检查 main_analysis section 的 dominant_visual_role
        for sec in blueprint.sections:
            if sec.role == BlueprintSectionRole.MAIN_ANALYSIS:
                if sec.dominant_visual_role in ("primary_trend", "overview_metric"):
                    return True
        return False

    def add_rule(self, condition: Callable, strategy_name: str):
        """扩展：添加自定义选择规则"""
        self._rules.append((condition, strategy_name))
