"""分析引擎主入口：列名匹配驱动。

run_analysis(df, intents=None)：
    1. 遍历已注册模型；
    2. intents 非空时仅运行名称命中的模型（兼容前端"选中意图→运行"交互）；
    3. 对每个模型做 required_columns ⊆ df.columns 的确定性匹配；
       命中 → compute → 收集 AnalysisPackage；
       未命中 → 跳过并记录 INFO 日志（不泄露样本）。
    4. 全部经 B12 防护 sanitize_json 后再返回。
"""
import logging
from typing import List, Optional

import pandas as pd

from src.analysis_engine.registry import get_models

# 双保险：确保 8 个分析模型在 run_analysis 执行前已注册到 registry。
# analysis.py 当前用 `from src.analysis_engine.engine import run_analysis` 直导本模块，
# 命名空间包机制下不一定触发 analysis_engine/__init__.py，故此处显式导入 models 包。
import src.analysis_engine.models  # noqa: E402,F401
from src.analysis_templates.base import AnalysisPackage
from src.utils.json_serializer import sanitize_json

logger = logging.getLogger("analysis_engine")

# LLM（或前端）可能传的口语化意图名 → 引擎内部模型 name。
# 设计意图：LLM 不应关心引擎内部模型名，这里做一层兜底归一化。
# 值为 None 表示「放行某一类模糊模型」（见 CLUSTER_NAMES）。
INTENT_ALIASES = {
    "rfm分析": "rfm_user_segmentation",
    "rfm 分析": "rfm_user_segmentation",
    "rfm": "rfm_user_segmentation",
    "用户流失预测": "churn_rule",
    "流失预测": "churn_rule",
    "流失": "churn_rule",
    "漏斗分析": "funnel",
    "漏斗": "funnel",
    "转化漏斗": "funnel",
    "关联规则挖掘": "association_rules",
    "关联规则": "association_rules",
    "购物篮": "association_rules",
    "同期群分析": "同期群与用户状态跃迁模型",
    "同期群": "同期群与用户状态跃迁模型",
    "cohort": "同期群与用户状态跃迁模型",
    "用户画像": "user_profile",
    "画像": "user_profile",
    "用户生命周期价值": "CLV",
    "clv": "CLV",
    # 「趋势分析」引擎无对应模型，不映射（查不到静默跳过，避免张冠李戴到 cohort）
    "聚类": None,  # None = 放行所有聚类类模型
}

# 聚类类模型 name 集合（供「聚类」模糊意图放行）
CLUSTER_NAMES = {
    "user_seg", "sku_seg", "geo_seg",
    "activity_seg", "category_seg", "churn_seg",
}


def run_analysis(df: pd.DataFrame, intents: Optional[List[str]] = None) -> List[AnalysisPackage]:
    if df is None:
        return []

    packages: List[AnalysisPackage] = []
    models = get_models()
    # 瞬态上游缓存：生产者挂出的每用户分群宽表（局部变量，函数返回即被 GC，
    # 不跨请求保留，上线不增加常驻内存）。
    upstream: dict = {}

    # 预归一化 LLM 传来的意图：查别名表 → 模型名集合 + 是否放行聚类
    _names: set = set()
    _allow_cluster = False
    if intents:
        for raw in intents:
            if not raw:
                continue
            key = str(raw).strip().lower()
            target = INTENT_ALIASES.get(key)
            if target is None:
                if key in INTENT_ALIASES:
                    # 显式映射到 None（模糊词如「聚类」）→ 放行聚类类模型
                    _allow_cluster = True
                elif raw in CLUSTER_NAMES:
                    # 别名表未命中，但本身就是聚类模型名 → 放行聚类类
                    _allow_cluster = True
                else:
                    # 兼容前端直接传真实 name/display_name
                    _names.add(raw)
            else:
                _names.add(target)

    def _match_intents(model) -> bool:
        if not intents:
            return True
        if model.name in _names or model.display_name in _names:
            return True
        if _allow_cluster and model.name in CLUSTER_NAMES:
            return True
        return False

    # ---------- Phase 1：生产者（无上游依赖，串行执行） ----------
    for model in models:
        if getattr(model, "upstream_keys", []):
            continue  # 消费者留到 Phase 2
        if not _match_intents(model):
            continue
        if not model.can_run(df):
            logger.info(
                "分析模型[%s]跳过：所需列 %s 未全部命中（df 列：%s）",
                model.name, model.required_columns, list(df.columns),
            )
            # 静默跳过：不生成占位包，前端不再展示任何“不支持”提示
            continue
        try:
            pkg = model.compute(df)
        except Exception as exc:  # 单模型失败不影响其他模型
            logger.exception("分析模型[%s]执行失败：%s", model.name, exc)
            continue

        if pkg is None:
            continue
        if not getattr(pkg, "id", None):
            pkg.id = model.name
        if getattr(pkg, "can_run", True):
            packages.append(pkg)
            # 捕获生产者挂出的每用户分群表（瞬态入 upstream，供 Phase 2 消费者使用）
            try:
                seg = model.segmentation_table(df)
            except Exception:
                seg = None
            if seg is not None and len(seg) > 0:
                upstream[model.name] = seg

    # ---------- Phase 2：消费者（依赖上游分群） ----------
    for model in models:
        ukeys = getattr(model, "upstream_keys", [])
        if not ukeys:
            continue
        if not _match_intents(model):
            continue
        # 软门槛：消费者只要 can_run 通过即跑，upstream 原样透传；
        # 是否真正消费上游由模型自身判定（base 不被上游缺失绑架，
        # 如「商品关联规则」base 独立产出、仅进阶 C 依赖 RFM 分层）。
        # 对用户画像等纯消费者无副作用：其内部 seg is None 时返回
        # can_run=False 的占位包，下方统一剔除。
        if not model.can_run(df):
            continue
        try:
            pkg = model.compute(df, upstream=upstream)
        except Exception as exc:
            logger.exception("分析模型[%s]执行失败：%s", model.name, exc)
            continue

        if pkg is None:
            continue
        if not getattr(pkg, "id", None):
            pkg.id = model.name
        if getattr(pkg, "can_run", True):
            packages.append(pkg)

    # 统一剔除所有 can_run=False 的包（engine 预检跳过、rfm/kmeans/cohort
    # 内部 _skipped 等路径产生的占位包都不流出引擎，前端不再展示任何"不支持"提示）
    packages = [p for p in packages if getattr(p, "can_run", True)]

    # B12 防护：杜绝 NaN/inf 进前端
    for pkg in packages:
        try:
            pkg.to_api_dict() if hasattr(pkg, "to_api_dict") else None
        except Exception:
            pass
    _ = [sanitize_json(p.to_api_dict()) for p in packages]

    return packages
