"""
图表生成 API 路由（V2：仅保留 ECharts 端点）
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import logging

from backend.services.session_manager import manager
from src.echart_generator import create_chart as create_echart
from src.echart_generator import _to_geo_name, _PROVINCE_CENTROIDS, _GEO_PROVINCE_NAMES
from src.utils.json_serializer import sanitize_json

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
    
    return sanitize_json({"success": True, "option": option})
