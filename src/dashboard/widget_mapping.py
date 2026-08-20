"""
Widget 类型映射配置 —— analysis_type → Widget 属性

独立配置模块，不依赖 Generator 主逻辑。
新增 analysis type 时只需在此添加一条记录，无需修改 Generator 代码。

设计原则：
- 纯配置，不包含逻辑
- 所有字段有明确默认值
- 支持按需覆盖（analysis_type 匹配时 merge 配置）
"""

from typing import Dict, Any, List


# ============================================================
# analysis_type → Widget 映射表
# ============================================================

ANALYSIS_TO_WIDGET_MAPPING: Dict[str, Dict[str, Any]] = {
    # ===== 增长分析 =====
    "growth_analysis": {
        "widget_type": "chart",
        "business_topic": "增长趋势",
        "chart_type": "line",
        "display_role": "main",
        "default_title": "增长趋势分析",
        "description": "展示核心指标随时间的变化趋势与增长率",
        "tags": ["trend", "growth", "时间序列"],
        "drill_down": True,
        "cross_filter": False,
        # 从 data_profile 中推断 filter 的维度关键词
        "filter_dimension_keywords": ["time", "时间", "日期", "月", "年", "季度"],
    },

    # ===== 排名分析 =====
    "ranking_analysis": {
        "widget_type": "chart",
        "business_topic": "排名对比",
        "chart_type": "bar",
        "display_role": "main",
        "default_title": "排名分析",
        "description": "展示各维度实体的指标排名和占比",
        "tags": ["ranking", "top", "对比"],
        "drill_down": True,
        "cross_filter": True,
        "filter_dimension_keywords": ["category", "分类", "产品", "品牌", "地区", "region"],
    },

    # ===== 结构分析 =====
    "structure_analysis": {
        "widget_type": "chart",
        "business_topic": "结构组成",
        "chart_type": "pie",
        "display_role": "main",
        "default_title": "结构分析",
        "description": "展示各维度在总量中的占比构成",
        "tags": ["structure", "占比", "组成"],
        "drill_down": True,
        "cross_filter": False,
        "filter_dimension_keywords": ["category", "分类", "产品", "地区", "region"],
    },

    # ===== 集中度分析 =====
    "concentration_analysis": {
        "widget_type": "chart",
        "business_topic": "集中度",
        "chart_type": "bar",
        "display_role": "secondary",
        "default_title": "集中度分析",
        "description": "展示 CR3/CR5/HHI 等集中度指标，识别帕累托效应",
        "tags": ["concentration", "pareto", "集中度", "风险"],
        "drill_down": False,
        "cross_filter": False,
        "filter_dimension_keywords": ["category", "分类", "产品"],
    },

    # ===== 分布分析 =====
    "distribution_analysis": {
        "widget_type": "chart",
        "business_topic": "分布特征",
        "chart_type": "bar",
        "display_role": "secondary",
        "default_title": "分布分析",
        "description": "展示指标的均值、中位数、标准差、偏度、峰度等分布特征",
        "tags": ["distribution", "统计", "分布"],
        "drill_down": False,
        "cross_filter": False,
        "filter_dimension_keywords": [],
    },

    # ===== 相关性分析 =====
    "correlation_analysis": {
        "widget_type": "chart",
        "business_topic": "指标相关性",
        "chart_type": "scatter",
        "display_role": "secondary",
        "default_title": "相关性分析",
        "description": "展示两个指标之间的相关关系（Pearson/Spearman）",
        "tags": ["correlation", "scatter", "关系"],
        "drill_down": False,
        "cross_filter": False,
        "filter_dimension_keywords": [],
    },

    # ===== 对比分析 =====
    "comparison_analysis": {
        "widget_type": "chart",
        "business_topic": "对比差异",
        "chart_type": "bar",
        "display_role": "secondary",
        "default_title": "对比分析",
        "description": "展示各组与全局均值的差异和提升度",
        "tags": ["comparison", "差异", "提升度"],
        "drill_down": True,
        "cross_filter": False,
        "filter_dimension_keywords": ["category", "分类", "产品", "地区", "region"],
    },

    # ===== 漏斗分析 =====
    "funnel": {
        "widget_type": "chart",
        "business_topic": "转化漏斗",
        "chart_type": "funnel",
        "display_role": "main",
        "default_title": "转化漏斗分析",
        "description": "展示用户从访问到下单各环节的转化/流失情况",
        "tags": ["funnel", "漏斗", "转化", "流失"],
        "drill_down": False,
        "cross_filter": False,
        "filter_dimension_keywords": [],
    },
    "funnel_analysis": {
        "widget_type": "chart",
        "business_topic": "转化漏斗",
        "chart_type": "funnel",
        "display_role": "main",
        "default_title": "转化漏斗分析",
        "description": "展示用户从访问到下单各环节的转化/流失情况",
        "tags": ["funnel", "漏斗", "转化", "流失"],
        "drill_down": False,
        "cross_filter": False,
        "filter_dimension_keywords": [],
    },

    # ===== 地理空间分析 =====
    "geo_analysis": {
        "widget_type": "map",
        "business_topic": "地理分布",
        "chart_type": "map",
        "display_role": "main",
        "default_title": "地理空间分析",
        "description": "展示指标在地理空间上的分布（省份/城市/地区）",
        "tags": ["geo", "地图", "空间", "区域"],
        "drill_down": True,
        "cross_filter": True,
        "filter_dimension_keywords": ["region", "地区", "省份", "省", "城市", "市", "区域"],
    },

    # ===== 异常分析 =====
    "anomaly_analysis": {
        "widget_type": "chart",
        "business_topic": "异常检测",
        "chart_type": "scatter",
        "display_role": "secondary",
        "default_title": "异常分析",
        "description": "展示 Z-Score/IQR 异常检测结果，标记离群点",
        "tags": ["anomaly", "异常", "离群", "预警"],
        "drill_down": False,
        "cross_filter": False,
        "filter_dimension_keywords": [],
    },

    # ===== 占比分析 =====
    "proportion_analysis": {
        "widget_type": "chart",
        "business_topic": "占比构成",
        "chart_type": "pie",
        "display_role": "secondary",
        "default_title": "占比分析",
        "description": "展示各部分在总体中的占比构成",
        "tags": ["proportion", "占比", "构成"],
        "drill_down": False,
        "cross_filter": False,
        "filter_dimension_keywords": ["category", "分类", "产品"],
    },

    # ===== 留存分析 =====
    "retention_analysis": {
        "widget_type": "kpi",
        "business_topic": "客户留存",
        "chart_type": None,
        "display_role": "secondary",
        "default_title": "留存分析",
        "description": "展示复购率、复购客户数、平均购买频次等留存指标",
        "tags": ["retention", "留存", "复购", "客户"],
        "drill_down": False,
        "cross_filter": False,
        "filter_dimension_keywords": ["time", "时间", "日期", "月"],
    },

    # ===== 同期群分析（cohort_heatmap） =====
    "cohort": {
        "widget_type": "chart",
        "business_topic": "同期群",
        "chart_type": "cohort_heatmap",
        "display_role": "main",
        "default_title": "同期群分析",
        "description": "下三角热力图展示用户留存与跃迁",
        "tags": ["cohort", "同期群", "留存矩阵"],
        "drill_down": False,
        "cross_filter": False,
        "filter_dimension_keywords": ["time", "时间", "月份", "首单月"],
    },

    # ===== 关联规则（force-directed graph） =====
    "association_rules": {
        "widget_type": "chart",
        "business_topic": "商品关联",
        "chart_type": "graph",
        "display_role": "main",
        "default_title": "商品关联规则",
        "description": "商品-商品共现关系网络图",
        "tags": ["association", "graph", "商品关联"],
        "drill_down": False,
        "cross_filter": False,
        "filter_dimension_keywords": ["category", "分类", "商品"],
    },
}


# ============================================================
# 默认配置（analysis_type 未在映射表中时使用）
# ============================================================

DEFAULT_WIDGET_CONFIG: Dict[str, Any] = {
    "widget_type": "chart",
    "business_topic": "分析结果",
    "chart_type": "bar",
    "display_role": "secondary",
    "default_title": "分析结果",
    "description": "",
    "tags": [],
    "drill_down": False,
    "cross_filter": False,
    "filter_dimension_keywords": [],
}


# ============================================================
# filter field → 中文标签映射
# ============================================================

FILTER_FIELD_LABELS: Dict[str, str] = {
    "time": "时间范围",
    "region": "地区",
    "product": "产品",
    "category": "分类",
    "brand": "品牌",
}


# ============================================================
# 工具函数
# ============================================================

def get_widget_config(analysis_type: str) -> Dict[str, Any]:
    """获取 analysis_type 对应的 Widget 配置"""
    # 移除 "_analysis" 后缀后再查一次（兼容 "growth" → "growth_analysis"）
    config = ANALYSIS_TO_WIDGET_MAPPING.get(analysis_type)
    if config is None and analysis_type.endswith("_analysis"):
        # 已经是完整名，不再处理
        pass
    if config is None:
        # 尝试加后缀
        config = ANALYSIS_TO_WIDGET_MAPPING.get(f"{analysis_type}_analysis")
    if config is None:
        config = DEFAULT_WIDGET_CONFIG
    return config
