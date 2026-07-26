"""分析模型基类。

判定规则（对应你说的入口逻辑）：
    拿映射后的列名，逐个与模型 required_columns 比对；
    required_columns 全部存在于 df.columns → 可以计算；
    缺任何一列 → 跳过（不报错）。
"""
from abc import ABC, abstractmethod
from typing import List

import pandas as pd

from src.analysis_templates.base import AnalysisPackage


class AnalysisModel(ABC):
    # 子类通过类属性声明自身元信息
    name: str = ""                 # 模型标识（唯一，用于 intents 过滤）
    display_name: str = ""         # 前端展示名
    description: str = ""          # 一句话说明
    required_columns: List[str] = []   # 映射后的标准列名，必须全部存在
    optional_columns: List[str] = []   # 可选列，存在则增强计算

    def can_run(self, df: pd.DataFrame) -> bool:
        """required_columns 是否全部 ⊆ df.columns；不满足即跳过。"""
        if df is None or len(df.columns) == 0:
            return False
        cols = set(df.columns)
        return all(req in cols for req in self.required_columns)

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> AnalysisPackage:
        """执行计算，返回归一化的 AnalysisPackage。

        chart_data / charts 用通用结构描述（由 echart_generator 渲染），
        不要在此处直接生成 ECharts option。
        """
        raise NotImplementedError
