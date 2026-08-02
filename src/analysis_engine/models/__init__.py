"""同期群模型子包。

import 本包即触发各模型的 register_model（模块级注册）。
"""
from . import cohort  # noqa: F401 触发 register_model(CohortAnalysisModel())
from . import rfm     # noqa: F401 触发 register_model(RFMModel())
from . import kmeans  # noqa: F401 触发 5 个 K-means 模型注册 + run_user_seg 降级函数
from . import user_profile  # noqa: F401 触发 register_model(UserProfileModel())
from . import clv         # noqa: F401 触发 register_model(CLVAnalysisModel())
from . import association_rules  # noqa: F401 触发 register_model(AssociationRulesModel())
# 注意：association_rules_advanced 不被直接 import 触发，由 association_rules.compute
# 内部惰性 import，避免循环依赖。
from . import churn_rule  # noqa: F401 触发 register_model(ChurnRuleModel())
from . import funnel      # noqa: F401 触发 register_model(FunnelAnalysisModel())
