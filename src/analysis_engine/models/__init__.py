"""同期群模型子包。import 本包即触发各模型的 register_model（模块级注册）。"""
from . import cohort
from . import rfm
from . import kmeans
from . import user_profile
from . import clv
from . import association_rules
# 注意：association_rules_advanced 不被直接 import 触发，由 association_rules.compute 内部惰性 import，避免循环依赖。
from . import churn_rule
from . import funnel
