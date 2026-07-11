"""
Importance Score Engine —— 语义化重要性评分引擎

核心职责：
- 综合多个维度计算 SemanticWidget 的 importance_score (0-1 浮点数)
- 生成 ImportanceDetail 评分明细
- 根据 importance_score 映射 PriorityLevel

与旧 Widget Generator 的 importance_score (0-100) 的区别：
- 旧版：简单的累加规则（severity + business_impact_length + confidence + data_coverage）
- 新版：5 维度加权计算，每个维度独立评分后加权汇总

5 个维度：
1. finding_importance —— BusinessFinding 的重要性
2. metric_value —— Metric 的业务价值
3. analysis_depth —— 分析深度（数据丰富度）
4. attention_priority —— 用户关注度
5. decision_impact —— 决策影响力
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.analysis_templates.base import AnalysisPackage

from src.dashboard.semantic_models import (
    ImportanceDetail, PriorityLevel, PreferredSize,
)
from src.domain.business_finding import Severity


# ============================================================
# Weight Configuration —— 权重配置
# ============================================================

# 5 个维度的默认权重（总和 = 1.0）
DEFAULT_WEIGHTS: Dict[str, float] = {
    "finding_importance": 0.30,     # BusinessFinding 重要性权重 30%
    "metric_value": 0.20,           # Metric 业务价值权重 20%
    "analysis_depth": 0.15,         # 分析深度权重 15%
    "attention_priority": 0.20,     # 用户关注度权重 20%
    "decision_impact": 0.15,        # 决策影响力权重 15%
}


# ============================================================
# Dimension Scorers —— 各维度评分器
# ============================================================

class FindingImportanceScorer:
    """BusinessFinding 重要性评分器

    评分因素：
    - Severity（严重程度）→ 核心权重
    - Confidence（置信度）→ 调整因子
    - Direction（方向性）→ 有明确方向加分
    """

    SEVERITY_SCORES: Dict[str, float] = {
        "critical": 1.0,
        "high": 0.8,
        "medium": 0.6,
        "low": 0.3,
        "info": 0.1,
    }

    def score(self, findings: List[Any]) -> float:
        """计算 findings 的综合重要性评分 0-1"""
        if not findings:
            return 0.2  # 无 finding 时给基础分

        max_score = 0.0
        avg_confidence = 0.0
        has_direction = False

        for f in findings:
            # 获取 severity
            sev = _safe_get(f, "severity", Severity.INFO)
            sev_str = sev.value if hasattr(sev, "value") else str(sev)
            sev_score = self.SEVERITY_SCORES.get(sev_str, 0.1)
            max_score = max(max_score, sev_score)

            # 获取 confidence
            conf = _safe_get(f, "confidence", 0.5)
            avg_confidence += float(conf) if conf else 0.5

            # 获取 direction
            dir_val = _safe_get(f, "direction", None)
            if dir_val and str(dir_val) in ("up", "down"):
                has_direction = True

        avg_confidence /= len(findings)

        # 综合计算：max_severity * confidence_adjustment + direction_bonus
        base = max_score * avg_confidence
        direction_bonus = 0.05 if has_direction else 0.0

        return min(base + direction_bonus, 1.0)


class MetricValueScorer:
    """Metric 业务价值评分器

    评分因素：
    - Metric 关键词（销售额 > 复购率 > HHI）
    - KPI 数量（有 KPI = 核心指标）
    - 数值大小（大数值 = 大业务量）
    """

    # 高价值 metric 关键词
    HIGH_VALUE_KEYWORDS = ["销售", "营收", "收入", "利润", "GMV", "revenue", "sales"]
    MEDIUM_VALUE_KEYWORDS = ["客户", "用户", "复购", "留存", "customer", "retention"]
    LOW_VALUE_KEYWORDS = ["HHI", "CR", "偏度", "峰度", "标准差", "concentration"]

    def score(self, metric: str, kpis: List[Any], findings: List[Any]) -> float:
        """计算 metric 的业务价值评分 0-1"""
        score = 0.5  # 基础分

        # 1. Metric 关键词加分
        metric_str = str(metric).lower() if metric else ""
        for kw in self.HIGH_VALUE_KEYWORDS:
            if kw in metric_str:
                score += 0.3
                break
        else:
            for kw in self.MEDIUM_VALUE_KEYWORDS:
                if kw in metric_str:
                    score += 0.2
                    break
            else:
                for kw in self.LOW_VALUE_KEYWORDS:
                    if kw in metric_str:
                        score -= 0.2
                        break

        # 2. KPI 数量加分（有 KPI = 核心指标）
        kpi_count = len(kpis) if kpis else 0
        if kpi_count >= 2:
            score += 0.15
        elif kpi_count >= 1:
            score += 0.1

        # 3. Finding 中的 value 数值加分
        for f in (findings or []):
            val = _safe_get(f, "value")
            if val is not None and isinstance(val, (int, float)):
                if abs(val) > 1000:
                    score += 0.05
                break

        return min(max(score, 0.0), 1.0)


class AnalysisDepthScorer:
    """分析深度评分器

    评分因素：
    - Chart 数量（图表多 = 分析深）
    - KPI 数量（指标多 = 覆盖广）
    - Finding 数量（发现多 = 分析深）
    - Insights 数量（洞察多 = 丰富）
    """

    def score(self, charts: List[Any], kpis: List[Any],
              findings: List[Any], insights: List[Any]) -> float:
        """计算分析深度评分 0-1"""
        chart_count = len(charts) if charts else 0
        kpi_count = len(kpis) if kpis else 0
        finding_count = len(findings) if findings else 0
        insight_count = len(insights) if insights else 0

        total_data_points = chart_count + kpi_count + finding_count + insight_count

        # 数据丰富度评分
        if total_data_points >= 8:
            depth_score = 1.0
        elif total_data_points >= 5:
            depth_score = 0.8
        elif total_data_points >= 3:
            depth_score = 0.6
        elif total_data_points >= 1:
            depth_score = 0.4
        else:
            depth_score = 0.2

        # Chart 存在加分（有可视化 = 分析更直观）
        if chart_count >= 1:
            depth_score = min(depth_score + 0.1, 1.0)

        return depth_score


class AttentionPriorityScorer:
    """用户关注度评分器

    评分因素：
    - analysis_type 优先级（增长 > 排名 > 结构 > 分布）
    - display_role（main > secondary > sidebar）
    - 是否有 time 维度（时间维度 = 管理层最关心）
    """

    # analysis_type → 注意力优先级
    TYPE_PRIORITY: Dict[str, float] = {
        "growth_analysis": 0.9,
        "ranking_analysis": 0.8,
        "comparison_analysis": 0.7,
        "geo_analysis": 0.7,
        "anomaly_analysis": 0.7,
        "structure_analysis": 0.6,
        "retention_analysis": 0.6,
        "concentration_analysis": 0.5,
        "distribution_analysis": 0.4,
        "correlation_analysis": 0.4,
        "proportion_analysis": 0.4,
        "risk_analysis": 0.6,
    }

    def score(self, analysis_type: str, display_role: str,
              dimension: str, data_profile: Dict[str, Any]) -> float:
        """计算用户关注度评分 0-1"""
        # 1. analysis_type 优先级
        type_score = self.TYPE_PRIORITY.get(analysis_type, 0.4)

        # 2. display_role 加分
        role_scores = {"main": 0.9, "secondary": 0.5, "sidebar": 0.3, "footer": 0.2}
        role_score = role_scores.get(display_role, 0.5)

        # 3. 时间维度加分（管理层最关心时间趋势）
        has_time = False
        time_cols = data_profile.get("time_cols", []) if data_profile else []
        if time_cols or (dimension and _is_time_keyword(dimension)):
            has_time = True

        # 综合计算
        base = (type_score * 0.6 + role_score * 0.4)
        if has_time:
            base = min(base + 0.1, 1.0)

        return base


class DecisionImpactScorer:
    """决策影响力评分器

    评分因素：
    - Severity 为 critical/high = 决策影响大
    - business_impact 内容长度和关键词
    - 有 recommendation = 可执行建议 = 决策关联
    """

    IMPACT_KEYWORDS = ["下降", "增长", "萎缩", "风险", "损失", "机会", "紧迫", "立即", "行动"]

    def score(self, findings: List[Any]) -> float:
        """计算决策影响力评分 0-1"""
        if not findings:
            return 0.2

        # 1. Severity 为 critical/high 加分
        max_impact = 0.0
        for f in findings:
            sev = _safe_get(f, "severity", Severity.INFO)
            sev_str = sev.value if hasattr(sev, "value") else str(sev)
            if sev_str == "critical":
                max_impact = max(max_impact, 1.0)
            elif sev_str == "high":
                max_impact = max(max_impact, 0.8)
            elif sev_str == "medium":
                max_impact = max(max_impact, 0.5)
            elif sev_str == "low":
                max_impact = max(max_impact, 0.3)

        # 2. business_impact 内容加分
        total_impact_len = 0
        impact_keyword_count = 0
        for f in findings:
            impact = _safe_get(f, "business_impact", "")
            if impact:
                total_impact_len += len(str(impact))
                for kw in self.IMPACT_KEYWORDS:
                    if kw in str(impact):
                        impact_keyword_count += 1

        # 3. recommendation 存在加分
        has_recommendation = False
        for f in findings:
            rec = _safe_get(f, "recommendation", "")
            if rec and str(rec).strip():
                has_recommendation = True
                break

        # 综合计算
        base = max_impact * 0.5
        # business_impact 越详细越重要
        if total_impact_len > 80:
            base += 0.3
        elif total_impact_len > 40:
            base += 0.2
        elif total_impact_len > 0:
            base += 0.1
        # 有影响关键词加分
        base += min(impact_keyword_count * 0.05, 0.2)
        # 有可执行建议加分
        if has_recommendation:
            base += 0.1

        return min(max(base, 0.0), 1.0)


# ============================================================
# Importance Score Engine —— 统一计算入口
# ============================================================

class ImportanceScoreEngine:
    """重要性评分引擎——综合 5 维度加权计算 importance_score (0-1)

    使用方式：
        engine = ImportanceScoreEngine()
        score, detail = engine.calculate(pkg)
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self._weights = weights or DEFAULT_WEIGHTS
        self._finding_scorer = FindingImportanceScorer()
        self._metric_scorer = MetricValueScorer()
        self._depth_scorer = AnalysisDepthScorer()
        self._attention_scorer = AttentionPriorityScorer()
        self._decision_scorer = DecisionImpactScorer()

    def calculate(self, pkg: Any) -> tuple:
        """计算 importance_score 和 ImportanceDetail

        Args:
            pkg: AnalysisPackage 对象或 dict

        Returns:
            (importance_score: float, ImportanceDetail)
        """
        # 提取 pkg 属性
        findings = _safe_get(pkg, "findings", []) or []
        kpis = _safe_get(pkg, "kpis", []) or []
        charts = _safe_get(pkg, "chart_data", []) or _safe_get(pkg, "charts", []) or []
        insights = _safe_get(pkg, "insights", []) or []
        metric = _safe_get(pkg, "metric", "") or ""
        dimension = _safe_get(pkg, "dimension", "") or ""
        analysis_type = _safe_get(pkg, "analysis_type", "") or ""
        confidence = _safe_get(pkg, "confidence", 0.5) or 0.5
        data_profile = _safe_get(pkg, "data_profile", {}) or {}

        # 从 widget_mapping 获取 display_role
        from src.dashboard.widget_mapping import get_widget_config
        config = get_widget_config(analysis_type)
        display_role = config.get("display_role", "secondary")

        # 计算各维度评分
        finding_importance = self._finding_scorer.score(findings)
        metric_value = self._metric_scorer.score(metric, kpis, findings)
        analysis_depth = self._depth_scorer.score(charts, kpis, findings, insights)
        attention_priority = self._attention_scorer.score(analysis_type, display_role, dimension, data_profile)
        decision_impact = self._decision_scorer.score(findings)

        # 加权汇总
        weighted_total = (
            finding_importance * self._weights["finding_importance"]
            + metric_value * self._weights["metric_value"]
            + analysis_depth * self._weights["analysis_depth"]
            + attention_priority * self._weights["attention_priority"]
            + decision_impact * self._weights["decision_impact"]
        )

        # 确保在 0-1 范围内
        weighted_total = min(max(weighted_total, 0.0), 1.0)

        # 构建 ImportanceDetail
        detail = ImportanceDetail(
            finding_importance=finding_importance,
            metric_value=metric_value,
            analysis_depth=analysis_depth,
            attention_priority=attention_priority,
            decision_impact=decision_impact,
            weighted_total=weighted_total,
        )

        return (weighted_total, detail)

    def score_to_priority_level(self, score: float) -> PriorityLevel:
        """importance_score → PriorityLevel"""
        if score >= 0.85:
            return PriorityLevel.HERO
        if score >= 0.55:
            return PriorityLevel.MAJOR
        return PriorityLevel.MINOR

    def score_to_preferred_size(self, score: float,
                                 visual_role: str = "") -> PreferredSize:
        """importance_score + visual_role → PreferredSize"""
        from src.dashboard.semantic_models import VisualRole

        # 特殊 role 固定尺寸
        role_size_map = {
            VisualRole.GEOGRAPHIC: PreferredSize.EXTRA_LARGE,
            VisualRole.PRIMARY_TREND: PreferredSize.LARGE,
            VisualRole.OVERVIEW_METRIC: PreferredSize.MEDIUM,
            VisualRole.DETAIL: PreferredSize.SMALL,
            VisualRole.SUMMARY_CARD: PreferredSize.SMALL,
        }

        # 尝试从 visual_role 映射
        try:
            vr = VisualRole(visual_role)
            if vr in role_size_map:
                return role_size_map[vr]
        except (ValueError, KeyError):
            pass

        # 按 importance_score 降级映射
        if score >= 0.85:
            return PreferredSize.EXTRA_LARGE
        if score >= 0.70:
            return PreferredSize.LARGE
        if score >= 0.40:
            return PreferredSize.MEDIUM
        return PreferredSize.SMALL


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


def _is_time_keyword(text: str) -> bool:
    """判断文本是否包含时间关键词"""
    time_keywords = ["时间", "日期", "月", "年", "季度", "周", "time", "date", "month", "year", "quarter"]
    text_lower = text.lower()
    return any(kw in text_lower for kw in time_keywords)
