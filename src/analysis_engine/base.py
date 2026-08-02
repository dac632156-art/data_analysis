"""分析模型基类。

判定规则（对应你说的入口逻辑）：
    拿映射后的列名，逐个与模型 required_columns 比对；
    required_columns 全部存在于 df.columns → 可以计算；
    缺任何一列 → 跳过（不报错）。
"""
from abc import ABC, abstractmethod
from typing import List, Optional

import pandas as pd

from src.analysis_templates.base import AnalysisPackage


class AnalysisModel(ABC):
    # 子类通过类属性声明自身元信息
    name: str = ""                 # 模型标识（唯一，用于 intents 过滤）
    display_name: str = ""         # 前端展示名
    description: str = ""          # 一句话说明
    required_columns: List[str] = []   # 映射后的标准列名，必须全部存在
    optional_columns: List[str] = []   # 可选列，存在则增强计算
    upstream_keys: List[str] = []      # 依赖的上游模型名（model.name）；空 = 生产者

    def segmentation_table(self, df: pd.DataFrame = None) -> Optional[pd.DataFrame]:
        """可选：返回每用户分群宽表供下游消费；默认 None（非生产者）。
        隔离契约：实现不得原地修改传入 df（须先 copy 或建新表）。"""
        return None

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

        隔离契约（多线程并行必需）：
        1. 不得原地修改传入的 df（如 df["列"]=... / df.loc[...]=...），须先 copy 或建新表。
           反例：user_profile._normalize_columns 在「无重命名」分支会 norm["用户ID"]=... 原地改 df，
           仅因其在 Phase 2 串行执行、未并发故暂安全，请勿效仿。
        2. 不得用实例属性（self._xxx）缓存跨方法中间结果（如 rfm._seg_table 返回之值），
           否则 Web API 并发请求会共用同一模型单例、抢同一份状态导致结果串味。
        """
        raise NotImplementedError
