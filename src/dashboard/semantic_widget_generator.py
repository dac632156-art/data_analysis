"""
Semantic Widget Generator —— AnalysisPackage → SemanticWidget[] 转换器

核心职责：
- 将 AnalysisPackage 列表转换为具有完整业务语义的 SemanticWidget 列表
- 每个 Widget 都有明确的 business_purpose、visual_role、analytical_role
- Widget 之间有语义关系（related_widgets）
- importance_score 是 0-1 浮点数，综合 5 维度加权

与旧 WidgetGenerator 的区别：
- WidgetGenerator: AnalysisPackage → Widget（纯视觉数据容器）
- SemanticWidgetGenerator: AnalysisPackage → SemanticWidget（业务语义数据容器）

禁止：
- 重新读取 DataFrame
- 重新计算指标
- 重新执行 Template
- 生成新的 BusinessFinding
- 修改 AnalysisPackage 数据
- 负责 Dashboard 布局
- 负责 Grid 排版
- 负责 React 页面
- 负责交互逻辑

所有信息只从 AnalysisPackage 的已有字段中提取。
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.analysis_templates.base import AnalysisPackage

from src.dashboard.semantic_models import (
    SemanticWidget, BusinessTopic, VisualRole, AnalyticalRole,
    PriorityLevel, PreferredSize, RecommendedSection,
    InteractionCapability, ImportanceDetail,
    SemanticFilter, SemanticDataSource,
    DependencyGraph,
)
from src.dashboard.semantic_rules import SemanticClassifier
from src.dashboard.importance_engine import ImportanceScoreEngine
from src.dashboard.relationship_engine import RelationshipEngine
from src.domain.business_finding import (
    Severity, Direction, FindingCategory,
)


# ============================================================
# Semantic Widget Generator
# ============================================================

class SemanticWidgetGenerator:
    """将 AnalysisPackage 转换为 SemanticWidget

    使用方式：
        gen = SemanticWidgetGenerator()
        widgets = gen.generate(packages)

    流程：
    1. 遍历每个 AnalysisPackage
    2. 提取业务属性（analysis_type, metric, dimension, findings）
    3. 计算 importance_score (0-1) + ImportanceDetail
    4. 语义分类（business_topic, visual_role, analytical_role 等）
    5. 构建 chart_config 和 data_source
    6. 构建 SemanticWidget
    7. 建立 Widget 间关系（RelationshipEngine）
    8. 返回 SemanticWidget[] 列表
    """

    def __init__(self):
        self._classifier = SemanticClassifier()
        self._importance_engine = ImportanceScoreEngine()
        self._relationship_engine = RelationshipEngine()
        self._widgets: List[SemanticWidget] = []

    # ============================================================
    # 主入口
    # ============================================================

    def generate(self, packages: List[Any]) -> List[SemanticWidget]:
        """将 AnalysisPackage 列表转换为 SemanticWidget 列表

        Args:
            packages: AnalysisPackage 对象列表（或 dict 列表）

        Returns:
            SemanticWidget 列表（已按 importance_score 降序排列，含 Widget 关系）
        """
        self._widgets = []

        for pkg in packages:
            if not self._is_valid_package(pkg):
                continue
            widgets = self._package_to_widgets(pkg)
            self._widgets.extend(widgets)

        # Step 7: 建立 Widget 间关系
        if len(self._widgets) >= 2:
            graph = self._relationship_engine.build_relationships(self._widgets)
            self._widgets = self._relationship_engine.attach_relationships(self._widgets, graph)

        # 按 importance_score 降序排列
        self._widgets.sort(key=lambda w: w.importance_score, reverse=True)
        return list(self._widgets)

    def generate_from_dicts(self, packages: List[Dict[str, Any]]) -> List[SemanticWidget]:
        """dict 版本入口——兼容后端 API 返回的 JSON 序列化 AnalysisPackage"""
        wrapped = [_DictWrapper(p) for p in packages]
        return self.generate(wrapped)

    # ============================================================
    # 单 Package 转换
    # ============================================================

    def _package_to_widgets(self, pkg: Any) -> List[SemanticWidget]:
        """单个 AnalysisPackage → 一个 SemanticWidget"""
        # Step 2: 提取业务属性
        analysis_type = _safe_get(pkg, "analysis_type", "") or ""
        metric = _safe_get(pkg, "metric", "") or ""
        dimension = _safe_get(pkg, "dimension", "") or ""
        findings = _safe_get(pkg, "findings", []) or []

        # 提取 finding_category（从第一个 finding 取）
        finding_category = ""
        if findings:
            cat = _safe_get(findings[0], "category", "")
            finding_category = cat.value if hasattr(cat, "value") else str(cat)

        # 提取 chart_type
        chart_type = self._derive_chart_type(pkg)

        # 提取 entity（从第一个 finding 取）
        entity = ""
        if findings:
            entity = _safe_get(findings[0], "entity", "") or ""

        # Step 3: 计算 importance_score
        importance_score, importance_detail = self._importance_engine.calculate(pkg)

        # Step 4: 语义分类
        classification = self._classifier.classify(
            analysis_type=analysis_type,
            finding_category=finding_category,
            chart_type=chart_type or "",
            importance_score=importance_score,
            metric=metric,
            dimension=dimension,
            entity=entity,
        )

        # Step 5 & 6: 构建 SemanticWidget
        widget = self._build_widget(
            pkg, importance_score, importance_detail, classification
        )

        return [widget]

    def _build_widget(
        self,
        pkg: Any,
        importance_score: float,
        importance_detail: ImportanceDetail,
        classification: Dict[str, Any],
    ) -> SemanticWidget:
        """构建 SemanticWidget（填充所有字段）"""

        # ----- 标识 -----
        title = self._derive_title(pkg)
        description = self._derive_description(pkg)

        # ----- 图表配置 -----
        chart_config = self._extract_chart_config(pkg)

        # ----- 业务语义（从 classification 取） -----
        business_topic = classification["business_topic"]
        visual_role = classification["visual_role"]
        analytical_role = classification["analytical_role"]
        priority_level = classification["priority_level"]
        preferred_size = classification["preferred_size"]
        recommended_section = classification["recommended_section"]
        business_purpose = classification["business_purpose"]
        interaction_capabilities = classification["interaction_capabilities"]

        # ----- 重要性 -----
        # 用引擎重新计算 priority_level（更精确）
        priority_level = self._importance_engine.score_to_priority_level(importance_score)
        preferred_size = self._importance_engine.score_to_preferred_size(
            importance_score, visual_role.value
        )

        # ----- 分析信息 -----
        analysis_type = _safe_get(pkg, "analysis_type", "") or ""
        finding_summary = self._derive_finding_summary(pkg)
        chart_type = self._derive_chart_type(pkg)

        # ----- 筛选器 -----
        filters = self._infer_semantic_filters(pkg, business_purpose)

        # ----- 数据源 -----
        data_source = self._extract_semantic_data_source(pkg)

        # ----- 元数据 -----
        metadata = self._enrich_metadata(pkg, importance_score)

        return SemanticWidget(
            title=title,
            description=description,
            chart_config=chart_config,
            business_topic=business_topic,
            business_purpose=business_purpose,
            visual_role=visual_role,
            analytical_role=analytical_role,
            importance_score=importance_score,
            importance_detail=importance_detail,
            priority_level=priority_level,
            preferred_size=preferred_size,
            recommended_section=recommended_section,
            analysis_type=analysis_type.replace("_analysis", ""),
            finding_summary=finding_summary,
            chart_type=chart_type,
            supported_filters=filters,
            interaction_capabilities=interaction_capabilities,
            data_source=data_source,
            metadata=metadata,
            _raw_package_ref=_safe_id(pkg),
        )

    # ============================================================
    # 字段派生方法
    # ============================================================

    def _derive_title(self, pkg: Any) -> str:
        """派生 Widget 标题"""
        business_question = _safe_get(pkg, "business_question", "") or ""
        metric = _safe_get(pkg, "metric", "") or ""
        dimension = _safe_get(pkg, "dimension", "") or ""

        if business_question:
            q = business_question.rstrip("？?")
            if len(q) <= 20:
                return q
            return q[:18] + "…"

        if metric and dimension:
            return f"{metric} × {dimension}"

        # 从 widget_mapping 取默认标题
        analysis_type = _safe_get(pkg, "analysis_type", "") or ""
        from src.dashboard.widget_mapping import get_widget_config
        config = get_widget_config(analysis_type)
        return str(config.get("default_title", "分析结果"))

    def _derive_description(self, pkg: Any) -> str:
        """派生 Widget 描述"""
        insights = _safe_get(pkg, "insights", []) or []
        if insights:
            first = str(insights[0]).strip()
            return first[:100] if len(first) > 100 else first

        # 从 widget_mapping 取
        analysis_type = _safe_get(pkg, "analysis_type", "") or ""
        from src.dashboard.widget_mapping import get_widget_config
        config = get_widget_config(analysis_type)
        desc = str(config.get("description", ""))
        if desc:
            return desc

        return ""

    def _derive_chart_type(self, pkg: Any) -> Optional[str]:
        """派生图表类型"""
        # 从 widget_mapping 配置取
        analysis_type = _safe_get(pkg, "analysis_type", "") or ""
        from src.dashboard.widget_mapping import get_widget_config
        config = get_widget_config(analysis_type)
        config_chart = config.get("chart_type")
        if config_chart:
            return str(config_chart)

        # 从 chart_data 取第一个
        chart_data = _safe_get(pkg, "chart_data", []) or []
        if chart_data:
            first = chart_data[0]
            if hasattr(first, "chart_type"):
                return str(getattr(first, "chart_type", "bar"))
            if isinstance(first, dict):
                return str(first.get("chart_type", first.get("type", "bar")))

        return None

    def _derive_finding_summary(self, pkg: Any) -> str:
        """派生核心发现摘要"""
        findings = _safe_get(pkg, "findings", []) or []
        for f in findings:
            title = _safe_get(f, "title")
            if title:
                return str(title)[:120]

        insights = _safe_get(pkg, "insights", []) or []
        if insights:
            return str(insights[0])[:120]
        return ""

    # ============================================================
    # Chart Config 提取
    # ============================================================

    def _extract_chart_config(self, pkg: Any) -> Dict[str, Any]:
        """提取图表配置（ECharts option）"""
        charts = _safe_get(pkg, "charts", []) or []
        if not charts:
            charts = _safe_get(pkg, "chart_data", []) or []

        config: Dict[str, Any] = {
            "chart_type": self._derive_chart_type(pkg),
            "data_available": False,
        }

        if not charts:
            return config

        first = charts[0]

        # 1) 优先使用已有的 ECharts option
        option = {}
        if hasattr(first, "option"):
            option = getattr(first, "option", {}) or {}
        elif isinstance(first, dict) and first.get("option"):
            option = first["option"]

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

        return config

    def _build_echarts_option(
        self, chart_type: str, data: List[Any],
        x_label: str = "", y_label: str = "",
    ) -> Dict[str, Any]:
        """从 chart_data 构造最小可用的 ECharts option"""
        if not data:
            return {}

        x_data = []
        y_data = []
        for item in data:
            if isinstance(item, dict):
                if "x" in item and "y" in item:
                    x_data.append(str(item["x"]))
                    y_data.append(float(item["y"]) if item["y"] is not None else 0)
                else:
                    keys = list(item.keys())
                    if len(keys) >= 2:
                        x_data.append(str(item[keys[0]]))
                        try:
                            y_data.append(float(item[keys[1]]))
                        except (TypeError, ValueError):
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
        else:
            series = {"name": y_label or "y", "type": chart_type, "data": y_data}

        return {
            "tooltip": {"trigger": "axis"},
            "grid": {"left": 8, "right": 16, "top": 16, "bottom": 8, "containLabel": True},
            "xAxis": {"type": "category", "data": x_data, "name": x_label},
            "yAxis": {"type": "value", "name": y_label},
            "series": [series],
        }

    # ============================================================
    # Semantic Filter 推断
    # ============================================================

    def _infer_semantic_filters(self, pkg: Any, business_purpose: str) -> List[SemanticFilter]:
        """推断语义化筛选器——带有 business_meaning"""
        filters: List[SemanticFilter] = []
        data_profile = _safe_get(pkg, "data_profile", {}) or {}

        time_cols = data_profile.get("time_cols", [])
        cat_cols = data_profile.get("category_cols", [])

        # 时间维度 → time filter
        if time_cols:
            filters.append(SemanticFilter(
                field="time",
                label="时间范围",
                filter_type="date_range",
                business_meaning="选择要分析的时间区间",
            ))

        # 分类维度 → region / product / category filter
        for col in cat_cols:
            col_lower = str(col).lower()
            field = _classify_category_field(col_lower)
            if field:
                label_map = {
                    "region": "地区",
                    "product": "产品",
                    "channel": "渠道",
                    "category": "分类",
                }
                label = label_map.get(field, str(col))

                # 给 filter 加上业务含义
                purpose_map = {
                    "region": f"选择要对比的地区维度（{business_purpose}）",
                    "product": f"选择要分析的产品维度",
                    "channel": f"选择要分析的渠道维度",
                    "category": f"选择要筛选的分类维度",
                }
                business_meaning = purpose_map.get(field, f"筛选{label}维度")

                existing = {f.field for f in filters}
                if field not in existing:
                    filters.append(SemanticFilter(
                        field=field,
                        label=label,
                        filter_type="dropdown",
                        business_meaning=business_meaning,
                    ))

        return filters[:5]

    # ============================================================
    # Data Source 提取
    # ============================================================

    def _extract_semantic_data_source(self, pkg: Any) -> SemanticDataSource:
        """提取语义化数据源"""
        finding_ids = []
        for f in (_safe_get(pkg, "findings", []) or []):
            fid = _safe_get(f, "id")
            if fid:
                finding_ids.append(str(fid))

        chart_slot = ""
        chart_data = _safe_get(pkg, "chart_data", []) or []
        if chart_data:
            first = chart_data[0]
            if hasattr(first, "slot"):
                chart_slot = str(getattr(first, "slot", ""))
            elif isinstance(first, dict):
                chart_slot = str(first.get("slot", ""))

        table_title = ""
        tables = _safe_get(pkg, "tables", []) or []
        if tables:
            first = tables[0]
            if hasattr(first, "title"):
                table_title = str(getattr(first, "title", ""))
            elif isinstance(first, dict):
                table_title = str(first.get("title", ""))

        kpi_label = ""
        kpis = _safe_get(pkg, "kpis", []) or []
        if kpis:
            first = kpis[0]
            if hasattr(first, "label"):
                kpi_label = str(getattr(first, "label", ""))
            elif isinstance(first, dict):
                kpi_label = str(first.get("label", ""))

        # 数据覆盖度计算
        data_count = 0
        if chart_data:
            first = chart_data[0]
            if hasattr(first, "data"):
                data_count = len(getattr(first, "data", []) or [])
            elif isinstance(first, dict):
                data_count = len(first.get("data", []) or [])
        coverage = min(data_count / 50.0, 1.0) if data_count > 0 else 0.0

        return SemanticDataSource(
            package_id=_safe_id(pkg),
            finding_ids=finding_ids,
            chart_slot=chart_slot,
            table_title=table_title,
            kpi_label=kpi_label,
            data_coverage=coverage,
        )

    # ============================================================
    # Metadata 填充
    # ============================================================

    def _enrich_metadata(self, pkg: Any, importance_score: float) -> Dict[str, Any]:
        """为 SemanticWidget metadata 补充字段"""
        base = {
            "package_id": _safe_id(pkg),
            "template_used": _safe_get(pkg, "template_used", ""),
            "calculator_used": _safe_get(pkg, "calculator_used", ""),
            "confidence": _safe_get(pkg, "confidence", 1.0),
            "importance_score_legacy": round(importance_score * 100),  # 旧版兼容
            "metric": _safe_get(pkg, "metric", ""),
            "dimension": _safe_get(pkg, "dimension", ""),
        }

        # KPI change
        findings = _safe_get(pkg, "findings", []) or []
        kpis = _safe_get(pkg, "kpis", []) or []

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

        # kpi_label
        if kpis:
            first = kpis[0]
            base["kpi_label"] = str(_safe_get(first, "value", ""))
        else:
            base["kpi_label"] = str(round(importance_score * 100))

        # tags
        analysis_type = _safe_get(pkg, "analysis_type", "") or ""
        from src.dashboard.widget_mapping import get_widget_config
        config = get_widget_config(analysis_type)
        base["tags"] = list(config.get("tags", []))

        return base

    # ============================================================
    # 工具方法
    # ============================================================

    @staticmethod
    def _is_valid_package(pkg: Any) -> bool:
        """检查 package 是否包含有效数据"""
        if pkg is None:
            return False
        findings = _safe_get(pkg, "findings", []) or []
        if findings:
            return True
        insights = _safe_get(pkg, "insights", []) or []
        if insights:
            return True
        charts = _safe_get(pkg, "chart_data", []) or []
        if charts:
            return True
        kpis = _safe_get(pkg, "kpis", []) or []
        if kpis:
            return True
        return False


# ============================================================
# 辅助函数
# ============================================================

def _safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    """安全获取属性（兼容对象和 dict）"""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _safe_id(pkg: Any) -> str:
    """安全获取 package id"""
    return str(_safe_get(pkg, "id", ""))


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


class _DictWrapper:
    """轻量 dict → object 适配器"""
    __slots__ = ("_d",)

    def __init__(self, d: Dict[str, Any]):
        self._d = d

    def __getattr__(self, name: str) -> Any:
        if name == "_d":
            return object.__getattribute__(self, "_d")
        return self._d.get(name)

    def get(self, key: str, default: Any = None) -> Any:
        return self._d.get(key, default)
