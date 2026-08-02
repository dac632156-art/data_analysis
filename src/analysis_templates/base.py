"""
Analysis Template Engine —— 基类 + 统一数据对象（V3：Domain Model）

V3 升级：
- 引入 src.domain.BusinessFinding 作为唯一业务发现模型
- AnalysisPackage 统一使用 Domain Model
- 旧数据类（BusinessFinding/BusinessMetricsSummary）保留为兼容别名
- 所有 Template 通过 FindingFactory 创建 Finding
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import math
import pandas as pd
from src.column_classifier import ColumnClassifier

# ===== Domain Model 导入 =====
from src.domain.business_finding import (
    BusinessFinding as DomainBusinessFinding,
    EvidenceRef,
    FindingCategory,
    Direction,
    Severity,
)
from src.domain.finding_factory import FindingFactory


# ===== 模板元信息与运行时配置 =====

@dataclass
class TemplateMeta:
    analysis_type: str
    display_name: str
    version: str = "1.0"
    description: str = ""
    supported_algorithms: list = field(default_factory=list)


@dataclass
class TemplateRuntime:
    REQUIRED_SCHEMA: dict = field(default_factory=dict)
    MIN_ROWS: int = 2
    MIN_DISTINCT_VALUES: int = 2
    DERIVED_REQUIREMENTS: dict = field(default_factory=dict)
    FALLBACK: str | None = None


# ===== 基础数据对象（V2 兼容） =====

@dataclass
class KPIItem:
    label: str
    value: str
    change: str = ""
    kpi_type: str = ""


@dataclass
class TableData:
    slot: str = ""  # 与图表一致的定位标识，如 "rfm_segment_summary_table"（排第一，与 ChartData 同构，保证 JSON 中 slot 在 title 之前）
    title: str = ""
    table_type: str = ""
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    chart_config: dict = field(default_factory=dict)  # 高级表格元数据（如群画像总览表的区块/颜色编码）


@dataclass
class ChartData:
    slot: str
    chart_type: str
    title: str
    x: str
    y: str
    data: list = field(default_factory=list)
    color: str = ""   # 分系列着色列名（散点/折线/柱状的簇标签/系列拆分用；留空=单色）
    right_col: str = ""  # 双轴图右轴列名（留空默认"净毛利"，兼容 RFM/COHORT 老场景）
    chart_config: dict = field(default_factory=dict)  # 高级图表元数据（前端按 kind 分支渲染）


@dataclass
class ChartItem:
    slot: str
    chart_type: str
    title: str
    role: str = ""
    option: dict = field(default_factory=dict)
    raw_data: list = field(default_factory=list)  # 原始扁平 rows（ChartData.data），供前端模板库组件使用


# ===== V3 向后兼容别名 =====

# 旧代码中的 BusinessFinding / EvidenceLink / BusinessMetricsSummary 现在指向 Domain Model
BusinessFinding = DomainBusinessFinding
EvidenceLink = EvidenceRef  # EvidenceLink → EvidenceRef 别名
BusinessMetricsSummary = dict  # 简化：dict 即可

# 保留旧 EvidenceLink 接口兼容
class _EvidenceLinkCompat:
    """向后兼容 EvidenceLink —— 映射到 EvidenceRef"""
    def __init__(self, finding_index: int = 0, chart_refs=None, table_refs=None, kpi_refs=None):
        self.finding_index = finding_index
        self.chart_refs = chart_refs or []
        self.table_refs = table_refs or []
        self.kpi_refs = kpi_refs or []


# ===== V3：AnalysisPackage（Domain Model 版） =====

@dataclass
class AnalysisPackage:
    """全系统统一的 Business Analysis Object（Domain Model 版）

    消费方：Dashboard / Professional Report / Reasoning Engine / API
    """

    # ========== Basic ==========
    id: str
    analysis_type: str
    business_question: str
    algorithm: str | None
    dimension: str | None
    metric: str | None

    # ========== Business Metrics ==========
    business_metrics: Dict[str, Any] = field(default_factory=dict)
    derived_metrics: dict = field(default_factory=dict)

    # ========== Domain Findings（V3 核心） ==========
    findings: List[DomainBusinessFinding] = field(default_factory=list)

    # ========== KPIs（V2 兼容） ==========
    kpis: List[KPIItem] = field(default_factory=list)

    # ========== Visualization（V2 兼容） ==========
    chart_data: List[ChartData] = field(default_factory=list)
    charts: List[ChartItem] = field(default_factory=list)
    tables: List[TableData] = field(default_factory=list)

    # ========== Summary（V2 兼容，从 findings 派生） ==========
    insights: List[str] = field(default_factory=list)
    conclusions: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    # ========== Summary Cards（前端/第三方消费：聚合卡片，供直接渲染） ==========
    summary_cards: dict = field(default_factory=dict)

    # ========== Metadata ==========
    metadata: dict = field(default_factory=dict)
    confidence: float = 1.0
    calculator_used: str = ""
    template_used: str = ""
    execution_time: float = 0.0
    can_run: bool = True
    fallback_from: str | None = None
    fallback_reason: str | None = None
    suggestion: str = ""   # 分析失败时的「下一步建议」（按分析类型动态生成，替代通用提示）
    saved_at: str | None = None
    data_profile: dict = field(default_factory=dict)

    # ===== 便捷方法 =====

    def get_findings_by_category(self, category: FindingCategory) -> List[DomainBusinessFinding]:
        return [f for f in self.findings if f.category == category]

    def get_critical_findings(self) -> List[DomainBusinessFinding]:
        return [f for f in self.findings if f.severity in (Severity.CRITICAL, Severity.HIGH)]

    def to_api_dict(self) -> Dict[str, Any]:
        import dataclasses
        d = dataclasses.asdict(self)
        # 将 DomainBusinessFinding 转为 dict
        d["findings"] = [f.to_dict() for f in self.findings]
        d.pop("data_profile", None)
        return d


# ===== 分析模板基类 =====

class AnalysisTemplate(ABC):
    meta: TemplateMeta
    runtime: TemplateRuntime

    def __init__(self):
        self.classifier = ColumnClassifier()
        self._factory = FindingFactory(self.meta.analysis_type)

    @property
    def factory(self) -> FindingFactory:
        return self._factory

    @property
    def spec(self):
        return self.runtime

    def can_run(self, df: pd.DataFrame) -> bool:
        required = self.runtime.REQUIRED_SCHEMA
        dim_type = required.get("dimension_type", "")
        if dim_type == "time":
            if not self._has_time_column(df):
                return False
        elif dim_type == "category":
            if not self._has_category_column(df):
                return False
        metric_type = required.get("metric_type", "")
        if metric_type == "numeric":
            if len(self._get_numeric_columns(df)) < required.get("min_metric", 1):
                return False
        if len(df) < self.runtime.MIN_ROWS:
            return False
        return True

    # ===== V3：核心执行流程 =====

    def execute(self, df: pd.DataFrame, dimension: str | None,
                metric: str | None, algorithm: str | None) -> AnalysisPackage:
        """V3 执行流程：KPI → Table → Chart → Finding → Evidence → Package"""
        import time as _time
        t0 = _time.time()

        # handle duplicate column names to avoid df[col] returning DataFrame
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated()]

        kpis = self.build_kpis(df, dimension, metric, algorithm)
        tables = self.build_tables(df, dimension, metric, algorithm)
        charts = self.build_charts(df, dimension, metric, algorithm)

        # V3：Domain Findings
        findings = self.build_findings(df, dimension, metric, algorithm, kpis, charts)

        # 自动链接证据
        chart_slots = [c.slot for c in charts]
        table_titles = [t.title for t in tables]
        kpi_labels = [k.label for k in kpis]
        findings = FindingFactory.link_all_evidence(findings, chart_slots, table_titles, kpi_labels)

        # 向后兼容：insights / conclusions / recommendations 从 findings 派生
        insights = [f.title for f in findings]
        conclusions = [f.business_meaning for f in findings if f.business_meaning]
        recommendations_list = [f.recommendation for f in findings if f.recommendation]

        biz_metrics = self._build_business_metrics_summary()
        elapsed = round(_time.time() - t0, 3)
        conf = round(sum(f.confidence for f in findings) / len(findings), 2) if findings else 0.5

        return AnalysisPackage(
            id="",
            analysis_type=self.meta.analysis_type,
            business_question="",
            algorithm=algorithm,
            dimension=dimension,
            metric=metric,
            # V3 Domain
            findings=findings,
            business_metrics=biz_metrics,
            # V2 兼容
            kpis=kpis,
            tables=tables,
            chart_data=charts,
            charts=[],
            insights=insights,
            conclusions=conclusions,
            recommendations=recommendations_list,
            confidence=conf,
            calculator_used=self._cache.get("_calculator_used", ""),
            template_used=self.meta.analysis_type,
            execution_time=elapsed,
            metadata={"version": self.meta.version, "display_name": self.meta.display_name},
            can_run=True,
            data_profile=self._get_data_profile(df),
            derived_metrics=self._get_derived_metrics(),
        )

    # ===== V3：抽象方法 =====

    @abstractmethod
    def build_findings(self, df, dimension, metric, algorithm,
                       kpis: List[KPIItem], charts: List[ChartData]) -> List[DomainBusinessFinding]:
        """V3：生成 Domain BusinessFinding 列表（每个 Template 通过 self.factory 创建）"""
        ...

    # ===== V2 抽象方法（保留兼容） =====

    @abstractmethod
    def build_kpis(self, df, dimension, metric, algorithm) -> List[KPIItem]:
        ...

    @abstractmethod
    def build_tables(self, df, dimension, metric, algorithm) -> List[TableData]:
        ...

    @abstractmethod
    def build_charts(self, df, dimension, metric, algorithm) -> List[ChartData]:
        ...

    def build_insights(self, df, dimension, metric, algorithm,
                       kpis: List[KPIItem], charts: List[ChartData]) -> List[str]:
        """V3 降级：从 build_findings 派生（子类无需覆盖）"""
        findings = self.build_findings(df, dimension, metric, algorithm, kpis, charts)
        return [f.title for f in findings]

    def build_conclusion(self, df, dimension, metric, algorithm,
                         insights: List[str]) -> List[str]:
        """V3 降级：从 build_findings 派生（子类无需覆盖）"""
        findings = self._cache.get("_last_findings", [])
        return [f.business_meaning for f in findings if f.business_meaning]

    # ===== 内部方法 =====

    def _build_business_metrics_summary(self) -> Dict[str, Any]:
        m = self._cache.get("metrics")
        if m is None:
            return {}
        if isinstance(m, dict):
            return m
        return {}

    def _get_derived_metrics(self) -> dict:
        m = self._cache.get("metrics")
        if m is None:
            return {}
        if isinstance(m, dict):
            return m
        return {}

    # ===== 工具方法 =====

    @staticmethod
    def _is_nan(val):
        if val is None:
            return True
        try:
            if isinstance(val, float):
                return val != val
            return False
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _safe_divide(a, b, default=None):
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
        result = series.pct_change()
        result.iloc[0] = default
        result = result.replace([float('inf'), float('-inf')], default)
        if default is None:
            result = result.apply(lambda x: None if (x is None or (isinstance(x, float) and x != x)) else x)
        else:
            result = result.fillna(default)
        return result

    @staticmethod
    def _safe_agg(series, func_name, default=None):
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

    def _has_time_column(self, df): return self.classifier.has_time_column(df)
    def _has_category_column(self, df): return self.classifier.has_category_column(df)
    def _get_numeric_columns(self, df): return self.classifier.get_numeric_columns(df)
    def _get_data_profile(self, df):
        result = self.classifier.classify_all(df)
        return {"time_cols": result.get("time_cols", []),
                "category_cols": result.get("category_cols", []),
                "numeric_cols": result.get("numeric_cols", [])}