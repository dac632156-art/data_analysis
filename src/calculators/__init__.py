"""
Business Calculator 层 —— 统一业务计算引擎

提供可复用的原子业务计算方法，与 Template / Report / Dashboard 解耦。

模块结构：
- base.py          BusinessMetrics 数据模型
- growth.py        GrowthCalculator（同比/环比/移动平均/累计/趋势拐点）
- ranking.py       RankingCalculator（TOPN/BottomN/排名/占比/累计占比）
- comparison.py    ComparisonCalculator（差异/差异率/提升度）
- retention.py     RetentionCalculator（复购率/复购客户数/平均频次）
- concentration.py ConcentrationCalculator（帕累托/CR3/CR5/HHI）
- distribution.py  DistributionCalculator（均值/中位数/标准差/偏度/峰度/分箱）
- correlation.py   CorrelationCalculator（Pearson/Spearman/相关性矩阵）
- anomaly.py       AnomalyCalculator（Z-Score/IQR异常检测）

设计原则：
1. 每个 Calculator 只输出 BusinessMetrics，不生成 KPI/Table/Chart/AnalysisPackage
2. 每个 Calculator 提供原子方法，Template 可按需自由组合
3. 不依赖 AI、不访问会话管理、不修改前端
"""

from src.calculators.base import BusinessMetrics
from src.calculators.growth import GrowthCalculator
from src.calculators.ranking import RankingCalculator
from src.calculators.comparison import ComparisonCalculator
from src.calculators.retention import RetentionCalculator
from src.calculators.concentration import ConcentrationCalculator
from src.calculators.distribution import DistributionCalculator
from src.calculators.correlation import CorrelationCalculator
from src.calculators.anomaly import AnomalyCalculator

__all__ = [
    "BusinessMetrics",
    "GrowthCalculator",
    "RankingCalculator",
    "ComparisonCalculator",
    "RetentionCalculator",
    "ConcentrationCalculator",
    "DistributionCalculator",
    "CorrelationCalculator",
    "AnomalyCalculator",
]