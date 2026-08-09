"""analysis_engine —— 新分析模型引擎（以「映射后列名匹配」为唯一入口）。
对外暴露：run_analysis / register_model / get_models / AnalysisModel / render_package
"""
from src.analysis_engine.base import AnalysisModel
from src.analysis_engine.registry import register_model, get_models, clear_models
from src.analysis_engine.engine import run_analysis
from src.analysis_engine.package_render import render_package

__all__ = ["AnalysisModel", "register_model", "get_models", "clear_models", "run_analysis", "render_package"]

# 触发模型注册：import 子包即执行各模型的 register_model（副作用）
import src.analysis_engine.models  # noqa: E402,F401
