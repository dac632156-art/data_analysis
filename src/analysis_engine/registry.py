"""模型注册表。

用户后续给出的分析模型，只需实现 AnalysisModel 并调用 register_model 注册即可，
引擎会自动按列名匹配运行。当前先为空（待模型定义到位后填入）。
"""
from typing import List

from src.analysis_engine.base import AnalysisModel

_MODELS: List[AnalysisModel] = []


def register_model(model: AnalysisModel) -> None:
    """注册一个分析模型。"""
    if not isinstance(model, AnalysisModel):
        raise TypeError("model 必须继承自 AnalysisModel")
    if not getattr(model, "name", ""):
        raise ValueError("model.name 不能为空")
    _MODELS.append(model)


def get_models() -> List[AnalysisModel]:
    return list(_MODELS)


def clear_models() -> None:
    _MODELS.clear()
