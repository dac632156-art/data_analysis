"""
Analysis Template Engine —— 基类 + 统一数据对象
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
import pandas as pd
from src.column_classifier import ColumnClassifier


# ===== 统一数据对象 =====

@dataclass
class KPIItem:
    label: str      # "总销售额"
    value: str      # "1,245,000"
    change: str     # "+3.2%" 或 null
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
    """全系统统一数据对象"""
    id: str
    analysis_type: str
    business_question: str
    algorithm: str | None
    dimension: str | None
    metric: str | None
    kpis: List[KPIItem] = field(default_factory=list)
    tables: List[TableData] = field(default_factory=list)
    charts: List[ChartItem] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    conclusions: List[str] = field(default_factory=list)
    can_run: bool = True
    fallback_from: str | None = None
    saved_at: str | None = None
    data_profile: dict = field(default_factory=dict)


@dataclass
class TemplateSpec:
    """每个模板必须声明以下全部字段"""
    analysis_type: str
    display_name: str
    REQUIRED_SCHEMA: dict       # {dimension_type, metric_type, min_dimension, min_metric}
    MIN_ROWS: int = 2
    MIN_DISTINCT_VALUES: int = 2
    DEFAULT_ALGORITHM: str | None = None
    FALLBACK: str | None = None
    OUTPUT_CHARTS: list = field(default_factory=list)
    OUTPUT_TABLES: list = field(default_factory=list)
    OUTPUT_KPIS: list = field(default_factory=list)


# ===== 分析模板基类 =====

class AnalysisTemplate(ABC):
    spec: TemplateSpec

    def __init__(self):
        self.classifier = ColumnClassifier()

    def can_run(self, df: pd.DataFrame) -> bool:
        """基于 spec.REQUIRED_SCHEMA 自动校验"""
        required = self.spec.REQUIRED_SCHEMA

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
        if len(df) < self.spec.MIN_ROWS:
            return False

        return True

    @abstractmethod
    def execute(self, df: pd.DataFrame, dimension: str | None,
                metric: str | None, algorithm: str | None = None) -> AnalysisPackage:
        """子类必须实现——按 spec.OUTPUT_* 严格输出"""
        ...

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
