"""同期群模型子包。

import 本包即触发各模型的 register_model（模块级注册）。
"""
from . import cohort  # noqa: F401 触发 register_model(CohortAnalysisModel())
