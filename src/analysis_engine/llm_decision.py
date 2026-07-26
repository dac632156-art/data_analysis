"""
LLM 决策路径（一期预留）。

本模块是「生成数据洞察」双路分析的 LLM 支路：
- 规则引擎支路：src.analysis_engine.engine 确定性跑命中模型（本期主力）。
- LLM 决策支路：调用 LLM 判定是否存在规则引擎未覆盖的分析类型，
  并（二期）通过沙箱执行生成额外分析包。

一期约束（用户确认）：
- 不接真实 LLM 调用网络，也不执行沙箱代码；
- 仅记录「已触发 + 已注册模型 + 数据维度」的判定日志；
- 返回空包列表（[]），由规则引擎支路产出全部 AnalysisPackage。

二期扩展点：在 llm_decision_path 内补全
  1) 构造 prompt（列名 + 少量样本 + registered_models 清单）；
  2) 调用 LLM（传入 llm_cfg 的 api_key/base_url/model）拿到候选分析类型；
  3) 沙箱生成对应分析代码并安全执行 → 产出 List[AnalysisPackage]。
接口签名（session_id / df / registered_models / llm_cfg / 返回类型）保持固定，
二期只填充执行体，不改动调用方。
"""
from typing import Any, Dict, List

import logging

logger = logging.getLogger("analysis_engine.llm_decision")


async def llm_decision_path(
    df: "Any",
    registered_models: List[str],
    llm_cfg: Dict[str, Any],
) -> List[Any]:
    """LLM 决策路径（一期预留）。

    Args:
        df: 已做列名映射的 DataFrame。
        registered_models: 当前已注册的分析模型名称列表。
        llm_cfg: LLM 配置（api_key / base_url / model），一期不消费。

    Returns:
        List[AnalysisPackage]：一期恒为空列表（沙箱执行延至二期）。
    """
    n_cols = len(getattr(df, "columns", ())) if getattr(df, "columns", None) is not None else 0
    logger.info(
        "LLM 决策路径已触发 | 列数=%d | 已注册模型=%s | 沙箱执行待二期(本期返回空包)",
        n_cols,
        registered_models,
    )
    # 一期：不调用 LLM、不执行沙箱，直接返回空包。
    return []
