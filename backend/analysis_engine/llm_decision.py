"""LLM 决策路径（一期预留）。

一期仅做「判定」：把列名 + 少量样本 + 已注册模型清单交给 LLM，
判定是否存在规则引擎未覆盖的分析类型；沙箱代码执行延至二期，
本期返回空包列表（仅记录决策日志）。

接口签名固定，二期只填沙箱执行体，无需改动调用方。
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger("llm_decision")


async def llm_decision_path(
    df: "pd.DataFrame",
    registered_models: List[str],
    llm_cfg: Dict[str, Any],
) -> List[Any]:
    """LLM 决策路径（一期预留）。

    返回 List[AnalysisPackage]，本期恒为空（沙箱执行待二期）。
    """
    # 一期：仅记录「已触发决策路径」日志，不泄露样本内容
    logger.info(
        "LLM 决策路径已触发 | 列数=%d | 已注册模型=%s | 沙箱执行待二期(本期返回空包)",
        len(getattr(df, "columns", []) or []),
        registered_models,
    )
    # TODO(二期): 调用 LLM 判定未覆盖分析类型，并在沙箱执行生成额外 AnalysisPackage
    return []
