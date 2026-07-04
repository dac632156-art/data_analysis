"""
Analysis Library —— YAML 驱动的分析知识库

职责：维护所有分析类型的业务知识（intent、关键词、模板映射、默认算法、输出类型、fallback）。
    绝不包含算法实现或列要求——这些属于 Template 层。

使用方式：
    from src.analysis_library import AnalysisLibrary
    lib = AnalysisLibrary()
    intent = lib.lookup("分析增长趋势")  # → AnalysisIntent(intent="growth", ...)
"""

from src.analysis_library.analysis_intent import AnalysisIntent
from src.analysis_library.registry import AnalysisLibrary

__all__ = ["AnalysisIntent", "AnalysisLibrary"]
