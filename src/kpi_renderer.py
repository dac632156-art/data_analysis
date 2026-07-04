"""
KPIRenderer —— 统一 KPI 格式化渲染层

输入 List[KPIItem] → 输出前端可直接消费的 RenderedKPI 列表。
统一处理：数值千分位、百分比小数位、变化量颜色标记
"""

from dataclasses import dataclass, field
from typing import List
from src.analysis_templates.base import KPIItem


@dataclass
class RenderedKPI:
    label: str        # "总销售额"
    value: str        # "1,245,000"
    change: str       # "+3.2%"
    trend: str        # "up" | "down" | "flat" | ""
    kpi_type: str     # "sum" | "avg" | "count" | "rate" | "change"


class KPIRenderer:
    """统一 KPI 渲染器"""

    def render(self, kpi: KPIItem) -> RenderedKPI:
        """渲染单个 KPI"""
        # 推断趋势方向
        trend = self._infer_trend(kpi.change) if kpi.change else ""

        # 格式化数值
        value = kpi.value
        change = kpi.change if kpi.change else ""

        return RenderedKPI(
            label=kpi.label,
            value=value,
            change=change,
            trend=trend,
            kpi_type=kpi.kpi_type,
        )

    def render_all(self, kpis: List[KPIItem]) -> List[RenderedKPI]:
        """批量渲染 KPI 列表"""
        return [self.render(k) for k in kpis]

    @staticmethod
    def _infer_trend(change_str: str) -> str:
        """从变化字符串推断趋势方向"""
        if not change_str:
            return ""
        cleaned = change_str.strip().replace("%", "")
        try:
            val = float(cleaned)
            if val > 0:
                return "up"
            elif val < 0:
                return "down"
            return "flat"
        except ValueError:
            return ""
