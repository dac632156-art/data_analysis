"""
Dashboard Layout Engine —— Widget[] → Dashboard Schema

布局引擎的职责不是简单的 Grid 排版，而是根据 Widget 的业务信息、
重要性、图表类型、视觉层级，自动设计整个 Dashboard。

设计原则：
- 不读取 DataFrame
- 不重新分析数据
- 策略模式：Layout Selection 通过规则引擎而非 if-else
- 所有布局配置来自 Layout Library (YAML)
- Grid 为 12 列栅格系统
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
import os
import uuid
import time
import yaml
import math

from src.dashboard.layout_schema import (
    DashboardSchema, LayoutConfig,
    WidgetSlot, DashboardSection, BusinessGroup,
    SectionRole,
)


# ============================================================
# Layout Library 加载
# ============================================================

def _load_layout_yaml(name: str) -> Dict[str, Any]:
    """加载指定名称的 YAML 布局配置"""
    layouts_dir = os.path.join(os.path.dirname(__file__), "layouts")
    filepath = os.path.join(layouts_dir, f"{name}.yaml")
    if not os.path.isfile(filepath):
        # fallback: executive
        filepath = os.path.join(layouts_dir, "executive.yaml")
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _list_available_layouts() -> List[str]:
    """列出所有可用的布局名称"""
    layouts_dir = os.path.join(os.path.dirname(__file__), "layouts")
    if not os.path.isdir(layouts_dir):
        return ["executive"]
    return sorted([
        os.path.splitext(f)[0]
        for f in os.listdir(layouts_dir)
        if f.endswith(".yaml")
    ])


# ============================================================
# Business Grouper —— 业务主题分组
# ============================================================

class BusinessGrouper:
    """自动按 business_topic 对 Widget 分组

    不做新模块，作为 Layout Engine 内部步骤。
    """

    # 预定义分组关键词（topic → 分组名）
    TOPIC_GROUPS: Dict[str, List[str]] = {
        "销售分析": ["销售", "增长", "营收", "收入", "profit", "sales"],
        "区域分析": ["区域", "地区", "省份", "城市", "geo", "地图", "地理"],
        "产品分析": ["产品", "商品", "排名", "top", "集中度", "占比"],
        "客户分析": ["客户", "留存", "复购", "用户", "customer", "retention"],
        "风险预警": ["异常", "风险", "anomaly", "预警", "下降", "decline"],
        "指标总览": ["kpi", "指标", "总览", "核心", "概览", "summary"],
    }

    def group(self, widgets: List[Dict[str, Any]]) -> List[BusinessGroup]:
        """对 Widget 列表进行业务主题分组

        Args:
            widgets: Widget dict 列表（含 business_topic, id, importance_score）

        Returns:
            BusinessGroup 列表（按 importance 降序）
        """
        groups: Dict[str, BusinessGroup] = {}

        for w in widgets:
            topic = _normalize_topic(w.get("business_topic", ""))
            if not topic:
                topic = "综合分析"

            if topic not in groups:
                groups[topic] = BusinessGroup(
                    id=f"group_{topic}",
                    topic=topic,
                    widget_ids=[],
                    importance=0,
                )

            wid = w.get("id", "")
            if wid:
                groups[topic].widget_ids.append(wid)
                groups[topic].importance += w.get("importance_score", 50)

        # 计算均值 importance
        for g in groups.values():
            if g.widget_ids:
                g.importance = round(g.importance / len(g.widget_ids))

        # 按 importance 降序排列
        result = sorted(groups.values(), key=lambda g: g.importance, reverse=True)
        return result


def _normalize_topic(raw: str) -> str:
    """规范化 business_topic → 标准分组名"""
    raw_lower = raw.lower()
    for group_name, keywords in BusinessGrouper.TOPIC_GROUPS.items():
        for kw in keywords:
            if kw.lower() in raw_lower:
                return group_name
    # 没有匹配 → 原样首字母大写
    return raw


# ============================================================
# Layout Selector —— 策略规则引擎（非 if-else）
# ============================================================

class LayoutSelector:
    """规则驱动的布局选择器

    每条规则是一个 (条件函数, 布局名) 元组。
    按优先级评估，首次命中即返回。
    新增布局只需添加规则，无需修改选择器代码。
    """

    def __init__(self):
        self._rules: List[Tuple[callable, str]] = []
        self._register_default_rules()

    def _register_default_rules(self):
        """注册默认选择规则（策略模式）"""
        self._rules = [
            # 规则 1: 有地图 → geo
            (self._has_geo_widgets, "geo"),
            # 规则 2: KPI 类型占比高 → compact
            (self._has_many_kpis, "compact"),
            # 规则 3: 趋势/折线图多 → wide
            (self._has_many_line_charts, "wide"),
            # 规则 4: Hero widget 多 → executive
            (self._has_hero_widgets, "executive"),
        ]

    def select(self, widgets: List[Dict[str, Any]], groups: List[BusinessGroup]) -> str:
        """选择最佳布局

        Args:
            widgets: Widget dict 列表
            groups: 业务分组列表

        Returns:
            布局名称（如 "executive" / "wide" / "compact" / "geo"）
        """
        # 按规则依次评估
        for condition, layout_name in self._rules:
            if condition(widgets, groups):
                return layout_name

        # 默认：根据 widget 数量
        if len(widgets) >= 8:
            return "wide"
        elif len(widgets) <= 3:
            return "compact"
        return "executive"

    # ===== 规则条件函数 =====

    @staticmethod
    def _has_geo_widgets(widgets: List[Dict[str, Any]], _) -> bool:
        for w in widgets:
            ct = w.get("chart_type", "") or ""
            if ct in ("map", "map_3d"):
                return True
            if "geo" in str(w.get("analysis_type", "")).lower():
                return True
        return False

    @staticmethod
    def _has_many_kpis(widgets: List[Dict[str, Any]], _) -> bool:
        kpi_count = sum(1 for w in widgets if w.get("widget_type") == "kpi")
        return kpi_count >= len(widgets) * 0.4

    @staticmethod
    def _has_many_line_charts(widgets: List[Dict[str, Any]], _) -> bool:
        line_count = sum(1 for w in widgets if w.get("chart_type") == "line")
        return line_count >= len(widgets) * 0.3

    @staticmethod
    def _has_hero_widgets(widgets: List[Dict[str, Any]], _) -> bool:
        hero_count = sum(1 for w in widgets if w.get("preferred_size") == "hero")
        return hero_count >= 1

    def add_rule(self, condition: callable, layout_name: str):
        """扩展：添加自定义选择规则"""
        self._rules.append((condition, layout_name))


# ============================================================
# Grid Allocator —— 自动分配 Grid 位置
# ============================================================

class GridAllocator:
    """自动将 Widget 分配为 Grid 槽位

    输入：Widget 列表 + LayoutConfig
    输出：WidgetSlot 列表（带 x, y, w, h）
    """

    def allocate(
        self,
        widgets: List[Dict[str, Any]],
        config: LayoutConfig,
        groups: List[BusinessGroup],
    ) -> List[WidgetSlot]:
        """执行 Grid 分配"""
        # 1. 排序：先按 importance 降序，同分按业务分组
        sorted_widgets = self._sort_by_priority(widgets, groups)

        # 2. 计算 size
        sized = [self._compute_size(w, config) for w in sorted_widgets]

        # 3. 分配 section
        sectioned = self._assign_sections(sized, config)

        # 4. 分配 Grid 坐标
        slots = self._assign_grid(sectioned, config)

        # 5. 视觉平衡调整
        if config.rebalance_enabled:
            slots = self._rebalance(slots, config)

        return slots

    # ===== 排序 =====

    @staticmethod
    def _sort_by_priority(
        widgets: List[Dict[str, Any]],
        groups: List[BusinessGroup],
    ) -> List[Dict[str, Any]]:
        """按 importance 降序排列

        同分时：同组排在一起（保持业务主题内聚）
        """
        # 构建 topic → importance 映射
        group_importance: Dict[str, int] = {g.topic: g.importance for g in groups}

        def sort_key(w):
            score = w.get("importance_score", 50)
            topic = _normalize_topic(w.get("business_topic", ""))
            group_score = group_importance.get(topic, 0)
            return (-score, -group_score)

        return sorted(widgets, key=sort_key)

    # ===== Size 计算 =====

    @staticmethod
    def _compute_size(
        widget: Dict[str, Any],
        config: LayoutConfig,
    ) -> Dict[str, Any]:
        """根据 preferred_size 查 Layout 配置计算 (w, h)"""
        size_class = widget.get("preferred_size", "medium")
        w, h = config.size_grid.get(size_class, (4, 3))
        widget["_grid_w"] = w
        widget["_grid_h"] = h
        widget["_size_class"] = size_class
        return widget

    # ===== Section 分配 =====

    @staticmethod
    def _assign_sections(
        widgets: List[Dict[str, Any]],
        config: LayoutConfig,
    ) -> List[Dict[str, Any]]:
        """为每个 Widget 分配 section_id

        Hero → score ≥ 90 的第一个 widget (最多 hero_cols / hero_w 个)
        Main  → score ≥ 60 或 display_role == main
        Secondary → 其他
        """
        hero_max = 1  # 默认最多 1 个 hero
        hero_count = 0
        hero_w = config.size_grid.get("hero", [12, 4])[0]

        for w in widgets:
            score = w.get("importance_score", 50)
            role = w.get("display_role", "secondary")
            size_class = w.get("_size_class", "medium")

            if score >= 90 and hero_count < hero_max and size_class == "hero":
                w["_section"] = "hero"
                hero_count += 1
            elif score >= 60 or role == "main":
                w["_section"] = "main"
            else:
                w["_section"] = "secondary"

        return widgets

    # ===== Grid 坐标分配 =====

    @staticmethod
    def _assign_grid(
        widgets: List[Dict[str, Any]],
        config: LayoutConfig,
    ) -> List[WidgetSlot]:
        """按 section 分组后，逐行分配 (x, y)"""
        slots: List[WidgetSlot] = []
        current_y = config.page_margin  # 顶部留白

        # 按 section_order 处理
        for section_name in config.section_order:
            sec_widgets = [w for w in widgets if w.get("_section") == section_name]
            if not sec_widgets:
                continue

            for w in sec_widgets:
                w["_y_start"] = current_y

            sec_slots, next_y = GridAllocator._layout_section(
                sec_widgets, config, current_y, section_name
            )
            slots.extend(sec_slots)
            current_y = next_y + config.section_gap

        return slots

    @staticmethod
    def _layout_section(
        section_widgets: List[Dict[str, Any]],
        config: LayoutConfig,
        start_y: int,
        section_name: str = "",
    ) -> Tuple[List[WidgetSlot], int]:
        """为单个 section 分配 Grid

        贪心逐行填充，每行累加 x，x + w > columns 则换行。
        """
        slots: List[WidgetSlot] = []
        x = 0
        y = start_y
        max_h_in_row = 0

        for w in section_widgets:
            gw = w.get("_grid_w", 4)
            gh = w.get("_grid_h", 3)

            # 换行判断
            if x + gw > config.columns and x > 0:
                x = 0
                y += max_h_in_row + config.widget_gap
                max_h_in_row = 0

            # 确保不超列数
            if gw > config.columns:
                gw = config.columns

            # 创建 Slot
            group_topic = _normalize_topic(w.get("business_topic", ""))
            slot = WidgetSlot(
                widget_id=w.get("id", ""),
                title=w.get("title", ""),
                widget_type=str(w.get("widget_type", "chart")),
                x=x,
                y=y,
                w=gw,
                h=gh,
                size_class=w.get("_size_class", "medium"),
                importance_score=w.get("importance_score", 50),
                visual_weight=w.get("importance_score", 50),
                group_id=f"group_{group_topic}",
                section_id=section_name,  # ★ 修复：写入 section_id，让前端 GridRenderer 能正确分组
                chart_type=w.get("chart_type"),
                chart_config=w.get("chart_config", {}),
                supported_filters=[
                    f if isinstance(f, dict) else {"field": str(f), "label": str(f), "filter_type": "dropdown"}
                    for f in w.get("supported_filters", [])
                ],
                metadata={
                    "analysis_type": w.get("analysis_type", ""),
                    "business_topic": w.get("business_topic", ""),
                },
            )
            slots.append(slot)

            x += gw
            if gh > max_h_in_row:
                max_h_in_row = gh

        if max_h_in_row == 0:
            max_h_in_row = 3
        y += max_h_in_row

        return slots, y

    # ===== 视觉平衡 =====

    @staticmethod
    def _rebalance(slots: List[WidgetSlot], config: LayoutConfig) -> List[WidgetSlot]:
        """视觉平衡调整

        目标：左右两侧视觉重量相近。
        策略：检查每行 x=0 ~ x=5 和 x=6 ~ x=11 的 visual_weight 之和，
        如果左侧 > 右侧 * 1.5，将最重的 widget 移到右侧。
        """
        # 按 y 分组
        rows: Dict[int, List[WidgetSlot]] = {}
        for s in slots:
            y = s.y
            if y not in rows:
                rows[y] = []
            rows[y].append(s)

        for y, row_slots in rows.items():
            left_weight = sum(s.visual_weight for s in row_slots if s.x < config.columns // 2)
            right_weight = sum(s.visual_weight for s in row_slots if s.x >= config.columns // 2)

            # 左侧过重 → 将最重的 widget 右移
            if left_weight > right_weight * 1.5 and len(row_slots) >= 2:
                row_slots.sort(key=lambda s: s.visual_weight, reverse=True)
                heaviest = row_slots[0]
                if heaviest.x < config.columns // 2:
                    # 移到右半侧
                    rightmost_x = max((s.x + s.w for s in row_slots if s.x >= config.columns // 2), default=config.columns // 2)
                    if rightmost_x + heaviest.w <= config.columns:
                        heaviest.x = rightmost_x

        return slots


# ============================================================
# Layout Engine 主编排器
# ============================================================

class LayoutEngine:
    """Dashboard Layout Engine —— Widget[] → DashboardSchema

    使用方式：
        engine = LayoutEngine()
        schema = engine.build(widgets, title="我的驾驶舱")
    """

    def __init__(self):
        self._grouper = BusinessGrouper()
        self._selector = LayoutSelector()
        self._allocator = GridAllocator()

    def build(
        self,
        widgets: List[Dict[str, Any]],
        title: str = "数据分析驾驶舱",
        layout_name: Optional[str] = None,
    ) -> DashboardSchema:
        """构建完整的 Dashboard Schema

        Args:
            widgets: Widget dict 列表（含 id, title, widget_type, importance_score,
                     preferred_size, business_topic, chart_type, chart_config,
                     supported_filters, display_role, analysis_type）
            title: Dashboard 标题
            layout_name: 指定布局名（None = 自动选择）

        Returns:
            DashboardSchema
        """
        if not widgets:
            return self._empty_schema(title)

        # 1. Business Grouping
        groups = self._grouper.group(widgets)

        # 2. Layout Selection
        if layout_name is None:
            layout_name = self._selector.select(widgets, groups)
        layout_data = _load_layout_yaml(layout_name)
        config = LayoutConfig.from_dict(layout_data)

        # 3. Grid Allocation
        slots = self._allocator.allocate(widgets, config, groups)

        # 4. Section 构建
        sections = self._build_sections(slots, config)

        # 5. 交互配置
        interactions = self._build_interactions(widgets, config, groups)

        # 6. 组装 Schema
        schema = DashboardSchema(
            id=f"dashboard_{uuid.uuid4().hex[:8]}",
            title=title,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            version="1.0",
            metadata={
                "widget_count": len(widgets),
                "layout_selected": layout_name,
                "groups": len(groups),
                "generator": "LayoutEngine v1.0",
            },
            layout=config,
            widgets=slots,
            sections=sections,
            groups=groups,
            interactions=interactions,
            theme={"mode": "light", "primary_color": "#38BDF8"},
            responsive={"breakpoints": {"lg": 1200, "md": 768, "sm": 480}},
            dark_mode=False,
            mobile={"enabled": False},
        )

        return schema

    # ===== 内部方法 =====

    def _build_sections(
        self,
        slots: List[WidgetSlot],
        config: LayoutConfig,
    ) -> List[DashboardSection]:
        """从 Grid Slot 构建 DashboardSection 列表"""
        section_map: Dict[str, DashboardSection] = {}
        section_display = {
            "hero": "核心指标",
            "main": "主要分析",
            "secondary": "辅助分析",
            "footer": "补充信息",
        }

        for slot in slots:
            # 根据 y 和 slot 的重要性推断 section role
            role = self._infer_section_role(slot, config)
            sec_key = role.value

            if sec_key not in section_map:
                section_map[sec_key] = DashboardSection(
                    id=f"sec_{sec_key}",
                    role=role,
                    title=section_display.get(sec_key, sec_key),
                )

            section_map[sec_key].widget_ids.append(slot.widget_id)

        # 设置 y 范围
        sections = list(section_map.values())
        for i, sec in enumerate(sections):
            sec_widgets = [s for s in slots if s.widget_id in sec.widget_ids]
            if sec_widgets:
                sec.y_start = min(s.y for s in sec_widgets)
                sec.y_end = max(s.y + s.h for s in sec_widgets)

        return sections

    @staticmethod
    def _infer_section_role(slot: WidgetSlot, config: LayoutConfig) -> SectionRole:
        """从 WidgetSlot 推断 section role"""
        if slot.size_class == "hero":
            return SectionRole.HERO
        if slot.importance_score >= 70:
            return SectionRole.MAIN
        if slot.importance_score >= 40:
            return SectionRole.SECONDARY
        return SectionRole.SIDEBAR

    @staticmethod
    def _build_interactions(
        widgets: List[Dict[str, Any]],
        config: LayoutConfig,
        groups: List[BusinessGroup],
    ) -> Dict[str, Any]:
        """构建 Dashboard 交互配置"""
        # 收集所有 filter field
        all_filters: set = set()
        for w in widgets:
            for f in w.get("supported_filters", []):
                if isinstance(f, dict):
                    all_filters.add(f.get("field", ""))
                elif isinstance(f, str):
                    all_filters.add(f)

        return {
            "global_filters": sorted([f for f in all_filters if f]),
            "default_filter": config.default_filter,
            "cross_filter_groups": config.cross_filter_groups,
            "drill_down_enabled": any(w.get("drill_down") for w in widgets),
            "cross_filter_enabled": any(w.get("cross_filter") for w in widgets),
            "business_groups": [
                {"topic": g.topic, "widget_count": len(g.widget_ids)}
                for g in groups
            ],
        }

    @staticmethod
    def _empty_schema(title: str) -> DashboardSchema:
        """生成空 Dashboard Schema"""
        return DashboardSchema(
            id="empty_dashboard",
            title=title,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            metadata={"widget_count": 0, "note": "无可用 Widget"},
        )
