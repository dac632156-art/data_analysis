"""
Widget Generator —— AnalysisPackage → Business Widget 转换器

唯一职责：将 AnalysisPackage 列表转换为标准化的 Business Widget 列表。

禁止：
- 重新读取 DataFrame
- 重新计算指标
- 重新执行 Template
- 生成新的 BusinessFinding
- 修改 AnalysisPackage 数据

所有信息只从 AnalysisPackage 的已有字段中提取。
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.analysis_templates.base import AnalysisPackage
    from src.domain.business_finding import BusinessFinding

from src.dashboard.models import (
    Widget, WidgetType, WidgetSize, DisplayRole,
    WidgetFilter, WidgetDataSource,
)
from src.dashboard.widget_mapping import (
    get_widget_config, FILTER_FIELD_LABELS, DEFAULT_WIDGET_CONFIG,
)
from src.domain.business_finding import (
    Severity, Direction, FindingCategory,
)


# ============================================================
# Widget Generator
# ============================================================

class WidgetGenerator:
    """将 AnalysisPackage 转换为 Business Widget

    使用方式：
        gen = WidgetGenerator()
        widgets = gen.generate(packages)
    """

    def __init__(self):
        self._widgets: List[Widget] = []
        self._config: Dict[str, Any] = {}

    # ============================================================
    # 主入口
    # ============================================================

    def generate(self, packages: List[AnalysisPackage]) -> List[Widget]:
        """将 AnalysisPackage 列表转换为 Widget 列表

        Args:
            packages: AnalysisPackage 对象列表

        Returns:
            Widget 列表（已按 priority 降序排列，尺寸由排名决定）
        """
        self._widgets = []

        for pkg in packages:
            if not self._is_valid_package(pkg):
                continue
            widgets = self._package_to_widgets(pkg)
            self._widgets.extend(widgets)

        # 按 priority 降序排列
        self._widgets.sort(key=lambda w: w.priority, reverse=True)

        # ★ 排名决定尺寸：按 importance 排名分配 HERO / LARGE / MEDIUM / SMALL
        # 不依赖绝对分数，只看"谁比谁更重要"
        self._size_by_rank(self._widgets)

        # ★ 专业大屏排版落定（与 RAG 骨架对齐）：
        # KPI widget → header（顶部 4 个 KPI 条），其它按排名分组到 main / secondary / footer。
        # 同时在 metadata.slot 写入"header" / "main-{n}" / "secondary-{n}" / "footer-{n}"，
        # 前端 BigScreenCard 即可按 slot 渲染"顶部 KPI 条 + 多栏区域"骨架，
        # 不再用 1-2 列瀑布流。
        self._assign_display_slots(self._widgets)

        return list(self._widgets)

    def generate_from_dicts(self, packages: List[Dict[str, Any]]) -> List[Widget]:
        """dict 版本入口——兼容后端 API 返回的 JSON 序列化 AnalysisPackage

        saved_packages 是 dict 列表，此方法自动转为 WidgetGenerator 能消费的格式。
        """
        wrapped = [_DictWrapper(p) for p in packages]
        return self.generate(wrapped)

    # ============================================================
    # 单 Package 转换
    # ============================================================

    def _package_to_widgets(self, pkg: AnalysisPackage) -> List[Widget]:
        """单个 AnalysisPackage → 一个或多个 Widget"""
        analysis_type = getattr(pkg, "analysis_type", "") or ""
        self._config = get_widget_config(analysis_type)

        widget = self._build_widget(pkg)
        return [widget]

    def _build_widget(self, pkg: AnalysisPackage) -> Widget:
        """构建单个 Widget（填充所有字段）"""
        # ----- 基础信息 -----
        title = self._derive_title(pkg)
        description = self._derive_description(pkg)
        widget_type = self._derive_widget_type(pkg)

        # ----- 业务信息 -----
        analysis_type = getattr(pkg, "analysis_type", "") or ""
        business_topic = self._config.get("business_topic", "分析结果")
        finding_summary = self._derive_finding_summary(pkg)

        # ----- 评分 & 尺寸 -----
        importance_score = self._calculate_importance_score(pkg)
        preferred_size = self._score_to_size(importance_score)
        priority = self._score_to_priority(importance_score)

        # ----- 可视化 -----
        chart_type = self._derive_chart_type(pkg)
        chart_config = self._extract_chart_config(pkg)

        # ----- 数据源 -----
        data_source = self._extract_data_source(pkg)

        # ----- 角色 -----
        display_role = self._derive_display_role(pkg, importance_score)

        # ----- 筛选器 -----
        filters = self._infer_filters(pkg)

        # ----- 下钻 / 交叉筛选 -----
        drill_down = bool(self._config.get("drill_down", False))
        cross_filter = bool(self._config.get("cross_filter", False))

        return Widget(
            title=title,
            description=description,
            widget_type=widget_type,
            analysis_type=analysis_type.replace("_analysis", ""),
            business_topic=business_topic,
            finding_summary=finding_summary,
            importance_score=importance_score,
            chart_type=chart_type,
            chart_config=self._enrich_chart_config(chart_config, pkg, widget_type),
            data_source=data_source,
            preferred_size=preferred_size,
            priority=priority,
            display_role=display_role,
            supported_filters=filters,
            drill_down=drill_down,
            cross_filter=cross_filter,
            metadata=self._enrich_metadata(pkg, importance_score, chart_type=chart_type, widget_type=widget_type),
            _raw_package_ref=_safe_id(pkg),
        )

    # ============================================================
    # 字段派生方法
    # ============================================================

    def _derive_title(self, pkg: AnalysisPackage) -> str:
        """派生 Widget 标题"""
        # 优先从 AnalysisPackage 中取
        business_question = getattr(pkg, "business_question", "") or ""
        metric = getattr(pkg, "metric", "") or ""
        dimension = getattr(pkg, "dimension", "") or ""

        if business_question:
            # 去掉问号，作为标题
            q = business_question.rstrip("？?")
            if len(q) <= 20:
                return q
            return q[:18] + "…"

        if metric and dimension:
            return f"{metric} × {dimension}"

        return str(self._config.get("default_title", "分析结果"))

    def _derive_description(self, pkg: AnalysisPackage) -> str:
        """派生 Widget 描述"""
        desc = str(self._config.get("description", ""))
        if desc:
            return desc
        # 从 insights 第一条生成
        insights = getattr(pkg, "insights", []) or []
        if insights:
            first = str(insights[0]).strip()
            return first[:100] if len(first) > 100 else first
        return ""

    def _derive_widget_type(self, pkg: AnalysisPackage) -> WidgetType:
        """派生 WidgetType——数据驱动，而非硬编码

        优先级：
        1. 有图表数据 → CHART（即使有表格也优先展示图）
        2. 有表格但无图 → TABLE
        3. 有KPI但无图无表 → KPI
        4. 兜底：从配置文件取，配置文件也没有 → INSIGHT
        """
        chart_data = getattr(pkg, "chart_data", []) or []
        # V3 新字段：charts（ChartItem 列表，含 option），与 chart_data 并行
        charts = getattr(pkg, "charts", []) or []
        tables = getattr(pkg, "tables", []) or []
        kpis = getattr(pkg, "kpis", []) or []

        # 1) 有图表 → chart（最直观的展示方式）
        if chart_data or charts:
            return WidgetType.CHART

        # 2) 有表格但无图表 → table（用户勾选了表类型分析）
        if tables:
            return WidgetType.TABLE

        # 3) 有KPI但无图表/表格 → kpi
        if kpis:
            return WidgetType.KPI

        # 4) 兜底：从配置文件取
        wtype = self._config.get("widget_type", "insight")
        try:
            return WidgetType(wtype)
        except ValueError:
            return WidgetType.INSIGHT

    def _derive_chart_type(self, pkg: AnalysisPackage) -> Optional[str]:
        """派生图表类型（从配置，或从 package 的第一个 chart）"""
        config_chart = self._config.get("chart_type")
        if config_chart:
            return str(config_chart)
        # ★ 关键修复：与 _extract_chart_config 完全一致的优先级——
        #   1) charts（来自 ai_layout 的 ChartItem）→ .option
        #   2) chart_data（来自 model 的 ChartData）→ .chart_type & .title & .data
        #
        # 早期版本两处优先级相反导致 cohort/graph 出现 series.type=line 的退化。
        chart_data = getattr(pkg, "charts", []) or []
        if not chart_data:
            chart_data = getattr(pkg, "chart_data", []) or []
        if chart_data:
            first = chart_data[0]
            got = None
            first_title = ""
            if hasattr(first, "chart_type"):
                got = str(getattr(first, "chart_type", "bar"))
                first_title = str(getattr(first, "title", "") or "")
            elif isinstance(first, dict):
                got = str(first.get("chart_type", first.get("type", "bar")))
                first_title = str(first.get("title", "") or "")

            # ★ 兜底：基于 chart title 或 business_question 识别热力图 / 关联图。
            #    解决 chart_data 字段为 dict 或 chart_type 缺失时被默认成 bar 的问题。
            bq = str(getattr(pkg, "business_question", "") or "")
            match_text = (first_title + "|" + bq).lower()
            if (got and ("cohort_heatmap" in got.lower() or got == "heatmap" and "cohort" in match_text)):
                return "cohort_heatmap"
            if (got and got == "graph"):
                return "graph"
            if "同期群" in match_text or "留存矩阵" in match_text or "cohort" in match_text:
                return "cohort_heatmap"
            if "关联" in match_text or "频繁项集" in match_text or "graph" in match_text:
                return "graph"

            return got or None
        return None

    def _derive_finding_summary(self, pkg: AnalysisPackage) -> str:
        """派生核心发现摘要"""
        findings = getattr(pkg, "findings", []) or []
        for f in findings:
            title = _safe_get(f, "title")
            if title:
                return str(title)[:120]
        # fallback: 取第一条 insight
        insights = getattr(pkg, "insights", []) or []
        if insights:
            return str(insights[0])[:120]
        return ""

    def _derive_display_role(self, pkg: AnalysisPackage, score: int) -> DisplayRole:
        """派生 layout role"""
        role = self._config.get("display_role", "secondary")
        try:
            return DisplayRole(role)
        except ValueError:
            pass
        # 高 score 自动提升为 main
        if score >= 80:
            return DisplayRole.MAIN
        if score >= 50:
            return DisplayRole.SECONDARY
        return DisplayRole.SIDEBAR

    # ============================================================
    # Importance Score（不调用 LLM，纯规则）
    # ============================================================

    def _calculate_importance_score(self, pkg: AnalysisPackage) -> int:
        """计算 importance_score 0-100

        评分因素（全部来自 AnalysisPackage 已有字段）：
        1. Finding Severity（严重程度）
        2. Business Impact（业务影响文字长度 ≈ 影响程度）
        3. Confidence（置信度）
        4. Data Coverage（KPI/Chart 数量）
        5. Analysis Priority（来自 analysis_type 的默认优先级）
        6. Chart Type Weight（KPI/trend 类权重更高）
        """
        score = 30  # 基准分（降低以拉开差距，配合 _enforce_size_distribution 保证层次）

        findings = getattr(pkg, "findings", []) or []

        # 1. Severity（最多贡献 20 分）
        severity_scores = {
            Severity.CRITICAL: 20,
            Severity.HIGH: 15,
            Severity.MEDIUM: 10,
            Severity.LOW: 5,
            Severity.INFO: 2,
        }
        max_sev = Severity.INFO
        for f in findings:
            sev = _safe_get(f, "severity")
            if isinstance(sev, Severity):
                sev_idx = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM,
                           Severity.LOW, Severity.INFO].index(sev)
                max_idx = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM,
                           Severity.LOW, Severity.INFO].index(max_sev)
                if sev_idx < max_idx:
                    max_sev = sev
        score += severity_scores.get(max_sev, 2)

        # 2. Business Impact（最多贡献 10 分）
        total_impact_len = 0
        for f in findings:
            impact = _safe_get(f, "business_impact")
            total_impact_len += len(str(impact)) if impact else 0
        if total_impact_len > 80:
            score += 10
        elif total_impact_len > 40:
            score += 7
        elif total_impact_len > 0:
            score += 3

        # 3. Confidence（最多贡献 8 分）
        conf = getattr(pkg, "confidence", 0.5) or 0.5
        score += round(conf * 8)

        # 4. Data Coverage（KPI + Chart 数量，最多贡献 10 分）
        kpi_count = len(getattr(pkg, "kpis", []) or [])
        chart_count = len(getattr(pkg, "chart_data", []) or [])
        data_points = kpi_count + chart_count
        if data_points >= 6:
            score += 10
        elif data_points >= 3:
            score += 6
        elif data_points >= 1:
            score += 2

        # 5. Analysis Priority（从 mappings 中的 tags/优先级推断，最多贡献 5 分）
        display_role = self._config.get("display_role", "secondary")
        if display_role == "main":
            score += 5
        elif display_role == "secondary":
            score += 2

        # 6. Chart Type Weight（轻度区分：KPI+5，趋势+3，其他+1）
        chart_type = self._derive_chart_type(pkg) or ""
        ct_weights = {"kpi": 5, "line": 3, "map": 4, "map_3d": 4, "gauge": 3}
        score += ct_weights.get(chart_type, 1)

        return min(max(score, 0), 100)

    # ============================================================
    # Size & Priority 计算
    # ============================================================

    @staticmethod
    def _score_to_size(score: int) -> WidgetSize:
        """importance_score → preferred_size"""
        if score >= 80:
            return WidgetSize.HERO
        if score >= 60:
            return WidgetSize.LARGE
        if score >= 35:
            return WidgetSize.MEDIUM
        return WidgetSize.SMALL

    @staticmethod
    def _size_by_rank(widgets: List[Widget]):
        """按 importance 排名分配尺寸（排名制，非绝对分制）

        原理：绝对分数受 severity/confidence 等影响波动大，全挤在同一区间。
        排名法则不受绝对分影响——只比较"谁比谁重要"，自然拉开梯度。

        BI 大屏布局：
        7+ Widgets → 第1名 HERO | 第2-3名 LARGE | 其余 MEDIUM | 末尾 SMALL
        5-6        → 第1名 HERO | 第2名 LARGE   | 其余 MEDIUM
        3-4        → 第1名 HERO | 其余 MEDIUM
        ≤2         → 保持原始尺寸
        """
        n = len(widgets)
        if n <= 2:
            return

        # 按 importance_score 降序排（同 priority 排序保持一致）
        sorted_widgets = sorted(widgets, key=lambda w: w.importance_score, reverse=True)

        # 根据 Widget 总数决定各尺寸的截止位
        if n >= 7:
            # 1 HERO + 2 LARGE + 剩余 MEDIUM，最后 1-2 个可能 SMALL
            hero_cut = 1
            large_cut = 3
            small_cut = n - 1  # 最后一个 SMALL，给底部一点变化
        elif n >= 5:
            hero_cut = 1
            large_cut = 2
            small_cut = n
        else:  # 3-4
            hero_cut = 1
            large_cut = 1  # 第2名开始就是 MEDIUM
            small_cut = n

        for rank, w in enumerate(sorted_widgets):
            if rank < hero_cut:
                w.preferred_size = WidgetSize.HERO
            elif rank < large_cut:
                w.preferred_size = WidgetSize.LARGE
            elif rank < small_cut:
                w.preferred_size = WidgetSize.MEDIUM
            else:
                w.preferred_size = WidgetSize.SMALL

    @staticmethod
    def _synthesize_kpi_widgets(widgets: List[Widget], target: int = 4) -> List[Widget]:
        """当 batch 内没有原生 KPI widget 时，从 top-importance 图表里派生 KPI 卡

        目的：保证任何大屏都有"顶部 KPI 条"，满足所有骨架（A/B/C/D/E）的必备槽位。

        派生策略（按 chart type 自适应）：
        - 时间序列（line/bar）：取末点值 → 总量；
        - 排名（bar）：取 top1 值 → 第一名数值；
        - 结构（pie）：最大扇区值 → 最大占比数值；
        - 雷达 / 其他：取第一个有效数值。
        """
        # 选重要性最高的前 N 张图表（必须是 CHART 或 KPI）
        chart_widgets = [w for w in widgets if w.widget_type in (WidgetType.CHART, WidgetType.KPI)]
        chart_widgets.sort(key=lambda w: w.importance_score, reverse=True)
        picks = chart_widgets[:target]
        if not picks:
            return []

        synthesized: List[Widget] = []
        for idx, w in enumerate(picks):
            value, unit, label = _extract_kpi_value_from_chart(w)
            if value is None:
                continue
            kpi = Widget(
                title=_short_kpi_title(w.title),
                description="",
                widget_type=WidgetType.KPI,
                analysis_type=w.analysis_type,
                business_topic=w.business_topic,
                finding_summary=w.finding_summary or w.title,
                importance_score=max(80, w.importance_score - 5),
                chart_type=None,
                chart_config={"data": [], "option": {}},
                data_source=WidgetDataSource(package_id=_safe_id_get(w)),
                preferred_size=WidgetSize.SMALL,
                priority=10,
                display_role=DisplayRole.SECONDARY,
                supported_filters=[],
                drill_down=False,
                cross_filter=False,
                metadata={
                    "synthesized": True,
                    "source_widget_id": w.id,
                    "formatted": _format_kpi_value(value, unit),
                    "value": _format_kpi_value(value, unit),
                    "unit": unit,
                    "kpi_label": label,
                    "change": _safe_delta(w),
                    "use_ethereal": True,
                    "chart_type": "kpi",
                },
                _raw_package_ref=None,
            )
            synthesized.append(kpi)
        return synthesized

    @staticmethod
    def _assign_display_slots(widgets: List[Widget]) -> None:
        """专业大屏排版槽位落定（与 RAG 骨架_A/B/D 对齐）。

        规则：
        - KPI widget → display_role=HEADER, slot="header-{i}"（顶部 KPI 条，最多 4 个）
        - 排名 1-3 主图 → display_role=MAIN, slot="main-{i}"（多栏主要分析区）
        - 排名 4+ → display_role=SECONDARY, slot="secondary-{i}"（辅助分析区）
        - 表格/洞察 → display_role=FOOTER, slot="footer-{i}"（底部信息区）

        同时写 metadata.slot 供前端消费，metadata.skeleton_size_class 供 WidgetFactory 调整尺寸。
        """
        # 排序：HERO 优先 → KPI 优先（顶部 KPI 永远排最前）
        def _sort_key(w: Widget):
            # 1. KPI 排最前
            if w.widget_type == WidgetType.KPI:
                return (0, -w.importance_score)
            # 2. 表格/洞察排最后
            if w.widget_type in (WidgetType.TABLE, WidgetType.INSIGHT, WidgetType.SUMMARY):
                return (2, -w.importance_score)
            # 3. 其它（图表/地图）按 importance 降序
            return (1, -w.importance_score)
        sorted_widgets = sorted(widgets, key=_sort_key)

        header_idx = main_idx = secondary_idx = footer_idx = 0
        for w in sorted_widgets:
            if not w.metadata:
                w.metadata = {}
            if w.widget_type == WidgetType.KPI and header_idx < 4:
                # KPI 在大屏里走顶部条带：用 metadata.slot="header-{i}" 标识（DisplayRole
                # 没有 HEADER 枚举，复用 MAIN，区分由 slot 字段承担）
                w.display_role = DisplayRole.MAIN
                w.metadata["slot"] = f"header-{header_idx}"
                w.metadata["slot_zone"] = "header"
                header_idx += 1
            elif w.widget_type in (WidgetType.TABLE, WidgetType.INSIGHT, WidgetType.SUMMARY):
                w.display_role = DisplayRole.FOOTER
                w.metadata["slot"] = f"footer-{footer_idx}"
                w.metadata["slot_zone"] = "footer"
                footer_idx += 1
            elif main_idx < 3:
                w.display_role = DisplayRole.MAIN
                w.metadata["slot"] = f"main-{main_idx}"
                w.metadata["slot_zone"] = "main"
                main_idx += 1
            else:
                w.display_role = DisplayRole.SECONDARY
                w.metadata["slot"] = f"secondary-{secondary_idx}"
                w.metadata["slot_zone"] = "secondary"
                secondary_idx += 1

        # ★ 如果头部 KPI 条为空（大多数 batch 不会自然生成 KPI widget，因为
        # _derive_widget_type 把"有 chart_data"的包都判为 CHART），则从排名前 4
        # 的图表里派生出 4 个 KPI 卡，保证大屏永远有顶部核心指标区
        # ——符合所有骨架（A/B/C/D/E）的"KPI 条"要求
        if header_idx == 0:
            synthetic_kpis = WidgetGenerator._synthesize_kpi_widgets(widgets, target=4)
            for kpi in synthetic_kpis:
                kpi.display_role = DisplayRole.MAIN
                kpi.metadata["slot"] = f"header-{header_idx}"
                kpi.metadata["slot_zone"] = "header"
                widgets.append(kpi)
                header_idx += 1
            # 把后注入的 KPI 放最前
            widgets.sort(key=lambda w: (
                0 if w.widget_type == WidgetType.KPI else
                2 if w.widget_type in (WidgetType.TABLE, WidgetType.INSIGHT, WidgetType.SUMMARY) else
                1, -w.importance_score,
            ))

    @staticmethod
    def _score_to_priority(score: int) -> int:
        """importance_score → display priority 1-10"""
        if score >= 90:
            return 10
        if score >= 80:
            return 8
        if score >= 60:
            return 6
        if score >= 40:
            return 4
        return 2

    # ============================================================
    # Data Source
    # ============================================================

    def _extract_data_source(self, pkg: AnalysisPackage) -> WidgetDataSource:
        """提取数据源引用（不持有原始数据）"""
        finding_ids = []
        for f in (getattr(pkg, "findings", []) or []):
            fid = _safe_get(f, "id")
            if fid:
                finding_ids.append(str(fid))

        chart_slot = ""
        chart_data = getattr(pkg, "chart_data", []) or []
        if chart_data:
            first = chart_data[0]
            if hasattr(first, "slot"):
                chart_slot = str(getattr(first, "slot", ""))
            elif isinstance(first, dict):
                chart_slot = str(first.get("slot", ""))

        table_title = ""
        tables = getattr(pkg, "tables", []) or []
        if tables:
            first = tables[0]
            if hasattr(first, "title"):
                table_title = str(getattr(first, "title", ""))
            elif isinstance(first, dict):
                table_title = str(first.get("title", ""))

        kpi_label = ""
        kpis = getattr(pkg, "kpis", []) or []
        if kpis:
            first = kpis[0]
            if hasattr(first, "label"):
                kpi_label = str(getattr(first, "label", ""))
            elif isinstance(first, dict):
                kpi_label = str(first.get("label", ""))

        return WidgetDataSource(
            package_id=_safe_id(pkg),
            finding_ids=finding_ids,
            chart_slot=chart_slot,
            table_title=table_title,
            kpi_label=kpi_label,
        )

    def _extract_chart_config(self, pkg: AnalysisPackage) -> Dict[str, Any]:
        """提取图表配置（前端可直接消费的 ECharts option）"""
        charts = getattr(pkg, "charts", []) or []
        if not charts:
            charts = getattr(pkg, "chart_data", []) or []

        config: Dict[str, Any] = {
            "chart_type": self._derive_chart_type(pkg),
            "data_available": False,
        }

        if not charts:
            return config

        first = charts[0]

        # 1) 优先使用已有的 ECharts option（如 ai_layout 生成）。
        #    但若 widget 需要特殊图型（cohort_heatmap/graph 这种 ECharts 会校验 series.type 的），
        #    丢弃原 option，用 data 走 _build_echarts_option 的专门分支重画。
        SPECIAL_CHART_TYPES = {"cohort_heatmap", "graph"}
        option = {}
        if hasattr(first, "option"):
            option = getattr(first, "option", {}) or {}
        elif isinstance(first, dict) and first.get("option"):
            option = first["option"]
        if option and (config.get("chart_type") in SPECIAL_CHART_TYPES):
            option = {}  # 强制走数据重建分支

        # 2) 如果没有 option，从 data 构造
        if not option:
            data_list = []
            if hasattr(first, "data"):
                data_list = getattr(first, "data", []) or []
            elif isinstance(first, dict):
                data_list = first.get("data", []) or []

            chart_type = config["chart_type"] or "bar"
            x_label = getattr(first, "x", "") if hasattr(first, "x") else first.get("x", "维度") if isinstance(first, dict) else "维度"
            y_label = getattr(first, "y", "") if hasattr(first, "y") else first.get("y", "指标") if isinstance(first, dict) else "指标"
            # 修复: 模板若仍用字面 "x"/"y" 时,从 pkg.metric / pkg.dimension 取真实列名
            if x_label in ("x", "", "维度") and pkg is not None:
                x_label = getattr(pkg, "dimension", "") or x_label
            if y_label in ("y", "", "指标") and pkg is not None:
                y_label = getattr(pkg, "metric", "") or y_label
            option = self._build_echarts_option(chart_type, data_list, x_label, y_label)

        config["option"] = option

        # 3) 统计信息
        if hasattr(first, "data"):
            data_list = getattr(first, "data", [])
        elif isinstance(first, dict):
            data_list = first.get("data", [])
        else:
            data_list = []
        config["data_count"] = len(data_list) if isinstance(data_list, list) else 0
        config["data_available"] = config["data_count"] > 0

        # 4) ★ 提取分类维度的 distinct 值（供前端下拉过滤器使用）
        if isinstance(data_list, list) and data_list:
            dim_values = self._extract_dim_values(data_list)
            if dim_values:
                config["dim_values"] = dim_values

        return config

    @staticmethod
    def _extract_dim_values(data_list: List[Any]) -> Dict[str, List[str]]:
        """从 chart_data 提取所有分类维度的 distinct 值

        字段命名约定：
        - 包含 省/市/区/地区/城市/city/region/省份 → region
        - 包含 产品/商品/品类/产品名/品牌/product/sku → product
        - 包含 渠道/来源/平台/channel/source → channel
        - 包含 类别/分类/类型/category/type → category
        - 包含 日期/月份/时间/date/month/year → time
        """
        result: Dict[str, set] = {
            "region": set(), "product": set(), "channel": set(),
            "category": set(), "time": set(),
        }
        rules = {
            "region":  ["省", "市", "区", "地区", "城市", "city", "region", "province", "国家"],
            "product": ["产品", "商品", "品类", "品牌", "product", "sku", "item"],
            "channel": ["渠道", "来源", "平台", "channel", "source"],
            "category": ["类别", "分类", "类型", "category", "type"],
            "time":    ["日期", "时间", "月份", "date", "month", "year", "year_month"],
        }

        def match_field(col: str) -> str:
            lower = str(col).lower()
            for fld, kws in rules.items():
                for kw in kws:
                    if kw.lower() in lower:
                        return fld
            return ""

        for row in data_list:
            if not isinstance(row, dict):
                continue
            for col, val in row.items():
                if val is None or isinstance(val, (int, float)):
                    continue
                fld = match_field(col)
                if fld:
                    result[fld].add(str(val))

        # 限制每个维度最多 50 个值
        return {k: sorted(list(v))[:50] for k, v in result.items() if v}

    def _build_echarts_option(
        self, chart_type: str, data: List[Any],
        x_label: str = "", y_label: str = "",
    ) -> Dict[str, Any]:
        """从 chart_data 构造最小可用的 ECharts option"""
        if not data:
            return {}

        # ★ 同期群下三角热力图：data 行键 [Index_j, 首单月, value, ci_lower/ci_upper(可选)]
        # 哨兵值 -1 表示"未观测"，渲染为灰块；其余值用 visualMap 分段上色。
        if chart_type == "cohort_heatmap":
            return self._build_cohort_heatmap_option(data)

        # ★ 商品关联规则关系网络图：data 行键 [source, target, value, lift(可选)]
        if chart_type == "graph":
            return self._build_graph_option(data)

        # 提取 x, y 序列
        x_data = []
        y_data = []
        for item in data:
            if isinstance(item, dict):
                # 兼容 {x: ..., y: ...} 和 {维度: ..., 指标: ...}
                if "x" in item and "y" in item:
                    x_data.append(str(item["x"]))
                    y_data.append(float(item["y"]) if item["y"] is not None else 0)
                else:
                    # 取第一个 key 作 x，第二个作 y
                    keys = list(item.keys())
                    if len(keys) >= 2:
                        x_data.append(str(item[keys[0]]))
                        try:
                            y_data.append(float(item[keys[1]]))
                        except (TypeError, ValueError):
                            y_data.append(0)
                    elif len(keys) == 1:
                        x_data.append(str(item[keys[0]]))
                        y_data.append(0)

        if not x_data:
            return {}

        if chart_type == "pie":
            return {
                "tooltip": {"trigger": "item"},
                "legend": {"type": "scroll", "bottom": 0},
                "series": [{
                    "type": "pie",
                    "radius": ["35%", "65%"],
                    "center": ["50%", "50%"],
                    "data": [{"name": x_data[i], "value": y_data[i]} for i in range(len(x_data))],
                }],
            }

        if chart_type == "line":
            series = {"name": y_label or "y", "type": "line", "data": y_data, "smooth": True, "showSymbol": True}
        else:  # bar / scatter / 默认
            series = {"name": y_label or "y", "type": chart_type, "data": y_data}

        # ★ 调试钩子：每次构建都把 chart_type + series.type 写到 dev 日志，便于排查"图表派发异常"问题
        try:
            import json as _json_dbg, os as _os_dbg, time as _t_dbg
            _dbg_path = r"D:\数据分析项目\backend\_echart_dbg.log"
            with open(_dbg_path, "a", encoding="utf-8") as _f_dbg:
                _series_types = [s.get("type") if isinstance(s, dict) else None for s in ([series] if isinstance(series, dict) else series)]
                _f_dbg.write(
                    f"[{_t_dbg.strftime('%H:%M:%S')}] "
                    f"chart_type={chart_type!r} series_types={_series_types!r} "
                    f"data_len={len(data) if isinstance(data, list) else 'NA'}\n"
                )
        except Exception:
            pass

        return {
            "tooltip": {"trigger": "axis"},
            "grid": {"left": 8, "right": 16, "top": 16, "bottom": 8, "containLabel": True},
            "xAxis": {"type": "category", "data": x_data, "name": x_label},
            "yAxis": {"type": "value", "name": y_label},
            "series": [series],
        }

    # ---------- 同期群下三角热力图 / 关联网络图 option 构造 ----------
    _COHORT_SENTINEL = -1.0  # 与 src/analysis_engine/models/cohort.py SENTINEL 对齐

    def _build_cohort_heatmap_option(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """构造同期群下三角热力图 ECharts option（与 echart_generator.create_cohort_heatmap 同口径）。"""
        # ★ 调试日志：标记走入了此分支
        try:
            import time as _t_dbg
            with open(r"D:\数据分析项目\backend\_echart_dbg.log", "a", encoding="utf-8") as _f_dbg:
                _f_dbg.write(f"[{_t_dbg.strftime('%H:%M:%S')}] cohort_heatmap branch HIT, data_len={len(data) if isinstance(data, list) else 'NA'}\n")
        except Exception:
            pass
        if not data:
            return {}
        try:
            xcats: List[Any] = []
            ycats: List[Any] = []
            x_idx: Dict[Any, int] = {}
            y_idx: Dict[Any, int] = {}
            heat: List[List[Any]] = []
            for r in data:
                if not isinstance(r, dict):
                    continue
                xv = r.get("Index_j")
                yv = r.get("首单月")
                v_raw = r.get("value", self._COHORT_SENTINEL)
                try:
                    v = float(v_raw)
                except (TypeError, ValueError):
                    v = self._COHORT_SENTINEL
                if xv not in x_idx:
                    x_idx[xv] = len(xcats)
                    xcats.append(xv)
                if yv not in y_idx:
                    y_idx[yv] = len(ycats)
                    ycats.append(yv)
                heat.append([x_idx[xv], y_idx[yv], v])

            # 排序：x=j 升序，y=cohort 升序（最近 cohort 在底，符合 cohort 表格直觉）
            xcats_sorted = sorted(xcats, key=lambda v: v if isinstance(v, (int, float)) else str(v))
            ycats_sorted = sorted(ycats, key=lambda v: str(v))
            # 重映射索引
            x_remap = {old: i for i, old in enumerate(xcats_sorted)}
            y_remap = {old: i for i, old in enumerate(ycats_sorted)}
            for row in heat:
                row[0] = x_remap.get(row[0], row[0])
                row[1] = y_remap.get(row[1], row[1])

            obs = [row[2] for row in heat if row[2] != self._COHORT_SENTINEL]
            vmin = min(obs) if obs else 0.0
            vmax = max(obs) if obs else 1.0
            if vmax - vmin < 1e-9:
                vmax = vmin + 1.0

            pieces = [{"value": self._COHORT_SENTINEL, "label": "未观测", "color": "#cbd5e1"}]
            n = 5
            step = (vmax - vmin) / n
            for k in range(n):
                lo = vmin + step * k
                hi = vmin + step * (k + 1)
                # 浅 → 深粉彩渐变（与仙气粉彩主题呼应）
                color = self._ethereal_heatmap_color(k / max(n - 1, 1))
                pieces.insert(1, {"min": lo, "max": hi + (k == n - 1 and 1e-9 or 0), "color": color})

            return {
                "tooltip": {
                    "position": "top",
                    "formatter": "(p) => p.value[2] === -1 ? '未观测' : `j=${p.value[0]} cohort=${p.value[1]}<br/>值=${p.value[2]}`",
                },
                "grid": {"left": 60, "right": 24, "top": 24, "bottom": 60, "containLabel": True},
                "xAxis": {"type": "category", "data": xcats_sorted, "name": "月偏移 Index_j",
                          "splitArea": {"show": True}},
                "yAxis": {"type": "category", "data": ycats_sorted, "name": "首单月 cohort",
                          "splitArea": {"show": True}},
                "visualMap": {"type": "piecewise", "pieces": pieces,
                              "left": "center", "bottom": 0, "orient": "horizontal",
                              "textStyle": {"fontSize": 10}},
                "series": [{
                    "type": "heatmap",
                    "data": heat,
                    "label": {"show": False},
                    "emphasis": {"itemStyle": {"borderColor": "#fff", "borderWidth": 1}},
                }],
                "_heatmap_kind": "cohort",
            }
        except Exception:
            return {}

    @staticmethod
    def _ethereal_heatmap_color(t: float) -> str:
        """仙气粉彩热力图颜色：从浅粉到深粉紫渐变（5 段）。"""
        # 与 src/dashboard/widget_generator.py 现有主题色保持同源思路：浅→深
        t = max(0.0, min(1.0, float(t)))
        # 端点（仙气粉彩）：浅粉 #ffe4ec → 深紫粉 #c084fc
        # 中间插值（线性）
        def hex_to_rgb(h):
            h = h.lstrip("#")
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        a = hex_to_rgb("#fce7f3")  # 最浅
        b = hex_to_rgb("#a855f7")  # 最深
        r = round(a[0] + (b[0] - a[0]) * t)
        g = round(a[1] + (b[1] - a[1]) * t)
        bl = round(a[2] + (b[2] - a[2]) * t)
        return f"rgb({r},{g},{bl})"

    def _build_graph_option(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """构造商品关联规则关系网络图 ECharts option。

        data 行键：source(商品A), target(商品B), value(共现次数), lift(提升度, 可选)。
        """
        # ★ 调试日志：标记走入了 graph 分支
        try:
            import time as _t_dbg
            with open(r"D:\数据分析项目\backend\_echart_dbg.log", "a", encoding="utf-8") as _f_dbg:
                _f_dbg.write(f"[{_t_dbg.strftime('%H:%M:%S')}] graph branch HIT, data_len={len(data) if isinstance(data, list) else 'NA'}\n")
        except Exception:
            pass
        if not data:
            return {}
        try:
            nodes_map: Dict[str, Dict[str, Any]] = {}
            links: List[Dict[str, Any]] = []
            for r in data:
                if not isinstance(r, dict):
                    continue
                src = str(r.get("source", "")).strip()
                tgt = str(r.get("target", "")).strip()
                if not src or not tgt:
                    continue
                if src not in nodes_map:
                    nodes_map[src] = {"name": src, "symbolSize": 12}
                if tgt not in nodes_map:
                    nodes_map[tgt] = {"name": tgt, "symbolSize": 12}
                try:
                    val = float(r.get("value", 1))
                except (TypeError, ValueError):
                    val = 1.0
                try:
                    lift = float(r.get("lift", 0))
                except (TypeError, ValueError):
                    lift = 0.0
                # 线粗=共现次数（最小 1，最大 6）；节点大小按累计共现次数累加
                nodes_map[src]["symbolSize"] = min(40, nodes_map[src].get("symbolSize", 12) + val * 0.1)
                nodes_map[tgt]["symbolSize"] = min(40, nodes_map[tgt].get("symbolSize", 12) + val * 0.1)
                links.append({
                    "source": src,
                    "target": tgt,
                    "value": val,
                    "lineStyle": {"width": max(1, min(6, val * 0.5)), "color": "#a855f7"},
                })

            nodes = [{"name": n["name"], "symbolSize": max(12, n.get("symbolSize", 12)),
                      "itemStyle": {"color": "#ec4899"}} for n in nodes_map.values()]
            return {
                "tooltip": {
                    "formatter": "(p) => p.dataType === 'edge' "
                                 "? `${p.data.source} ↔ ${p.data.target}<br/>共现 ${p.data.value} 次${p.data.lineStyle && ''}` "
                                 ": `${p.name}（累计共现 ${p.value || 0}）`",
                },
                "legend": {"data": [n["name"] for n in nodes], "type": "scroll", "bottom": 0,
                           "textStyle": {"fontSize": 10}},
                "series": [{
                    "type": "graph",
                    "layout": "force",
                    "data": nodes,
                    "links": links,
                    "force": {"repulsion": 120, "edgeLength": [30, 80]},
                    "roam": True,
                    "draggable": True,
                    "label": {"show": True, "position": "right", "fontSize": 10},
                    "lineStyle": {"opacity": 0.7, "curveness": 0.2},
                    "emphasis": {"focus": "adjacency"},
                }],
            }
        except Exception:
            return {}

    # ============================================================
    # Chart Config & Metadata 填充
    # ============================================================

    def _enrich_chart_config(
        self, config: Dict[str, Any], pkg: AnalysisPackage,
        widget_type: WidgetType,
    ) -> Dict[str, Any]:
        """为 KPI/Chart/Table Widget 补充数据"""
        if widget_type == WidgetType.KPI:
            # 从 derived_metrics 或 kpis 中提取数值用于 sparkline
            derived = getattr(pkg, "derived_metrics", {}) or {}
            values = None
            # 尝试取 values（BusinessMetrics 格式）
            if isinstance(derived, dict):
                values = derived.get("values")
            if not values:
                values = derived.get("growth_rates")
            if values and isinstance(values, list):
                config["data"] = [float(v) for v in values if v is not None]
            else:
                config["data"] = []

        elif widget_type == WidgetType.TABLE:
            # ★ TABLE Widget：从 AnalysisPackage.tables 提取表格数据
            tables = getattr(pkg, "tables", []) or []
            if tables:
                first_table = tables[0]
                if hasattr(first_table, "columns"):
                    config["columns"] = list(getattr(first_table, "columns", []))
                elif isinstance(first_table, dict):
                    config["columns"] = list(first_table.get("columns", []))

                # 取 rows（兼容 dataclass 和 dict 形态的 first_table）
                rows_src: list = []
                if hasattr(first_table, "rows"):
                    rows_src = list(getattr(first_table, "rows", []) or [])
                elif isinstance(first_table, dict):
                    rows_src = list(first_table.get("rows", []) or [])

                cols = list(config.get("columns", []) or [])

                def _row_to_list(r):
                    # 已经是 list/tuple → 直接转 list
                    if isinstance(r, (list, tuple)):
                        return list(r)
                    # dict：按 columns 顺序取值；没 columns 就拿 values
                    if isinstance(r, dict):
                        if cols:
                            return [r.get(c) for c in cols]
                        return list(r.values())
                    # 其他类型（None/str/数字）→ 兜底为单格
                    return [r]

                def _flatten_cell(v):
                    # 单元格里 pandas 序列化常出现 {"value": x, "format": ...} 或 {"x": ..., "y": ...}
                    # 递归取出"叶子"值，避免前端 String(dict) → [object Object]
                    if v is None or isinstance(v, (str, int, float, bool)):
                        return v
                    if isinstance(v, dict):
                        if "value" in v and len(v) <= 4:
                            return _flatten_cell(v["value"])
                        if "text" in v and len(v) <= 4:
                            return _flatten_cell(v["text"])
                        # 多字段 dict（特征向量等）→ 转紧凑字符串
                        try:
                            return ", ".join(f"{k}={_flatten_cell(vv)}" for k, vv in v.items() if vv is not None)
                        except Exception:
                            return str(v)
                    if isinstance(v, (list, tuple)):
                        return ", ".join(str(_flatten_cell(x)) for x in v)
                    return v

                config["rows"] = [[_flatten_cell(c) for c in _row_to_list(r)] for r in rows_src]
                config["table_type"] = (
                    str(getattr(first_table, "table_type", ""))
                    if hasattr(first_table, "table_type")
                    else str(first_table.get("table_type", "")) if isinstance(first_table, dict) else ""
                )
                config["data_available"] = bool(config.get("rows"))

        return config

    def _enrich_metadata(
        self, pkg: AnalysisPackage, score: int,
        chart_type: Optional[str] = None,
        widget_type: Optional[WidgetType] = None,
    ) -> Dict[str, Any]:
        """为 Widget metadata 补充 KPI 卡片所需字段，并同步 chart_type / series_type 供前端派发"""
        base = {
            "package_id": _safe_id(pkg),
            "template_used": getattr(pkg, "template_used", ""),
            "calculator_used": getattr(pkg, "calculator_used", ""),
            "confidence": getattr(pkg, "confidence", 1.0),
            "tags": list(self._config.get("tags", [])),
        }

        # ★ 同步 chart_type 到 metadata，供前端 ChartWidget 派发到 Ethereal*Chart
        # 即使后端 chart_type 为空，前端也会用 chartNode.series[0].type 兜底（ChartWidget.tsx）
        if chart_type:
            base["chart_type"] = chart_type
            base["series_type"] = chart_type  # 别名：EtherealChart 内部用 series_type 派发
        if widget_type:
            base["widget_type_name"] = widget_type.value
        # 标记统一走仙气粉彩组件库（前端读 use_ethereal 直接派发）
        base["use_ethereal"] = True


        # ★ 把 data_profile 注入 metadata，让前端下拉过滤能拿到分类列名
        data_profile = getattr(pkg, "data_profile", {}) or {}
        base["data_profile"] = {
            "category_cols": data_profile.get("category_cols", []),
            "numeric_cols": data_profile.get("numeric_cols", []),
            "time_cols": data_profile.get("time_cols", []),
        }
        # KPI Widget 需要 change + kpi_label
        findings = getattr(pkg, "findings", []) or []
        kpis = getattr(pkg, "kpis", []) or []

        # change: 从第一个 finding 的 value 提取
        change = 0.0
        for f in findings:
            val = _safe_get(f, "value")
            if val is not None and isinstance(val, (int, float)):
                change = float(val)
                break
        if change == 0.0 and kpis:
            first_kpi = kpis[0]
            ch = _safe_get(first_kpi, "change", "0")
            try:
                change = float(str(ch).replace("%", "").replace("+", ""))
            except (ValueError, TypeError):
                change = 0.0
        base["change"] = change

        # kpi_label: 从第一个 KPI 取 value
        if kpis:
            first = kpis[0]
            base["kpi_label"] = str(_safe_get(first, "value", ""))
        else:
            base["kpi_label"] = str(score)

        return base

    # ============================================================
    # Filter 推断
    # ============================================================

    def _infer_filters(self, pkg: AnalysisPackage) -> List[WidgetFilter]:
        """从 data_profile 推断支持的筛选器

        只根据 data_profile 中实际存在的列类型生成 filter，
        不创造不存在的字段。
        """
        filters: List[WidgetFilter] = []
        data_profile = getattr(pkg, "data_profile", {}) or {}

        time_cols = data_profile.get("time_cols", [])
        cat_cols = data_profile.get("category_cols", [])
        numeric_cols = data_profile.get("numeric_cols", [])

        # 时间维度 → time filter
        if time_cols:
            filters.append(WidgetFilter(
                field="time",
                label="时间范围",
                filter_type="date_range",
            ))

        # 分类维度 → region / product / category filter
        for col in cat_cols:
            col_lower = str(col).lower()
            field = self._classify_category_field(col_lower)
            if field:
                label = FILTER_FIELD_LABELS.get(field, str(col))
                # 去重
                existing = {f.field for f in filters}
                if field not in existing:
                    filters.append(WidgetFilter(
                        field=field,
                        label=label,
                        filter_type="dropdown",
                    ))

        # 数值维度 → 可选筛选（高/低）
        if len(numeric_cols) >= 2 and not filters:
            filters.append(WidgetFilter(
                field="metric",
                label="指标选择",
                filter_type="dropdown",
            ))

        return filters[:5]  # 最多 5 个筛选器

    @staticmethod
    def _classify_category_field(col_lower: str) -> str:
        """根据列名关键词推断 filter 类型"""
        region_kw = ["省份", "省", "城市", "市", "地区", "区域", "region", "city", "area", "geo"]
        product_kw = ["产品", "商品", "product", "sku", "item", "品类", "类目", "品牌"]
        channel_kw = ["渠道", "来源", "channel", "source", "平台"]

        for kw in region_kw:
            if kw in col_lower:
                return "region"
        for kw in product_kw:
            if kw in col_lower:
                return "product"
        for kw in channel_kw:
            if kw in col_lower:
                return "channel"

        return "category"

    # ============================================================
    # 工具方法
    # ============================================================

    @staticmethod
    def _is_valid_package(pkg: AnalysisPackage) -> bool:
        """检查 package 是否包含有效数据"""
        if pkg is None:
            return False
        findings = getattr(pkg, "findings", []) or []
        if findings:
            return True
        insights = getattr(pkg, "insights", []) or []
        if insights:
            return True
        charts = getattr(pkg, "chart_data", []) or []
        if charts:
            return True
        chart_items = getattr(pkg, "charts", []) or []
        if chart_items:
            return True
        kpis = getattr(pkg, "kpis", []) or []
        if kpis:
            return True
        return False


# ============================================================
# KPI 派生辅助（_synthesize_kpi_widgets 使用）
# ============================================================

def _safe_id_get(w) -> str:
    """安全获取 widget/package id（兼容 dataclass 和 dict）"""
    if w is None:
        return ""
    if isinstance(w, dict):
        return str(w.get("id") or w.get("widget_id") or "")
    return str(getattr(w, "id", "") or getattr(w, "widget_id", "") or "")


def _extract_kpi_value_from_chart(w) -> tuple:
    """从图表 widget 中抽出一个数值作为 KPI 卡的"核心数字"

    返回 (value: Optional[float], unit: str, label: str)
    """
    try:
        cfg = getattr(w, "chart_config", None) or {}
        if isinstance(cfg, dict):
            data = cfg.get("data") or []
            option = cfg.get("option") or {}
        else:
            data = []
            option = {}

        # 优先：直接读 cfg.data（数组/数值）——Ethereal* 风格
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                # 找第一个数值的字段（value/val/数量/mean/total/...）
                for k in ("value", "val", "count", "total", "amount", "mean", "y", "ratio", "percent"):
                    v = first.get(k)
                    if isinstance(v, (int, float)):
                        return float(v), "", str(first.get("name") or first.get("label") or "")
                # 退化：第一个数值
                for k, v in first.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        return float(v), "", str(first.get("name") or first.get("label") or "")
            if isinstance(first, (int, float)):
                return float(first), "", ""

        # 备选：从 ECharts option.series 取最后一个数据点的"和"或"末点"
        series_list = option.get("series") if isinstance(option, dict) else None
        if series_list:
            s = series_list[0] if series_list else {}
            s_data = s.get("data") if isinstance(s, dict) else None
            if isinstance(s_data, list) and s_data:
                last = s_data[-1]
                if isinstance(last, (int, float)):
                    return float(last), "", ""
                if isinstance(last, dict):
                    v = last.get("value") or last.get("y")
                    if isinstance(v, (int, float)):
                        return float(v), "", str(last.get("name") or "")

        return None, "", ""
    except Exception:
        return None, "", ""


def _format_kpi_value(value, unit: str) -> str:
    """格式化 KPI 数值"""
    if value is None:
        return ""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if unit == "%":
        return f"{v:.1f}%"
    if abs(v) >= 1_000_000_000:
        return f"{v / 1_000_000_000:.2f}B"
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:.2f}M"
    if abs(v) >= 10_000:
        return f"{v / 10_000:.2f}万"
    if abs(v) >= 1000:
        return f"{v / 1000:.1f}k"
    if abs(v) >= 10:
        return f"{v:.1f}"
    return f"{v:.2f}"


def _short_kpi_title(title: str) -> str:
    """缩短 KPI 卡标题（≤ 8 汉字/16 字符）"""
    if not title:
        return "核心指标"
    t = str(title).strip()
    if len(t) > 16:
        t = t[:14] + "…"
    return t


def _safe_delta(w) -> float:
    """提取 widget 的趋势值（change_rate），找不到返回 0"""
    try:
        md = getattr(w, "metadata", None) or {}
        if isinstance(md, dict):
            for k in ("change_rate", "trend", "delta", "change"):
                v = md.get(k)
                if isinstance(v, (int, float)):
                    return float(v)
        cfg = getattr(w, "chart_config", None) or {}
        data = cfg.get("data") if isinstance(cfg, dict) else None
        if isinstance(data, list) and len(data) >= 2 and isinstance(data[0], (int, float)) and isinstance(data[-1], (int, float)):
            first, last = float(data[0]), float(data[-1])
            if first != 0:
                return round((last - first) / abs(first) * 100, 1)
    except Exception:
        pass
    return 0.0


# ============================================================
# 安全访问辅助（兼容 AnalysisPackage 对象和 dict）
# ============================================================

def _safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    """安全获取属性（兼容对象和 dict）"""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _safe_id(pkg: AnalysisPackage) -> str:
    """安全获取 package id"""
    return str(_safe_get(pkg, "id", ""))


class _DictWrapper:
    """轻量 dict → object 适配器，让 WidgetGenerator 兼容后端 API 返回的 dict"""
    __slots__ = ("_d",)

    def __init__(self, d: Dict[str, Any]):
        self._d = d

    def __getattr__(self, name: str) -> Any:
        if name == "_d":
            return object.__getattribute__(self, "_d")
        return self._d.get(name)

    def get(self, key: str, default: Any = None) -> Any:
        return self._d.get(key, default)
