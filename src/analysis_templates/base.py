"""
Analysis Template Engine —— 基类 + 统一数据对象

V2 更新：
- TemplateSpec 拆为 TemplateMeta（元信息）+ TemplateRuntime（运行时要求）
- AnalysisTemplate 增加 build_kpis/tables/charts/insights/conclusion 五个抽象方法
- AnalysisPackage 包含完整的多页面共享契约
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
import math
import pandas as pd
from src.column_classifier import ColumnClassifier


# ===== 模板元信息与运行时配置 =====

@dataclass
class TemplateMeta:
    """模板元信息——静态描述，不包含运行时逻辑"""
    analysis_type: str               # "growth_analysis"
    display_name: str                # "增长分析"
    version: str = "1.0"
    description: str = ""
    supported_algorithms: list = field(default_factory=list)  # ["yoy", "mom", "qoq"]


@dataclass
class TemplateRuntime:
    """模板运行时要求——列要求、行数要求、fallback"""
    REQUIRED_SCHEMA: dict = field(default_factory=dict)        # {dimension_type, metric_type, min_dimension, min_metric}
    MIN_ROWS: int = 2
    MIN_DISTINCT_VALUES: int = 2
    DERIVED_REQUIREMENTS: dict = field(default_factory=dict)   # 派生分析所需的基础列组合
    FALLBACK: str | None = None                                 # 降级模板名


# ===== 统一数据对象 =====

@dataclass
class KPIItem:
    label: str      # "总销售额"
    value: str      # "1,245,000"
    change: str     # "+3.2%" 或 ""
    kpi_type: str   # "sum" | "avg" | "count" | "rate" | "change"


@dataclass
class TableData:
    title: str       # "增长率明细"
    table_type: str  # "summary" | "ranking" | "cross" | "growth" | "correlation" | "detail" | "exception"
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)


@dataclass
class ChartData:
    """模板输出的原始图表数据（不含 ECharts option）"""
    slot: str         # "trend" | "growth_rate" | "cumulative" | ...
    chart_type: str   # "line" | "bar" | "pie" | "area" | ...
    title: str        # 图表标题
    x: str            # X 轴列名
    y: str            # Y 轴列名
    data: list = field(default_factory=list)  # [{x: ..., y: ...}, ...]


@dataclass
class ChartItem:
    """渲染后的图表（含 ECharts option）"""
    slot: str         # "trend" | "growth_rate" | "cumulative" | ...
    chart_type: str   # "line" | "bar" | "pie" | "area" | ...
    title: str        # 图表标题
    role: str         # "primary" | "secondary" | "detail"
    option: dict = field(default_factory=dict)  # ECharts option


@dataclass
class AnalysisPackage:
    """全系统统一数据对象——所有页面（Dashboard/Report/CommandCenter）共享的契约"""
    id: str
    analysis_type: str
    business_question: str
    algorithm: str | None
    dimension: str | None
    metric: str | None
    kpis: List[KPIItem] = field(default_factory=list)
    tables: List[TableData] = field(default_factory=list)
    chart_data: List[ChartData] = field(default_factory=list)
    charts: List[ChartItem] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    conclusions: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    can_run: bool = True
    fallback_from: str | None = None
    fallback_reason: str | None = None
    saved_at: str | None = None
    data_profile: dict = field(default_factory=dict)


# ===== 分析模板基类 =====

class AnalysisTemplate(ABC):
    """分析模板基类

    每个子类必须定义：
    - meta: TemplateMeta（元信息）
    - runtime: TemplateRuntime（运行时要求）

    必须实现：
    - can_run(df) → bool
    - execute(df, dim, met, algorithm) → AnalysisPackage
    - build_kpis(...) → List[KPIItem]
    - build_tables(...) → List[TableData]
    - build_charts(...) → List[ChartData]
    - build_insights(...) → List[str]
    - build_conclusion(...) → List[str]

    为保持向后兼容，提供一个 spec 属性访问 TemplateRuntime。
    """

    meta: TemplateMeta
    runtime: TemplateRuntime

    def __init__(self):
        self.classifier = ColumnClassifier()

    @property
    def spec(self):
        """向后兼容：TemplateRuntime 可当 TemplateSpec 用"""
        return self.runtime

    def can_run(self, df: pd.DataFrame) -> bool:
        """基于 runtime.REQUIRED_SCHEMA 自动校验"""
        required = self.runtime.REQUIRED_SCHEMA

        # 1. 检查 dimension_type
        dim_type = required.get("dimension_type", "")
        if dim_type == "time":
            if not self._has_time_column(df):
                return False
        elif dim_type == "category":
            if not self._has_category_column(df):
                return False

        # 2. 检查 metric_type (min_metric 个 numeric 列)
        numeric_cols = self._get_numeric_columns(df)
        min_metric = required.get("min_metric", 1)
        if len(numeric_cols) < min_metric:
            return False

        # 3. 检查行数
        if len(df) < self.runtime.MIN_ROWS:
            return False

        # 4. 派生分析能力检查（如复购率需要 客户ID+订单日期+订单号）
        if self.runtime.DERIVED_REQUIREMENTS:
            req = self.runtime.DERIVED_REQUIREMENTS
            required_cols = req.get("required_columns", [])
            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                return False

        return True

    def execute(self, df: pd.DataFrame, dimension: str | None,
                metric: str | None, algorithm: str | None = None) -> AnalysisPackage:
        """默认 execute：调用五个 build_*() 方法组装 AnalysisPackage。

        子类可以覆盖 execute() 以实现更复杂的计算逻辑，
        但推荐的做法是覆盖 build_*() 五个方法，让 execute() 自动组装。
        """
        # ① 数据计算（子类在 build_* 中完成）
        kpis = self.build_kpis(df, dimension, metric, algorithm)
        tables = self.build_tables(df, dimension, metric, algorithm)
        chart_data_list = self.build_charts(df, dimension, metric, algorithm)
        insights = self.build_insights(df, dimension, metric, algorithm, kpis, chart_data_list)
        conclusions = self.build_conclusion(df, dimension, metric, algorithm, insights)

        return AnalysisPackage(
            id="",
            analysis_type=self.meta.analysis_type,
            business_question="",
            algorithm=algorithm,
            dimension=dimension,
            metric=metric,
            kpis=kpis,
            tables=tables,
            chart_data=chart_data_list,
            charts=[],
            insights=insights,
            conclusions=conclusions,
            recommendations=[],
            metadata={"version": self.meta.version, "display_name": self.meta.display_name},
            can_run=True,
            data_profile=self._get_data_profile(df),
        )

    # ===== build_* 抽象方法 =====

    @abstractmethod
    def build_kpis(self, df: pd.DataFrame, dimension: str | None,
                   metric: str | None, algorithm: str | None) -> List[KPIItem]:
        """构建 KPI 指标列表"""
        ...

    @abstractmethod
    def build_tables(self, df: pd.DataFrame, dimension: str | None,
                     metric: str | None, algorithm: str | None) -> List[TableData]:
        """构建表格数据列表"""
        ...

    @abstractmethod
    def build_charts(self, df: pd.DataFrame, dimension: str | None,
                     metric: str | None, algorithm: str | None) -> List[ChartData]:
        """构建图表数据列表（不含 ECharts option）"""
        ...

    @abstractmethod
    def build_insights(self, df: pd.DataFrame, dimension: str | None,
                       metric: str | None, algorithm: str | None,
                       kpis: List[KPIItem], chart_data: List[ChartData]) -> List[str]:
        """生成洞察文本列表"""
        ...

    @abstractmethod
    def build_conclusion(self, df: pd.DataFrame, dimension: str | None,
                         metric: str | None, algorithm: str | None,
                         insights: List[str]) -> List[str]:
        """生成结论文本列表"""
        ...

    # --- 边界修复工具方法（所有模板共用）---

    @staticmethod
    def _is_nan(val):
        """安全的 NaN 检测，避免 Linux 上 pandas checknull C 扩展崩溃"""
        if val is None:
            return True
        try:
            import math
            if isinstance(val, float):
                return val != val  # IEEE 754: NaN != NaN
            return False
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _safe_divide(a, b, default=None):
        """安全除法：b=0 或结果为 inf/nan 时返回 default"""
        if b == 0 or (isinstance(b, float) and (math.isinf(b) or math.isnan(b))):
            return default
        result = a / b
        if isinstance(result, float) and (math.isinf(result) or math.isnan(result)):
            return default
        if hasattr(result, '__float__'):
            fv = float(result)
            if math.isinf(fv) or math.isnan(fv):
                return default
        return result

    @staticmethod
    def _safe_pct_change(series, default=None):
        """安全环比/同比：首行 NaN 和 inf/nan 替换为 default"""
        result = series.pct_change()
        result.iloc[0] = default
        result = result.replace([float('inf'), float('-inf')], default)
        if default is None:
            # 避免 .notna() 触发 Linux checknull 崩溃
            result = result.apply(lambda x: None if (x is None or (isinstance(x, float) and x != x)) else x)
        else:
            result = result.fillna(default)
        return result

    @staticmethod
    def _safe_agg(series, func_name, default=None):
        """安全聚合：std/skew/kurt 单行或结果为 nan/inf 时返回 default"""
        if len(series) < 2:
            return default
        val = getattr(series, func_name)()
        if isinstance(val, float) and (math.isinf(val) or math.isnan(val)):
            return default
        if hasattr(val, '__float__'):
            fv = float(val)
            if math.isinf(fv) or math.isnan(fv):
                return default
        return val

    # --- helper 方法（委托 ColumnClassifier）---

    def _has_time_column(self, df: pd.DataFrame) -> bool:
        return self.classifier.has_time_column(df)

    def _has_category_column(self, df: pd.DataFrame) -> bool:
        return self.classifier.has_category_column(df)

    def _get_numeric_columns(self, df: pd.DataFrame) -> list:
        return self.classifier.get_numeric_columns(df)

    def _get_data_profile(self, df: pd.DataFrame) -> dict:
        result = self.classifier.classify_all(df)
        return {
            "time_cols": result.get("time_cols", []),
            "category_cols": result.get("category_cols", []),
            "numeric_cols": result.get("numeric_cols", []),
        }
