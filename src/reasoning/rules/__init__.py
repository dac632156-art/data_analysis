"""推理规则包——每个规则独立文件，按需加载"""
from src.reasoning.rules.base_rule import BaseRule

# 规则注册表
from src.reasoning.rules.cross_growth_region import CrossGrowthRegionRule
from src.reasoning.rules.risk_concentration import RiskConcentrationRule

# 待实现的规则骨架
from src.reasoning.rules.cross_ranking_retention import CrossRankingRetentionRule
from src.reasoning.rules.cross_concentration_risk import CrossConcentrationRiskRule
from src.reasoning.rules.root_cause_decline import RootCauseDeclineRule
from src.reasoning.rules.root_cause_anomaly import RootCauseAnomalyRule
from src.reasoning.rules.risk_decline import RiskDeclineRule
from src.reasoning.rules.opportunity_growth import OpportunityGrowthRule
from src.reasoning.rules.opportunity_mid_tail import OpportunityMidTailRule

BUILTIN_RULES = [
    CrossGrowthRegionRule(),
    RiskConcentrationRule(),
    CrossRankingRetentionRule(),
    CrossConcentrationRiskRule(),
    RootCauseDeclineRule(),
    RootCauseAnomalyRule(),
    RiskDeclineRule(),
    OpportunityGrowthRule(),
    OpportunityMidTailRule(),
]