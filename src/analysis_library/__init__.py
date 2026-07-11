"""
Analysis Library —— YAML 驱动的分析知识中心（V3）

升级为全系统的唯一分析知识来源：
- 分析意图、业务问题、关键词、优先级
- Template 映射、Calculator 映射
- 数据 Schema 要求、字段需求
- 输出规范（KPI/Table/Chart，含描述）
- 派生指标定义
- Fallback 策略
- 自动意图生成规则

使用方式：
    from src.analysis_library import AnalysisLibrary
    lib = AnalysisLibrary()
    intent = lib.lookup("分析增长趋势")         # 中文 → AnalysisIntent
    profiles = lib.get_all_profiles()           # 所有分析类型概要
    suggestions = lib.suggest_intents_for_columns(t, c, n)  # 列 → 推荐意图
    path = lib.get_template_module_path("growth")            # intent → Template 路径
"""

from src.analysis_library.analysis_intent import (
    AnalysisIntent,
    OutputSpecDetail,
    OutputItemSpec,
    SchemaRequirement,
    OutputSpec,  # 向后兼容别名
)
from src.analysis_library.registry import AnalysisLibrary

__all__ = [
    "AnalysisIntent",
    "AnalysisLibrary",
    "OutputSpecDetail",
    "OutputItemSpec",
    "SchemaRequirement",
    "OutputSpec",
]