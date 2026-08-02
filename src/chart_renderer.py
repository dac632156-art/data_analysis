"""
ChartRenderer —— 统一图表渲染层
封装 echart_generator.create_chart()，ChartData → ECharts option
"""
import logging

import pandas as pd
from typing import Optional, Dict, Any
from src.analysis_templates.base import ChartData, ChartItem
from src.echart_generator import create_chart

logger = logging.getLogger(__name__)


class ChartRenderer:
    """统一图表渲染器"""

    # 所有图表一律 primary，不再区分主/辅（消除「辅图」角色；2026-07-11）。
    # 看板布局优先级另由 widget_mapping 的 display_role 决定，与此 role 无关。
    ROLE_MAP = {
        "line":  "primary",
        "bar":   "primary",
        "area":  "primary",
        "pie":   "primary",
        "scatter": "primary",
        "histogram": "primary",
        "ranking": "primary",
    }

    def render(self, chart_data: ChartData, theme: str = "dark") -> Optional[ChartItem]:
        """调用 echart_generator.create_chart() 生成 ECharts option"""
        try:
            df = pd.DataFrame(chart_data.data) if chart_data.data else pd.DataFrame()
            if df.columns.duplicated().any():
                df = df.loc[:, ~df.columns.duplicated()]

            # ★ 关键修复：模板 build_charts 把已算好的数据行用字面键 "x"/"y" 存放，
            #   但 ChartData.x / ChartData.y 是真实列名（如「产品类别」/「利润金额」）。
            #   create_chart 需要按真实列名定位，因此把占位键重命名为真实列名，
            #   否则会 KeyError 导致整张图渲染失败（charts 返回空）。
            rename_map = {}
            if "x" in df.columns and chart_data.x and chart_data.x != "x":
                rename_map["x"] = chart_data.x
            if "y" in df.columns and chart_data.y and chart_data.y != "y":
                rename_map["y"] = chart_data.y
            if rename_map:
                df = df.rename(columns=rename_map)

            # color 透传：散点/折线按系列（簇标签）着色；留空则单色
            chart_kwargs = {
                "x": chart_data.x,
                "y": chart_data.y,
                "title": chart_data.title,
            }
            if chart_data.color:
                chart_kwargs["color"] = chart_data.color
            if chart_data.right_col:
                chart_kwargs["right_col"] = chart_data.right_col
            option = create_chart(
                df=df,
                chart_type=chart_data.chart_type,
                **chart_kwargs,
            )

            role = self.ROLE_MAP.get(chart_data.chart_type, "primary")

            # 对数 Y 轴：等宽分箱下高值一柱顶天、稀疏长尾不可见，log 刻度让所有柱子
            # 重回视野（min=1 避 log(0)=undefined，剔空箱后无 0 值，安全）。
            if (chart_data.chart_config or {}).get("log_y") and isinstance(option, dict):
                yAxis = option.get("yAxis")
                if isinstance(yAxis, dict):
                    yAxis["type"] = "log"
                    yAxis["min"] = 1

            # 生成器返回空 dict（{}）→ 视为「无内容可画」，直接返回 None，
            # 由 render_all 过滤掉，避免产生「空白卡片」占位。
            if not option:
                return None
            return ChartItem(
                slot=chart_data.slot,
                chart_type=chart_data.chart_type,
                title=chart_data.title,
                role=role,
                option=option,
                raw_data=chart_data.data,  # 原始扁平 rows，供前端模板库组件使用
            )
        except Exception as exc:
            # 只加日志、不改行为：渲染失败仍返回 None 交由 render_all 过滤，
            # 但必须留下线索（此前静默吞掉导致图表"无声消失"无从排查）。
            logger.warning(
                "图表渲染失败 slot=%s chart_type=%s: %s: %s",
                chart_data.slot, chart_data.chart_type,
                type(exc).__name__, exc,
            )
            return None

    def render_all(self, chart_data_list: list, theme: str = "dark") -> list:
        return [c for c in (self.render(d, theme) for d in chart_data_list) if c is not None]
