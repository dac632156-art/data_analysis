"""
ChartRenderer —— 统一图表渲染层
封装 echart_generator.create_chart()，ChartData → ECharts option
"""
import pandas as pd
from typing import Optional, Dict, Any
from src.analysis_templates.base import ChartData, ChartItem
from src.echart_generator import create_chart


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

            option = create_chart(
                df=df,
                chart_type=chart_data.chart_type,
                x=chart_data.x,
                y=chart_data.y,
                title=chart_data.title,
            )

            role = self.ROLE_MAP.get(chart_data.chart_type, "primary")

            return ChartItem(
                slot=chart_data.slot,
                chart_type=chart_data.chart_type,
                title=chart_data.title,
                role=role,
                option=option if option else {},
            )
        except Exception:
            return None

    def render_all(self, chart_data_list: list, theme: str = "dark") -> list:
        return [c for c in (self.render(d, theme) for d in chart_data_list) if c is not None]
