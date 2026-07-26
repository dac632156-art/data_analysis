"""analysis_engine —— 新分析模型引擎（以「映射后列名匹配」为唯一入口）。

对外暴露：
- run_analysis(df, intents=None) -> List[AnalysisPackage]  主入口
- register_model(model) / get_models()                模型注册
- AnalysisModel                                       模型基类
- render_package(pkg_dict)                            补全 rendered_* 字段
"""
from src.analysis_engine.base import AnalysisModel
from src.analysis_engine.registry import register_model, get_models, clear_models
from src.analysis_engine.engine import run_analysis
from src.analysis_engine.package_render import render_package

__all__ = [
    "AnalysisModel",
    "register_model",
    "get_models",
    "clear_models",
    "run_analysis",
    "render_package",
]

# 触发模型注册：import 子包即执行各模型的 register_model（副作用）
import src.analysis_engine.models  # noqa: E402,F401
