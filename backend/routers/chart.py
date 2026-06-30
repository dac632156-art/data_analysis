"""
图表生成 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import json
import logging

from backend.services.session_manager import manager
from src.chart_generator import (
    get_chart_recommendations, create_chart, create_heatmap
)
from src.echart_generator import create_chart as create_echart
from src.echart_generator import _to_geo_name, _PROVINCE_CENTROIDS, _GEO_PROVINCE_NAMES

router = APIRouter()
logger = logging.getLogger(__name__)


class ChartRequest(BaseModel):
    session_id: str
    chart_type: str
    x: str
    y: Optional[str] = None
    title: Optional[str] = None
    color: Optional[str] = None
    orientation: Optional[str] = "v"


class HeatmapRequest(BaseModel):
    session_id: str
    title: Optional[str] = "相关性热力图"


class ChartRecRequest(BaseModel):
    session_id: str

@router.post("/chart/recommendations")
async def api_chart_recommendations(req: ChartRecRequest):
    """获取 AI 图表推荐"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    recommendations = get_chart_recommendations(df)
    return {"success": True, "recommendations": recommendations}


@router.post("/chart/create")
async def api_create_chart(req: ChartRequest):
    """创建图表"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    
    kwargs = {}
    if req.y:
        kwargs['y'] = req.y
    if req.title:
        kwargs['title'] = req.title
    if req.color:
        kwargs['color'] = req.color
    if req.orientation:
        kwargs['orientation'] = req.orientation
    
    try:
        fig = create_chart(df, req.chart_type, x=req.x, **kwargs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if fig is None:
        raise HTTPException(status_code=400, detail="图表生成失败，请检查参数")
    
    # 将 plotly Figure 转为 JSON
    fig_json = json.loads(fig.to_json())
    return {"success": True, "figure": fig_json}


@router.post("/chart/echart-create")
async def api_create_echart(req: ChartRequest):
    """创建 ECharts 图表（返回 ECharts option JSON）"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    
    chart_type = req.chart_type
    x_axis = req.x

    # ★ 地区→省份展开由 create_gl_map 内部处理，不再在此处降级

    kwargs = {}
    if req.y:
        kwargs['y'] = req.y
    if req.title:
        kwargs['title'] = req.title
    if req.color:
        kwargs['color'] = req.color
    if req.orientation:
        kwargs['orientation'] = req.orientation
    
    try:
        option = create_echart(df, chart_type, x=x_axis, **kwargs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if option is None:
        raise HTTPException(status_code=400, detail="图表生成失败，请检查参数")
    
    return {"success": True, "option": option}


@router.post("/chart/heatmap")
async def api_heatmap(req: HeatmapRequest):
    """创建热力图"""
    df = manager.get_data(req.session_id)
    if df is None:
        raise HTTPException(status_code=404, detail="未找到数据")
    fig = create_heatmap(df, req.title)
    if fig is None:
        raise HTTPException(status_code=400, detail="热力图生成失败（至少需要2个数值列）")
    fig_json = json.loads(fig.to_json())
    return {"success": True, "figure": fig_json}
