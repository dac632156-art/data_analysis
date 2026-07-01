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

    ROLE_MAP = {
        "line":  "primary",
        "bar":   "secondary",
        "area":  "detail",
        "pie":   "primary",
        "scatter": "primary",
        "histogram": "primary",
    }

    def render(self, chart_data: ChartData, theme: str = "dark") -> Optional[ChartItem]:
        """调用 echart_generator.create_chart() 生成 ECharts option"""
        try:
            df = pd.DataFrame(chart_data.data) if chart_data.data else pd.DataFrame()

            option = create_chart(
                df=df,
                chart_type=chart_data.chart_type,
                x=chart_data.x,
                y=chart_data.y,
                title=chart_data.title,
            )

            role = self.ROLE_MAP.get(chart_data.chart_type, "secondary")

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
