"""
ChartRenderer —— 统一图表渲染层
封装 echart_generator.create_chart()，ChartData → ECharts option
"""
import logging
import math
import re

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

            # 阈值红线：把 chart_config.threshold 直接写成 markLine 注入 series，
            # 使任何拿到该 option 的客户端（医疗看板 / 分析预览 / 导出 HTML）都能自动画红线，
            # 不再依赖某个前端组件单独计算 threshold。仅对柱状/直方图生效。
            option = self._inject_threshold_markline(option, chart_data)

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

    @staticmethod
    def _inject_threshold_markline(option: Dict[str, Any], chart_data: "ChartData") -> Dict[str, Any]:
        """对柱状/直方图 series 注入阈值红线 markLine（原地修改 option 并返回）。

        红线动态落在"第一个数值 >= 阈值的区间起点"的「左边界」（即阈值的数值分界点），
        **不依赖具体阈值**，任何数据算出的阈值都能正确定位。

        实现要点（关键坑）：ECharts 的 category 轴 markLine 只认整数类目索引或类目名，
        不支持浮点坐标（传 2.5 会被忽略/截断，红线又掉回柱子正中）。因此采用「双 X 轴」：
        保留原 category 轴给柱子，新增一个隐藏的 value 轴（min=0, max=桶数-1）专门给
        markLine 定位，传 best_idx-0.5 即可精确落在两桶之间（桶左边界）。
        """
        cfg = chart_data.chart_config or {}
        threshold = cfg.get("threshold")
        if not (isinstance(threshold, (int, float)) and math.isfinite(threshold)):
            return option
        if chart_data.chart_type not in ("bar", "histogram"):
            return option
        if not isinstance(option, dict):
            return option

        # 取 X 轴 category（兼容 xAxis 为 dict 或 list）
        x_axis = option.get("xAxis")
        if isinstance(x_axis, list):
            x_axis = x_axis[0] if x_axis else None
        categories = x_axis.get("data") if isinstance(x_axis, dict) else None
        if not isinstance(categories, list) or not categories:
            return option

        # 从桶名提取「区间起点」用于定位阈值分界：
        # - "≥157天" / ">=157" → 157（尾桶，区间起点即阈值下限）
        # - "0~10天" / "0-10" → 取区间起点 0
        # - "53" / "106"（纯数字桶名）→ 数字本身即起点
        # 注意：不能只匹"≥"/">"前缀，否则中间桶(0~10天/53/106)提取不出数值，
        # 红线就只能永远落在带≥的尾桶（之前的根因之一）。
        def _bucket_start(cat: str) -> float | None:
            s = str(cat)
            # 优先匹配 "≥N" / ">=N" / ">N" 尾桶
            m = re.search(r"[≥>=]+\s*(\d+(?:\.\d+)?)", s)
            if m:
                return float(m.group(1))
            # 区间 "a~b" / "a-b" → 起点 a
            m = re.search(r"(\d+(?:\.\d+)?)\s*[~\-]\s*\d+(?:\.\d+)?", s)
            if m:
                return float(m.group(1))
            # 纯数字桶名 "53" / "106" → 数字本身
            m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*", s)
            if m:
                return float(m.group(1))
            return None

        best_idx = -1
        for i, cat in enumerate(categories):
            v = _bucket_start(cat)
            if v is None:
                continue
            if v >= float(threshold):
                best_idx = i
                break
        if best_idx < 0:
            # 阈值超过所有桶起点（如阈值大于尾桶下限）：红线落在「最右桶右边界外侧」，
            # 表示全量已超阈值，而不是静默不画（否则"阈值很大时没红线"）
            best_idx = len(categories) - 1
            x_coord = float(best_idx) + 0.5
        else:
            # 红线落在命中桶的「左边界」= best_idx - 0.5；首桶 clamp 到 0 避免画出轴外左侧
            x_coord = max(float(best_idx) - 0.5, 0.0)

        label = cfg.get("threshold_label") or "阈值"
        # 红线落在命中桶的「左边界」= best_idx - 0.5（value 轴浮点坐标）。
        # 首桶 clamp 到 0，避免画到轴外左侧被裁掉。
        x_coord = max(float(best_idx) - 0.5, 0.0)
        # 标签带具体阈值数值（天），直击"看不出阈值是多少"的痛点；无论阈值多少都带"天"
        threshold_val = float(threshold)
        if abs(threshold_val - round(threshold_val)) < 1e-6:
            label_formatter = f"{label} {int(round(threshold_val))}天"
        else:
            label_formatter = f"{label} {threshold_val:g}天"
        mark_line = {
            "symbol": "none",
            "silent": True,
            # 关键：用第二个（隐藏 value）轴定位，才能精确落在浮点坐标（桶左边界）
            "xAxisIndex": 1,
            "lineStyle": {"color": "#DC2626", "width": 3},
            "label": {
                "show": True,
                # end：标签落在竖直线段「顶端外侧」，横排（不再沿线段旋转成竖排）
                "position": "end",
                # 负向 Y 偏移把标签向上推远，避免压到柱顶数字（如 "383"）
                "offset": [0, -12],
                "formatter": label_formatter,
                "color": "#fff",
                "backgroundColor": "#DC2626",
                "padding": [2, 6],
                "borderRadius": 4,
                "fontSize": 12,
            },
            "data": [{"xAxis": x_coord}],
        }

        # 构造「双 X 轴」：原 category 轴 + 隐藏 value 轴（min=0, max=桶数-1，与类目索引对齐）
        hidden_value_axis = {
            "type": "value",
            "show": False,
            "min": 0,
            "max": len(categories) - 1,
            "splitNumber": max(len(categories) - 1, 1),
        }
        original_x_axis = option.get("xAxis")
        if isinstance(original_x_axis, list):
            # 已有多轴：避免重复追加隐藏轴（幂等）
            has_hidden = any(
                isinstance(ax, dict) and ax.get("type") == "value" and ax.get("_threshold_axis")
                for ax in original_x_axis
            )
            if not has_hidden:
                option["xAxis"] = [
                    *original_x_axis,
                    {**hidden_value_axis, "_threshold_axis": True},
                ]
        else:
            option["xAxis"] = [
                original_x_axis if isinstance(original_x_axis, dict) else {"type": "category", "data": categories},
                {**hidden_value_axis, "_threshold_axis": True},
            ]

        # 向所有 series 注入（兼容 series 为 dict 或 list）
        series = option.get("series")
        if isinstance(series, dict):
            option["series"] = {**series, "markLine": mark_line}
        elif isinstance(series, list):
            option["series"] = [
                {**(s if isinstance(s, dict) else {"type": chart_data.chart_type}), "markLine": mark_line}
                for s in series
            ]
        return option
