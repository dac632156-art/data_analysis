"""
统计分析 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import json

from backend.services.session_manager import manager
from src.stats_analyzer import get_descriptive_stats, get_group_stats, get_correlation_matrix, get_quick_insights
from src.utils.json_serializer import sanitize_json
from src.utils.helpers import get_numeric_columns, get_categorical_columns

router = APIRouter()


class StatsRequest(BaseModel):
    session_id: str


class GroupStatsRequest(StatsRequest):
    group_col: str
    agg_cols: Optional[List[str]] = None


class CorrRequest(StatsRequest):
    method: str = "pearson"


@router.post("/stats/descriptive")
async def api_descriptive_stats(req: StatsRequest):
    """获取描述性统计"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    stats = get_descriptive_stats(df)
    return sanitize_json({
        "success": True,
        "stats": stats.to_dict(orient="index") if hasattr(stats, 'to_dict') else stats,
        "columns": list(stats.columns) if hasattr(stats, 'columns') else [],
        "index": list(stats.index) if hasattr(stats, 'index') else [],
    })


@router.post("/stats/group")
async def api_group_stats(req: GroupStatsRequest):
    """获取分组统计"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    if req.group_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"无效的分组列: {req.group_col}")
    result = get_group_stats(df, req.group_col, req.agg_cols)
    return sanitize_json({
        "success": True,
        "stats": result.reset_index().to_dict(orient="records") if hasattr(result, 'reset_index') else result,
        "columns": list(result.columns) if hasattr(result, 'columns') else [],
    })


@router.post("/stats/correlation")
async def api_correlation(req: CorrRequest):
    """获取相关性矩阵"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    corr = get_correlation_matrix(df, req.method)
    return sanitize_json({
        "success": True,
        "correlation": corr.to_dict() if hasattr(corr, 'to_dict') else corr,
        "columns": list(corr.columns) if hasattr(corr, 'columns') else [],
    })


@router.post("/stats/quick-insights")
async def api_quick_insights(req: StatsRequest):
    """获取快速数据洞察"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    insights = get_quick_insights(df)
    return sanitize_json({"success": True, "insights": insights})


@router.post("/stats/numeric-columns")
async def api_numeric_columns(req: StatsRequest):
    """获取数值列"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    return sanitize_json({"success": True, "columns": get_numeric_columns(df)})
