"""
Semantic Classification Engine —— Rule Engine + Strategy Pattern

核心职责：
- 根据 AnalysisPackage 的 analysis_type、FindingCategory、chart_type 等
- 自动判断 Widget 的：visual_role、analytical_role、business_topic、priority_level、preferred_size、recommended_section

设计原则：
- 不使用大量 if-else
- 采用 Rule Engine（声明式规则表）+ Strategy Pattern（分类策略）
- 新增 analysis_type 时只需添加一条规则，无需修改引擎代码
- 规则可组合、可覆盖、可扩展
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field

from src.dashboard.semantic_models import (
    BusinessTopic, VisualRole, AnalyticalRole,
    PriorityLevel, PreferredSize, RecommendedSection,
    InteractionCapability,
)
from src.domain.business_finding import FindingCategory, Severity, Direction


# ============================================================
# Classification Rule —— 声明式规则单元
# ============================================================

@dataclass
class ClassificationRule:
    """分类规则——声明式配置，不包含逻辑分支

    每条规则定义一个 analysis_type 到语义属性的映射。
    规则之间不冲突——同一 analysis_type 只有一条主规则。
    """
    # 匹配条件
    analysis_type: str = ""                          # 匹配的 analysis_type
    finding_category: FindingCategory = FindingCategory.UNKNOWN  # 匹配的 FindingCategory（可选）
    chart_type: str = ""                             # 匹配的 chart_type（可选）

    # 分类结果
    business_topic: BusinessTopic = BusinessTopic.GENERAL
    visual_role: VisualRole = VisualRole.RANKING
    analytical_role: AnalyticalRole = AnalyticalRole.MONITOR
    priority_level: PriorityLevel = PriorityLevel.MAJOR
    preferred_size: PreferredSize = PreferredSize.MEDIUM
    recommended_section: RecommendedSection = RecommendedSection.MAIN_ANALYSIS
    business_purpose_template: str = ""              # 业务目的模板（支持 {metric}、{dimension} 占位符）
    interaction_capabilities: List[InteractionCapability] = field(default_factory=list)

    # 优先级覆盖规则（当 importance_score > threshold 时升级）
    hero_threshold: float = 0.85                     # importance_score > 此值 → Hero
    major_threshold: float = 0.55                    # importance_score > 此值 → Major


# ============================================================
# Rule Registry —— 规则注册表
# ============================================================

CLASSIFICATION_RULES: Dict[str, ClassificationRule] = {
    # ===== 增长分析 =====
    "growth_analysis": ClassificationRule(
        analysis_type="growth_analysis",
        finding_category=FindingCategory.GROWTH,
        business_topic=BusinessTopic.GROWTH,
        visual_role=VisualRole.PRIMARY_TREND,
        analytical_role=AnalyticalRole.MONITOR,
        priority_level=PriorityLevel.MAJOR,
        preferred_size=PreferredSize.LARGE,
        recommended_section=RecommendedSection.MAIN_ANALYSIS,
        business_purpose_template="监控{metric}变化趋势，发现增长与衰退信号",
        interaction_capabilities=[
            InteractionCapability.TIME_RANGE,
            InteractionCapability.DRILL_DOWN,
            InteractionCapability.HOVER_DETAIL,
        ],
        hero_threshold=0.85,
    ),

    # ===== 排名分析 =====
    "ranking_analysis": ClassificationRule(
        analysis_type="ranking_analysis",
        finding_category=FindingCategory.RANKING,
        business_topic=BusinessTopic.SALES,
        visual_role=VisualRole.RANKING,
        analytical_role=AnalyticalRole.COMPARE,
        priority_level=PriorityLevel.MAJOR,
        preferred_size=PreferredSize.LARGE,
        recommended_section=RecommendedSection.COMPARISON,
        business_purpose_template="识别{dimension}维度中{metric}的高低排名与集中度",
        interaction_capabilities=[
            InteractionCapability.CROSS_FILTER,
            InteractionCapability.DRILL_DOWN,
            InteractionCapability.HOVER_DETAIL,
        ],
        hero_threshold=0.80,
    ),

    # ===== 结构分析 =====
    "structure_analysis": ClassificationRule(
        analysis_type="structure_analysis",
        finding_category=FindingCategory.STRUCTURE,
        business_topic=BusinessTopic.GENERAL,
        visual_role=VisualRole.COMPOSITION,
        analytical_role=AnalyticalRole.EXPLAIN,
        priority_level=PriorityLevel.MAJOR,
        preferred_size=PreferredSize.MEDIUM,
        recommended_section=RecommendedSection.COMPARISON,
        business_purpose_template="揭示{dimension}在{metric}中的占比构成与结构差异",
        interaction_capabilities=[
            InteractionCapability.DIMENSION_SWITCH,
            InteractionCapability.HOVER_DETAIL,
        ],
    ),

    # ===== 集中度分析 =====
    "concentration_analysis": ClassificationRule(
        analysis_type="concentration_analysis",
        finding_category=FindingCategory.CONCENTRATION,
        business_topic=BusinessTopic.RISK,
        visual_role=VisualRole.CONCENTRATION,
        analytical_role=AnalyticalRole.EVALUATE,
        priority_level=PriorityLevel.MINOR,
        preferred_size=PreferredSize.MEDIUM,
        recommended_section=RecommendedSection.DETAIL,
        business_purpose_template="评估{metric}的集中度风险（CR3/CR5/HHI），识别帕累托效应",
        interaction_capabilities=[InteractionCapability.HOVER_DETAIL],
    ),

    # ===== 分布分析 =====
    "distribution_analysis": ClassificationRule(
        analysis_type="distribution_analysis",
        finding_category=FindingCategory.DISTRIBUTION,
        business_topic=BusinessTopic.GENERAL,
        visual_role=VisualRole.DISTRIBUTION,
        analytical_role=AnalyticalRole.EXPLAIN,
        priority_level=PriorityLevel.MINOR,
        preferred_size=PreferredSize.SMALL,
        recommended_section=RecommendedSection.DETAIL,
        business_purpose_template="展示{metric}的分布特征（均值/中位数/偏度/峰度）",
        interaction_capabilities=[InteractionCapability.HOVER_DETAIL],
    ),

    # ===== 相关性分析 =====
    "correlation_analysis": ClassificationRule(
        analysis_type="correlation_analysis",
        finding_category=FindingCategory.CORRELATION,
        business_topic=BusinessTopic.GENERAL,
        visual_role=VisualRole.CORRELATION,
        analytical_role=AnalyticalRole.DISCOVER,
        priority_level=PriorityLevel.MINOR,
        preferred_size=PreferredSize.SMALL,
        recommended_section=RecommendedSection.DETAIL,
        business_purpose_template="发现{metric}与{dimension}之间的相关关系",
        interaction_capabilities=[InteractionCapability.HOVER_DETAIL],
    ),

    # ===== 对比分析 =====
    "comparison_analysis": ClassificationRule(
        analysis_type="comparison_analysis",
        finding_category=FindingCategory.COMPARISON,
        business_topic=BusinessTopic.GENERAL,
        visual_role=VisualRole.COMPARISON,
        analytical_role=AnalyticalRole.COMPARE,
        priority_level=PriorityLevel.MAJOR,
        preferred_size=PreferredSize.LARGE,
        recommended_section=RecommendedSection.COMPARISON,
        business_purpose_template="对比不同{dimension}的{metric}差异与提升度",
        interaction_capabilities=[
            InteractionCapability.CROSS_FILTER,
            InteractionCapability.DIMENSION_SWITCH,
            InteractionCapability.HOVER_DETAIL,
        ],
    ),

    # ===== 地理空间分析 =====
    "geo_analysis": ClassificationRule(
        analysis_type="geo_analysis",
        finding_category=FindingCategory.GEO,
        business_topic=BusinessTopic.OPERATION,
        visual_role=VisualRole.GEOGRAPHIC,
        analytical_role=AnalyticalRole.DISCOVER,
        priority_level=PriorityLevel.MAJOR,
        preferred_size=PreferredSize.EXTRA_LARGE,
        recommended_section=RecommendedSection.MAIN_ANALYSIS,
        business_purpose_template="识别{metric}在区域维度的地理分布差异与热点",
        interaction_capabilities=[
            InteractionCapability.DRILL_DOWN,
            InteractionCapability.CROSS_FILTER,
            InteractionCapability.CLICK_LINK,
        ],
        hero_threshold=0.80,
    ),

    # ===== 异常分析 =====
    "anomaly_analysis": ClassificationRule(
        analysis_type="anomaly_analysis",
        finding_category=FindingCategory.ANOMALY,
        business_topic=BusinessTopic.RISK,
        visual_role=VisualRole.WARNING,
        analytical_role=AnalyticalRole.DISCOVER,
        priority_level=PriorityLevel.MAJOR,
        preferred_size=PreferredSize.MEDIUM,
        recommended_section=RecommendedSection.MONITORING,
        business_purpose_template="检测{metric}中的异常离群点，发出预警信号",
        interaction_capabilities=[
            InteractionCapability.HOVER_DETAIL,
            InteractionCapability.CLICK_LINK,
        ],
    ),

    # ===== 占比分析 =====
    "proportion_analysis": ClassificationRule(
        analysis_type="proportion_analysis",
        finding_category=FindingCategory.PROPORTION,
        business_topic=BusinessTopic.GENERAL,
        visual_role=VisualRole.COMPOSITION,
        analytical_role=AnalyticalRole.EXPLAIN,
        priority_level=PriorityLevel.MINOR,
        preferred_size=PreferredSize.MEDIUM,
        recommended_section=RecommendedSection.COMPARISON,
        business_purpose_template="揭示各部分在{metric}总体中的占比构成",
        interaction_capabilities=[InteractionCapability.HOVER_DETAIL],
    ),

    # ===== 留存分析 =====
    "retention_analysis": ClassificationRule(
        analysis_type="retention_analysis",
        finding_category=FindingCategory.RETENTION,
        business_topic=BusinessTopic.CUSTOMER,
        visual_role=VisualRole.OVERVIEW_METRIC,
        analytical_role=AnalyticalRole.MONITOR,
        priority_level=PriorityLevel.MAJOR,
        preferred_size=PreferredSize.MEDIUM,
        recommended_section=RecommendedSection.OVERVIEW,
        business_purpose_template="监控客户留存率、复购频次与客户忠诚度变化",
        interaction_capabilities=[
            InteractionCapability.TIME_RANGE,
            InteractionCapability.HOVER_DETAIL,
        ],
    ),

    # ===== 风险分析 =====
    "risk_analysis": ClassificationRule(
        analysis_type="risk_analysis",
        finding_category=FindingCategory.RISK,
        business_topic=BusinessTopic.RISK,
        visual_role=VisualRole.WARNING,
        analytical_role=AnalyticalRole.EVALUATE,
        priority_level=PriorityLevel.MAJOR,
        preferred_size=PreferredSize.MEDIUM,
        recommended_section=RecommendedSection.MONITORING,
        business_purpose_template="评估{metric}相关风险等级与潜在损失",
        interaction_capabilities=[InteractionCapability.HOVER_DETAIL],
    ),
}

# 默认规则——analysis_type 未在规则表中时使用
DEFAULT_CLASSIFICATION_RULE = ClassificationRule(
    analysis_type="*",
    business_topic=BusinessTopic.GENERAL,
    visual_role=VisualRole.RANKING,
    analytical_role=AnalyticalRole.MONITOR,
    priority_level=PriorityLevel.MINOR,
    preferred_size=PreferredSize.MEDIUM,
    recommended_section=RecommendedSection.DETAIL,
    business_purpose_template="展示{metric}分析结果",
    interaction_capabilities=[InteractionCapability.HOVER_DETAIL],
)


# ============================================================
# Strategy Pattern —— 分类策略接口
# ============================================================

class ClassificationStrategy:
    """分类策略——决定如何根据 AnalysisPackage 属性选择 ClassificationRule

    策略组合：
    1. PrimaryStrategy：基于 analysis_type 精确匹配
    2. CategoryFallbackStrategy：基于 FindingCategory 降级匹配
    3. ChartTypeFallbackStrategy：基于 chart_type 降级匹配
    """

    def classify(self, analysis_type: str, finding_category: str,
                 chart_type: str, importance_score: float) -> ClassificationRule:
        """主分类入口——按优先级依次尝试匹配策略"""
        # Strategy 1: analysis_type 精确匹配
        rule = self._match_by_analysis_type(analysis_type)
        if rule:
            return self._apply_importance_override(rule, importance_score)

        # Strategy 2: FindingCategory 降级匹配
        rule = self._match_by_category(finding_category)
        if rule:
            return self._apply_importance_override(rule, importance_score)

        # Strategy 3: chart_type 降级匹配
        rule = self._match_by_chart_type(chart_type)
        if rule:
            return self._apply_importance_override(rule, importance_score)

        # Fallback: 默认规则
        return DEFAULT_CLASSIFICATION_RULE

    def _match_by_analysis_type(self, analysis_type: str) -> Optional[ClassificationRule]:
        """Strategy 1: analysis_type 精确匹配"""
        # 尝试完整名
        if analysis_type in CLASSIFICATION_RULES:
            return CLASSIFICATION_RULES[analysis_type]
        # 尝试加后缀
        if f"{analysis_type}_analysis" in CLASSIFICATION_RULES:
            return CLASSIFICATION_RULES[f"{analysis_type}_analysis"]
        # 尝试去掉后缀
        base = analysis_type.replace("_analysis", "")
        if base in CLASSIFICATION_RULES:
            return CLASSIFICATION_RULES[base]
        if f"{base}_analysis" in CLASSIFICATION_RULES:
            return CLASSIFICATION_RULES[f"{base}_analysis"]
        return None

    def _match_by_category(self, finding_category: str) -> Optional[ClassificationRule]:
        """Strategy 2: FindingCategory 降级匹配"""
        # 将 category 值转为 analysis_type 模式匹配
        category_to_type = {
            "growth": "growth_analysis",
            "ranking": "ranking_analysis",
            "comparison": "comparison_analysis",
            "concentration": "concentration_analysis",
            "distribution": "distribution_analysis",
            "correlation": "correlation_analysis",
            "anomaly": "anomaly_analysis",
            "structure": "structure_analysis",
            "proportion": "proportion_analysis",
            "geo": "geo_analysis",
            "retention": "retention_analysis",
            "risk": "risk_analysis",
        }
        mapped_type = category_to_type.get(finding_category)
        if mapped_type and mapped_type in CLASSIFICATION_RULES:
            return CLASSIFICATION_RULES[mapped_type]
        return None

    def _match_by_chart_type(self, chart_type: str) -> Optional[ClassificationRule]:
        """Strategy 3: chart_type 降级匹配"""
        chart_to_visual = {
            "line": ClassificationRule(
                analysis_type="*",
                visual_role=VisualRole.PRIMARY_TREND,
                analytical_role=AnalyticalRole.MONITOR,
                preferred_size=PreferredSize.LARGE,
                business_purpose_template="展示{metric}随时间的变化趋势",
            ),
            "bar": ClassificationRule(
                analysis_type="*",
                visual_role=VisualRole.RANKING,
                analytical_role=AnalyticalRole.COMPARE,
                preferred_size=PreferredSize.MEDIUM,
                business_purpose_template="对比各{dimension}的{metric}差异",
            ),
            "pie": ClassificationRule(
                analysis_type="*",
                visual_role=VisualRole.COMPOSITION,
                analytical_role=AnalyticalRole.EXPLAIN,
                preferred_size=PreferredSize.MEDIUM,
                business_purpose_template="揭示{dimension}的占比构成",
            ),
            "scatter": ClassificationRule(
                analysis_type="*",
                visual_role=VisualRole.CORRELATION,
                analytical_role=AnalyticalRole.DISCOVER,
                preferred_size=PreferredSize.SMALL,
                business_purpose_template="发现{metric}与{dimension}的关联关系",
            ),
            "map": ClassificationRule(
                analysis_type="*",
                visual_role=VisualRole.GEOGRAPHIC,
                analytical_role=AnalyticalRole.DISCOVER,
                preferred_size=PreferredSize.EXTRA_LARGE,
                business_purpose_template="展示{metric}的地理分布",
            ),
        }
        return chart_to_visual.get(chart_type)

    def _apply_importance_override(self, rule: ClassificationRule,
                                    importance_score: float) -> ClassificationRule:
        """根据 importance_score 覆盖 priority_level 和 preferred_size"""
        # 根据规则中的阈值升级
        if importance_score >= rule.hero_threshold:
            rule.priority_level = PriorityLevel.HERO
            # Hero 通常升级尺寸
            if rule.preferred_size == PreferredSize.MEDIUM:
                rule.preferred_size = PreferredSize.LARGE
            elif rule.preferred_size == PreferredSize.SMALL:
                rule.preferred_size = PreferredSize.MEDIUM
        elif importance_score >= rule.major_threshold:
            rule.priority_level = PriorityLevel.MAJOR
        else:
            rule.priority_level = PriorityLevel.MINOR

        return rule


# ============================================================
# Business Topic Strategy —— 业务主题推断
# ============================================================

class BusinessTopicStrategy:
    """业务主题推断策略——从 AnalysisPackage 属性推断 BusinessTopic

    策略组合：
    1. 从 finding_category 直接映射
    2. 从 metric 关键词推断
    3. 从 dimension 关键词推断
    """

    # metric → BusinessTopic 关键词映射
    METRIC_KEYWORD_MAP: Dict[str, BusinessTopic] = {
        "销售": BusinessTopic.SALES,
        "营收": BusinessTopic.FINANCE,
        "收入": BusinessTopic.FINANCE,
        "利润": BusinessTopic.FINANCE,
        "成本": BusinessTopic.FINANCE,
        "客户": BusinessTopic.CUSTOMER,
        "用户": BusinessTopic.CUSTOMER,
        "留存": BusinessTopic.CUSTOMER,
        "复购": BusinessTopic.CUSTOMER,
        "产品": BusinessTopic.PRODUCT,
        "效率": BusinessTopic.EFFICIENCY,
        "质量": BusinessTopic.QUALITY,
        "增长": BusinessTopic.GROWTH,
        "风险": BusinessTopic.RISK,
    }

    def infer(self, metric: str, dimension: str, analysis_type: str) -> BusinessTopic:
        """推断 BusinessTopic"""
        # Strategy 1: 从 ClassificationRule 获取
        strategy = ClassificationStrategy()
        rule = strategy._match_by_analysis_type(analysis_type)
        if rule and rule.business_topic != BusinessTopic.GENERAL:
            return rule.business_topic

        # Strategy 2: 从 metric 关键词推断
        for kw, topic in self.METRIC_KEYWORD_MAP.items():
            if kw in metric.lower():
                return topic

        # Strategy 3: 从 dimension 关键词推断
        dim_lower = dimension.lower() if dimension else ""
        if any(kw in dim_lower for kw in ["省", "市", "地区", "区域", "region", "city", "geo"]):
            return BusinessTopic.OPERATION

        return BusinessTopic.GENERAL


# ============================================================
# Recommended Section Strategy —— 推荐区域推断
# ============================================================

class RecommendedSectionStrategy:
    """推荐区域推断策略

    根据 Widget 的 visual_role 和 priority_level 决定它应该放在 Dashboard 的哪个区域。
    """

    # visual_role + priority_level → recommended_section 映射
    SECTION_MAP: Dict[Tuple[str, str], RecommendedSection] = {
        # Hero + overview_metric → overview 区域
        ("overview_metric", "hero"): RecommendedSection.OVERVIEW,
        ("overview_metric", "major"): RecommendedSection.OVERVIEW,
        ("overview_metric", "minor"): RecommendedSection.DETAIL,

        # Hero + primary_trend → main_analysis 区域
        ("primary_trend", "hero"): RecommendedSection.MAIN_ANALYSIS,
        ("primary_trend", "major"): RecommendedSection.MAIN_ANALYSIS,
        ("primary_trend", "minor"): RecommendedSection.DETAIL,

        # ranking/comparison → comparison 区域
        ("ranking", "hero"): RecommendedSection.MAIN_ANALYSIS,
        ("ranking", "major"): RecommendedSection.COMPARISON,
        ("ranking", "minor"): RecommendedSection.DETAIL,
        ("comparison", "hero"): RecommendedSection.MAIN_ANALYSIS,
        ("comparison", "major"): RecommendedSection.COMPARISON,
        ("comparison", "minor"): RecommendedSection.DETAIL,

        # composition → comparison 区域
        ("composition", "hero"): RecommendedSection.MAIN_ANALYSIS,
        ("composition", "major"): RecommendedSection.COMPARISON,
        ("composition", "minor"): RecommendedSection.DETAIL,

        # warning → monitoring 区域
        ("warning", "hero"): RecommendedSection.MONITORING,
        ("warning", "major"): RecommendedSection.MONITORING,
        ("warning", "minor"): RecommendedSection.DETAIL,

        # geographic → main_analysis 区域
        ("geographic", "hero"): RecommendedSection.MAIN_ANALYSIS,
        ("geographic", "major"): RecommendedSection.MAIN_ANALYSIS,
        ("geographic", "minor"): RecommendedSection.DETAIL,

        # detail → detail 区域
        ("detail", "hero"): RecommendedSection.DETAIL,
        ("detail", "major"): RecommendedSection.DETAIL,
        ("detail", "minor"): RecommendedSection.DETAIL,
    }

    def infer(self, visual_role: VisualRole, priority_level: PriorityLevel) -> RecommendedSection:
        """推断推荐区域"""
        key = (visual_role.value, priority_level.value)
        return self.SECTION_MAP.get(key, RecommendedSection.DETAIL)


# ============================================================
# Business Purpose Builder —— 业务目的模板填充
# ============================================================

class BusinessPurposeBuilder:
    """业务目的构建器——从模板和 AnalysisPackage 属性生成 business_purpose"""

    def build(self, template: str, metric: str, dimension: str,
              entity: str = "") -> str:
        """填充 business_purpose_template"""
        purpose = template
        purpose = purpose.replace("{metric}", metric or "指标")
        purpose = purpose.replace("{dimension}", dimension or "维度")
        purpose = purpose.replace("{entity}", entity or "实体")
        return purpose


# ============================================================
# Semantic Classifier —— 统一分类入口
# ============================================================

class SemanticClassifier:
    """语义分类引擎——将 AnalysisPackage 属性分类为 SemanticWidget 的语义属性

    使用 Rule Engine + Strategy Pattern 组合：
    1. ClassificationStrategy：匹配 ClassificationRule
    2. BusinessTopicStrategy：推断 BusinessTopic
    3. RecommendedSectionStrategy：推断 RecommendedSection
    4. BusinessPurposeBuilder：填充 business_purpose
    """

    def __init__(self):
        self._classification_strategy = ClassificationStrategy()
        self._topic_strategy = BusinessTopicStrategy()
        self._section_strategy = RecommendedSectionStrategy()
        self._purpose_builder = BusinessPurposeBuilder()

    def classify(
        self,
        analysis_type: str,
        finding_category: str,
        chart_type: str,
        importance_score: float,
        metric: str,
        dimension: str,
        entity: str = "",
    ) -> Dict[str, Any]:
        """统一分类入口——返回所有语义属性

        Returns:
            {
                "business_topic": BusinessTopic,
                "visual_role": VisualRole,
                "analytical_role": AnalyticalRole,
                "priority_level": PriorityLevel,
                "preferred_size": PreferredSize,
                "recommended_section": RecommendedSection,
                "business_purpose": str,
                "interaction_capabilities": List[InteractionCapability],
            }
        """
        # Step 1: 匹配 ClassificationRule
        rule = self._classification_strategy.classify(
            analysis_type, finding_category, chart_type, importance_score
        )

        # Step 2: 推断 BusinessTopic（优先用规则，降级用关键词）
        business_topic = self._topic_strategy.infer(metric, dimension, analysis_type)
        # 如果规则中的 topic 更精确，优先使用
        if rule.business_topic != BusinessTopic.GENERAL:
            business_topic = rule.business_topic

        # Step 3: 推断 RecommendedSection（优先用规则，降级用策略）
        recommended_section = self._section_strategy.infer(
            rule.visual_role, rule.priority_level
        )
        # 如果规则中已指定 section，优先使用
        if rule.recommended_section != RecommendedSection.DETAIL:
            recommended_section = rule.recommended_section

        # Step 4: 填充 business_purpose
        business_purpose = self._purpose_builder.build(
            rule.business_purpose_template, metric, dimension, entity
        )

        return {
            "business_topic": business_topic,
            "visual_role": rule.visual_role,
            "analytical_role": rule.analytical_role,
            "priority_level": rule.priority_level,
            "preferred_size": rule.preferred_size,
            "recommended_section": recommended_section,
            "business_purpose": business_purpose,
            "interaction_capabilities": rule.interaction_capabilities,
        }
