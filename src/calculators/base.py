"""
Business Calculator Base —— Business Metrics 统一数据模型

职责：
- 定义 Calculator 到 Template 之间的数据契约
- 只包含纯数据，不做任何计算、渲染、AI 调用

设计原则：
- Calculator 输出 BusinessMetrics → Template 消费
- 不包含 KPIItem / TableData / ChartData / AnalysisPackage
- 不包含 ECharts option
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class BusinessMetrics:
    """统一的业务指标输出——所有 Calculator 的唯一输出格式

    这是一个扁平、可序列化的数据模型。每个字段都有明确的业务语义，
    方便 Template 自由组合使用。

    Calculator 只填充它计算的字段，其余留默认值。
    """

    # ========== 元信息 ==========
    calculator: str = ""          # 来源 Calculator 名称，如 "growth"
    algorithm: str = ""           # 使用的算法，如 "yoy" / "mom"
    dimension: Optional[str] = None
    metric: Optional[str] = None

    # ========== 增长类 ==========
    growth_rates: List[Optional[float]] = field(default_factory=list)
    growth_rate_avg: Optional[float] = None
    growth_rate_label: str = ""   # "同比增长率" / "环比变化率" / "季环比变化率"
    cumulative_values: List[float] = field(default_factory=list)
    moving_averages: List[Optional[float]] = field(default_factory=list)
    trend_change_points: List[int] = field(default_factory=list)  # 趋势拐点索引

    # ========== 排名类 ==========
    ranks: List[int] = field(default_factory=list)       # 排名（1-based）
    shares: List[float] = field(default_factory=list)     # 占比（0-1）
    cumulative_shares: List[float] = field(default_factory=list)
    top_n: int = 0
    top_n_labels: List[str] = field(default_factory=list)
    top_n_values: List[float] = field(default_factory=list)
    bottom_n_labels: List[str] = field(default_factory=list)
    bottom_n_values: List[float] = field(default_factory=list)

    # ========== 对比类 ==========
    differences: List[Optional[float]] = field(default_factory=list)
    difference_rates: List[Optional[float]] = field(default_factory=list)
    lifts: List[Optional[float]] = field(default_factory=list)
    global_mean: Optional[float] = None
    global_sum: Optional[float] = None

    # ========== 集中度类 ==========
    cr3: Optional[float] = None           # CR3（前3名集中度）
    cr5: Optional[float] = None           # CR5（前5名集中度）
    hhi: Optional[float] = None           # HHI 指数（0-10000）
    top20_share: Optional[float] = None   # Top20% 的份额
    gini: Optional[float] = None          # 基尼系数
    pareto_ratio: Optional[float] = None  # 帕累托比例（% 的维度贡献 % 的指标）

    # ========== 分布类 ==========
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    skew: Optional[float] = None      # 偏度
    kurtosis: Optional[float] = None   # 峰度
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    q1: Optional[float] = None
    q3: Optional[float] = None
    iqr: Optional[float] = None
    histogram_bins: List[float] = field(default_factory=list)
    histogram_counts: List[int] = field(default_factory=list)

    # ========== 相关性类 ==========
    correlation_coefficient: Optional[float] = None
    correlation_p_value: Optional[float] = None
    correlation_method: str = ""         # "pearson" / "spearman"
    correlation_pairs: List[Dict[str, Any]] = field(default_factory=list)

    # ========== 异常类 ==========
    z_scores: List[Optional[float]] = field(default_factory=list)
    anomaly_indices: List[int] = field(default_factory=list)   # 异常点索引
    anomaly_labels: List[str] = field(default_factory=list)    # 异常点标签
    anomaly_method: str = ""             # "zscore" / "iqr"
    anomaly_threshold: float = 3.0

    # ========== 复购/留存类 ==========
    repeat_purchase_rate: Optional[float] = None
    repeat_customer_count: Optional[int] = None
    total_customer_count: Optional[int] = None
    avg_purchase_frequency: Optional[float] = None

    # ========== 结构化辅助数据 ==========
    labels: List[str] = field(default_factory=list)
    values: List[float] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    # ========== 业务维度评估（业务级推理的原料, Calculator 无关） ==========
    # 各 Calculator 自行约定 dict 内的 key,例如 Growth:
    # {"source": "华东", "contribution": {"华东": 65.0, "华北": 20.0},
    #  "driver": "老客户复购", "quality": "高",
    #  "risk": "区域集中度过高", "sustainability": "一般"}
    business_assessment: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（用于缓存、序列化、日志打印）"""
        import dataclasses
        return dataclasses.asdict(self)