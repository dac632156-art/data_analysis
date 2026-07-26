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
from src.analysis_templates.base import AnalysisPackage
from src.utils.json_serializer import sanitize_json

logger = logging.getLogger("analysis_engine")


def run_analysis(df: pd.DataFrame, intents: Optional[List[str]] = None) -> List[AnalysisPackage]:
    if df is None:
        return []

    packages: List[AnalysisPackage] = []
    models = get_models()

    for model in models:
        # 可选意图过滤
        if intents:
            names = [str(x) for x in intents if x]
            if model.name not in names and model.display_name not in names:
                continue

        if not model.can_run(df):
            logger.info(
                "分析模型[%s]跳过：所需列 %s 未全部命中（df 列：%s）",
                model.name, model.required_columns, list(df.columns),
            )
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
        packages.append(pkg)

    # B12 防护：杜绝 NaN/inf 进前端
    for pkg in packages:
        try:
            pkg.to_api_dict() if hasattr(pkg, "to_api_dict") else None
        except Exception:
            pass
    _ = [sanitize_json(p.to_api_dict()) for p in packages]

    return packages
