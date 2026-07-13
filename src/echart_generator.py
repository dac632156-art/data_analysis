"""
ECharts 图表生成模块 - 输出 ECharts option JSON
支持与 Plotly chart_generator 相同的图表类型 + ECharts 独有的 brush/timeline 等交互
"""
import json
import math
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List

# ========== 降采样护栏常量 ==========
_MAX_SERIES_POINTS = 2000   # 线/散/柱/面积单序列点上限
_MAX_CATEGORY = 50          # 类目轴类别上限
_MAX_PIE_SLICES = 20        # 饼图/树图/词云扇区上限

# ★ Galaxy AI Analytics 统一配色（与前端 frontend/src/theme 模块保持一致）
# 10 色有序分类色板，禁止彩虹 / 每图随机配色。后端无法 import TS，此为常数镜像，
# 修改颜色时务必同步 frontend/src/theme/Palette.ts 与 ChartStyle.ts。
# BLUE_PALETTE 必须与前端 ChartStyle.series 完全一致（蓝→靛→青→金→粉→橙→青柠→淡紫→天空蓝→湖绿，暖色前置，AI 紫禁入图表）。
BLUE_PALETTE = [
    "#38BDF8", "#818CF8", "#22D3EE", "#FBBF24",
    "#F472B6", "#FB923C", "#84CC16", "#C084FC",
    "#60A5FA", "#2DD4BF",
]
# 向后兼容别名（Chart Factory 内统一使用 BLUE_PALETTE）
WARM_COLORS = BLUE_PALETTE

# Galaxy 主题常量（Single Source of Truth 的 Python 镜像）
GALAXY = {
    "page_bg": "#020617",
    "card_bg": "#0F172A",
    "text_primary": "#F8FAFC",
    "text_secondary": "#94A3B8",
    "text_muted": "#94A3B8",
    "axis": "rgba(248,250,252,0.55)",
    "primary": "#38BDF8",
    "primary_hover": "#7DD3FC",
    "primary_active": "#0EA5E9",
    "primary_bright": "#67E8F9",
    "sky": "#0ea5e9",
    "sky_mid": "#0369a1",
    "sky_deep": "#0c4a6e",
    "ai": "#8B5CF6",
    "interaction": "#22D3EE",
    "map_normal": "#23304E",
    "heat_start": "#13243F",
    "success": "#34D399",
    "danger": "#FB7185",
    "warning": "#FBBF24",
    "grid": "rgba(255,255,255,0.08)",
    "border": "rgba(255,255,255,0.08)",
    "tooltip_bg": "#0F172A",
    "tooltip_border": "rgba(255,255,255,0.08)",
    "tooltip_content": "#CBD5E1",
}

# ECharts 深色主题基础配置（统一 Galaxy 蓝）
DARK_THEME = {
    "backgroundColor": "transparent",
    "textStyle": {"color": GALAXY["text_secondary"]},
    "title": {"textStyle": {"color": GALAXY["text_primary"]}},
    "tooltip": {
        "backgroundColor": GALAXY["tooltip_bg"],
        "borderColor": GALAXY["tooltip_border"],
        "textStyle": {"color": GALAXY["text_primary"]}
    },
    "legend": {
        "textStyle": {"color": GALAXY["text_secondary"]},
        "top": "bottom"
    },
    "toolbox": {
        "feature": {
            "saveAsImage": {"title": "下载为PNG", "backgroundColor": "transparent"},
            "dataView": {"title": "数据视图", "readOnly": True},
        }
    },
}


def _get_default_title(title: str) -> dict:
    return {"text": title, "left": "center", "top": 8, "textStyle": {"color": GALAXY["text_primary"], "fontSize": 14}}


def _sort_data(df, x, y):
    """按 x 排序数据（如果 x 是数值型则按值排序）"""
    try:
        return df.sort_values(x)
    except Exception:
        return df


# 省份/地区/城市关键词 — 用于判断是否需要自动分组
_GEO_KEYWORDS = ['省', '市', '区', '县', '地区', '区域', '城市', '省份', '州', '国', '镇', '乡',
                  'province', 'city', 'region', 'area', 'district', 'state', 'country',
                  '部门', '科室', '单位', '组织', '机构', '类别', '类型', '分类', '分组']

_GEO_COL_KEYWORDS = ['省', '市', '区', '县', '地区', '区域', '城市', '省份', '地址', '位置',
                      'province', 'city', 'region', 'area', 'district', 'state', 'location',
                      '部门', '科室', '单位', '组织', '类别', '类型', '分类', '分组', '名称']


def _should_auto_group(df: pd.DataFrame, x: str) -> bool:
    """判断 X 轴列是否需要自动分组聚合
    
    条件：X 是分类列，且同一值出现多次（重复率 > 0），
    或者列名/值内容包含省份/地区等关键词
    """
    if x not in df.columns:
        return False
    
    col = df[x]
    # 1. 必须是分类列（object/category）
    dtype_str = str(col.dtype)
    if 'int' in dtype_str or 'float' in dtype_str or 'datetime' in dtype_str:
        return False
    
    # 2. 列名包含地区/分类关键词
    col_lower = x.lower()
    if any(kw in col_lower for kw in _GEO_COL_KEYWORDS):
        return True
    
    # 3. 值内容包含省份/地区关键词
    sample_vals = col.dropna().head(20).astype(str).tolist()
    if any(any(kw in v for kw in _GEO_KEYWORDS) for v in sample_vals):
        return True
    
    # 4. 同一值重复出现（非唯一映射）
    n_unique = col.nunique()
    n_total = len(col)
    if n_total > n_unique and n_total / n_unique > 1.2:
        return True
    
    return False


def _auto_groupby(df: pd.DataFrame, x: str, y: Optional[str] = None,
                   agg_func: str = 'sum') -> pd.DataFrame:
    """自动分组聚合：当 X 轴是省份/地区等分类列时，groupby X 并聚合 Y
    
    - 如果需要分组，返回 groupby 后的 DataFrame
    - 如果不需要分组，返回原始 DataFrame（不做任何修改）
    - agg_func 默认 'sum'，可选 'mean', 'count', 'max', 'min'
    """
    if not _should_auto_group(df, x):
        return df
    
    if y is None or y not in df.columns:
        # 没有 Y 列 → 做 value_counts
        counts = df[x].value_counts().reset_index()
        counts.columns = [x, 'count']
        return counts
    
    # groupby X，聚合 Y
    try:
        agg_df = df.groupby(x, as_index=False).agg({y: agg_func})
        return agg_df
    except Exception:
        # 聚合失败时返回原始数据
        return df


# ==================== 基础图表 ====================

def create_bar_chart(df: pd.DataFrame, x: str, y: Optional[str] = None,
                     title: str = "柱状图", color: Optional[str] = None,
                     orientation: str = "v", **ignored) -> Dict[str, Any]:
    """创建柱状图 ECharts option — 自动对省份/地区列分组聚合"""
    if y is None:
        counts = df[x].value_counts().reset_index()
        counts.columns = [x, 'count']
        y = 'count'
        df_plot = counts
    else:
        # ★ 自动分组：X 轴是省份/地区等分类列时 groupby 聚合
        df_plot = _auto_groupby(df, x, y)

    df_plot = _sort_data(df_plot, x, y)
    x_data = df_plot[x].astype(str).tolist()
    y_values = df_plot[y].fillna(0).tolist()

    option = {
        **_get_default_title(title),
        "tooltip": DARK_THEME["tooltip"],
        "legend": DARK_THEME["legend"],
        "toolbox": DARK_THEME["toolbox"],
        "grid": {"top": 60, "left": 50, "right": 20, "bottom": 40},
    }

    if orientation == "h":
        option["yAxis"] = {"type": "category", "data": x_data, "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}}
        option["xAxis"] = {"type": "value", "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}}
    else:
        option["xAxis"] = {"type": "category", "data": x_data, "axisLabel": {"rotate": 30 if len(x_data) > 8 else 0},
                           "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}}
        option["yAxis"] = {"type": "value", "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}}

    if color and color in df.columns:
        groups = df_plot[color].unique()
        series_list = []
        for i, g in enumerate(groups):
            group_data = df_plot[df_plot[color] == g]
            g_y = group_data.set_index(x).reindex(df_plot[x].unique())[y].fillna(0).tolist()
            series_list.append({
                "name": str(g), "type": "bar",
                "data": g_y,
                "itemStyle": {"color": WARM_COLORS[i % len(WARM_COLORS)]}
            })
        option["series"] = series_list
    else:
        option["series"] = [{
            "name": y, "type": "bar",
            "data": [{"value": v, "itemStyle": {"color": WARM_COLORS[i % len(WARM_COLORS)]}}
                     for i, v in enumerate(y_values)]
        }]

    return option


def create_line_chart(df: pd.DataFrame, x: str, y: Optional[str] = None,
                      title: str = "折线图", color: Optional[str] = None, **ignored) -> Dict[str, Any]:
    """创建折线图 ECharts option — 自动对省份/地区列分组聚合"""
    if y is None:
        counts = df[x].value_counts().sort_index().reset_index()
        counts.columns = [x, 'count']
        y = 'count'
        df_plot = counts
    else:
        # ★ 自动分组：X 轴是省份/地区等分类列时 groupby 聚合
        df_plot = _auto_groupby(df, x, y)

    df_plot = _sort_data(df_plot, x, y)
    x_data = df_plot[x].astype(str).tolist()

    option = {
        **_get_default_title(title),
        "tooltip": DARK_THEME["tooltip"],
        "legend": DARK_THEME["legend"],
        "toolbox": DARK_THEME["toolbox"],
        "grid": {"top": 60, "left": 50, "right": 20, "bottom": 40},
        "xAxis": {"type": "category", "data": x_data, "boundaryGap": False,
                  "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}},
        "yAxis": {"type": "value", "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}},
    }

    if color and color in df.columns:
        groups = df_plot[color].unique()
        series_list = []
        for i, g in enumerate(groups):
            group_data = df_plot[df_plot[color] == g]
            g_y = group_data.set_index(x).reindex(df_plot[x].unique())[y].fillna(0).tolist()
            series_list.append({
                "name": str(g), "type": "line",
                "data": g_y, "smooth": True,
                "lineStyle": {"color": WARM_COLORS[i % len(WARM_COLORS)]},
                "itemStyle": {"color": WARM_COLORS[i % len(WARM_COLORS)]},
            })
        option["series"] = series_list
    else:
        option["series"] = [{
            "name": y, "type": "line",
            "data": df_plot[y].fillna(0).tolist(),
            "smooth": True,
            "lineStyle": {"color": WARM_COLORS[0]},
            "itemStyle": {"color": WARM_COLORS[0]},
        }]
    return option


def create_area_chart(df: pd.DataFrame, x: str, y: Optional[str] = None,
                      title: str = "面积图", color: Optional[str] = None, **ignored) -> Dict[str, Any]:
    """创建面积图"""
    option = create_line_chart(df, x, y, title, color)
    for s in option.get("series", []):
        s["areaStyle"] = {"opacity": 0.3}
    return option


def create_scatter_chart(df: pd.DataFrame, x: str, y: Optional[str] = None,
                         title: str = "散点图", color: Optional[str] = None, **ignored) -> Dict[str, Any]:
    """创建散点图"""
    if y is None:
        raise ValueError("散点图需要同时指定 X 轴和 Y 轴")

    option = {
        **_get_default_title(title),
        "tooltip": DARK_THEME["tooltip"],
        "legend": DARK_THEME["legend"],
        "toolbox": DARK_THEME["toolbox"],
        "grid": {"top": 60, "left": 50, "right": 20, "bottom": 40},
        "xAxis": {"type": "value", "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}},
        "yAxis": {"type": "value", "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}},
    }

    if color and color in df.columns:
        groups = df[color].unique()
        series_list = []
        for i, g in enumerate(groups):
            group_data = df[df[color] == g]
            pts = [
                [float(row[x]), float(row[y])]
                for _, row in group_data.iterrows()
                if pd.notna(row[x]) and pd.notna(row[y])
            ]
            series_list.append({
                "name": str(g), "type": "scatter",
                "data": pts,
                "symbolSize": 8,
                "itemStyle": {"color": WARM_COLORS[i % len(WARM_COLORS)]}
            })
        option["series"] = series_list
    else:
        pts = [
            [float(row[x]), float(row[y])]
            for _, row in df.iterrows()
            if pd.notna(row[x]) and pd.notna(row[y])
        ]
        option["series"] = [{
            "name": f"{x}-{y}", "type": "scatter",
            "data": pts,
            "symbolSize": 8,
            "itemStyle": {"color": WARM_COLORS[0]}
        }]
    return option


def create_pie_chart(df: pd.DataFrame, names: Optional[str] = None, values: Optional[str] = None,
                     x: Optional[str] = None, y: Optional[str] = None,
                     title: str = "饼图", **ignored) -> Dict[str, Any]:
    """创建饼图"""
    names = names or x
    values = values or y

    if names is None:
        raise ValueError("饼图需要指定分类列")

    if values:
        data = df.groupby(names)[values].sum().reset_index()
    else:
        data = df[names].value_counts().reset_index()
        data.columns = [names, 'count']
        values = 'count'

    pie_data = []
    for i, (_, row) in enumerate(data.iterrows()):
        pie_data.append({
            "name": str(row[names]),
            "value": float(row[values]),
            "itemStyle": {"color": WARM_COLORS[i % len(WARM_COLORS)]}
        })

    return {
        **_get_default_title(title),
        "tooltip": DARK_THEME["tooltip"],
        "legend": DARK_THEME["legend"],
        "toolbox": DARK_THEME["toolbox"],
        "series": [{
            "type": "pie",
            "radius": ["35%", "65%"],
            "center": ["50%", "50%"],
            "emphasis": {
                "label": {"fontSize": 18, "fontWeight": "bold"},
                "scaleSize": 10
            },
            "data": pie_data,
            "label": {"color": "#94a3b8"},
            "labelLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}},
        }]
    }


def create_histogram(df: pd.DataFrame, x: str, title: str = "直方图", **ignored) -> Dict[str, Any]:
    """创建直方图（用 bar 模拟，手动分箱 — ECharts 无内置 histogram 类型）"""
    values = df[x].dropna()
    if len(values) == 0:
        raise ValueError("直方图需要数值数据")

    # 自动计算分箱数
    n_bins = min(20, max(5, int(len(values) ** 0.5)))
    min_val, max_val = float(values.min()), float(values.max())
    bin_width = (max_val - min_val) / n_bins if max_val > min_val else 1

    bins = [min_val + i * bin_width for i in range(n_bins + 1)]
    labels = [f"{bins[i]:.1f}-{bins[i+1]:.1f}" for i in range(n_bins)]

    # 统计每个区间的频次
    counts = [0] * n_bins
    for v in values:
        idx = min(int((float(v) - min_val) / bin_width), n_bins - 1)
        counts[idx] += 1

    return {
        **_get_default_title(title),
        "tooltip": DARK_THEME["tooltip"],
        "toolbox": DARK_THEME["toolbox"],
        "grid": {"top": 60, "left": 50, "right": 20, "bottom": 50},
        "xAxis": {
            "type": "category", "data": labels, "name": x,
            "axisLabel": {"rotate": 30, "fontSize": 10},
            "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}
        },
        "yAxis": {
            "type": "value", "name": "频次",
            "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}
        },
        "series": [{
            "name": "频次", "type": "bar",
            "data": counts,
            "itemStyle": {"color": WARM_COLORS[0]},
            "barWidth": "90%",
        }]
    }


def create_box_plot(df: pd.DataFrame, y: str, x: Optional[str] = None,
                    title: str = "箱线图", **ignored) -> Dict[str, Any]:
    """创建箱线图"""
    option = {
        **_get_default_title(title),
        "tooltip": DARK_THEME["tooltip"],
        "toolbox": DARK_THEME["toolbox"],
        "grid": {"top": 60, "left": 50, "right": 20, "bottom": 40},
    }

    if x and x in df.columns:
        groups = df[x].dropna().unique()
        x_data = [str(g) for g in groups]
        box_data = []
        for i, g in enumerate(groups):
            group_vals = df[df[x] == g][y].dropna().tolist()
            box_data.append({
                "name": str(g),
                "value": group_vals,
            })
        option["xAxis"] = {"type": "category", "data": x_data, "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}}
        option["yAxis"] = {"type": "value", "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}}
        option["series"] = [{
            "name": y, "type": "boxplot",
            "data": [
                {
                    "name": str(groups[i]),
                    "value": [
                        np.percentile(v, 0) if v else 0,    # min
                        np.percentile(v, 25) if v else 0,   # Q1
                        np.percentile(v, 50) if v else 0,   # median
                        np.percentile(v, 75) if v else 0,   # Q3
                        np.percentile(v, 100) if v else 0,  # max
                    ]
                }
                for i, v in enumerate([df[df[x] == g][y].dropna().tolist() for g in groups])
            ],
            "itemStyle": {"color": WARM_COLORS[0], "borderColor": WARM_COLORS[1]},
            "boxWidth": [20, 40],
        }]
    else:
        vals = df[y].dropna().tolist()
        option["xAxis"] = {"type": "category", "data": [y], "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}}
        option["yAxis"] = {"type": "value", "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}}
        option["series"] = [{
            "name": y, "type": "boxplot",
            "data": [[
                np.percentile(vals, 0), np.percentile(vals, 25),
                np.percentile(vals, 50), np.percentile(vals, 75),
                np.percentile(vals, 100)
            ]],
            "itemStyle": {"color": WARM_COLORS[0], "borderColor": WARM_COLORS[1]},
        }]
    return option


def create_heatmap(df: pd.DataFrame, title: str = "相关性热力图", **ignored) -> Optional[Dict[str, Any]]:
    """创建相关性热力图"""
    numeric_df = df.select_dtypes(include=[np.number])
    if len(numeric_df.columns) < 2:
        return None

    corr = numeric_df.corr()
    x_data = corr.columns.tolist()
    y_data = corr.index.tolist()
    data = []
    max_val = 0
    for i, row_name in enumerate(y_data):
        for j, col_name in enumerate(x_data):
            v = round(float(corr.iloc[i, j]), 2)
            data.append([j, i, v])
            max_val = max(max_val, abs(v))

    return {
        **_get_default_title(title),
        "tooltip": DARK_THEME["tooltip"],
        "toolbox": DARK_THEME["toolbox"],
        "grid": {"top": 60, "left": 80, "right": 40, "bottom": 40},
        "xAxis": {"type": "category", "data": x_data, "axisLabel": {"rotate": 30},
                  "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}, "position": "top"},
        "yAxis": {"type": "category", "data": y_data,
                  "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}},
        "visualMap": {
            "min": -max_val, "max": max_val,
            "inRange": {"color": ["#23304E", "#1E3A8A", "#0369a1", "#38BDF8", "#7DD3FC"]},
            "text": ["正相关", "负相关"],
            "textStyle": {"color": "#94a3b8"},
            "calculable": True,
            "orient": "horizontal",
            "left": "center",
            "bottom": 0,
        },
        "series": [{
            "type": "heatmap", "data": data,
            "label": {"show": True, "color": "#e2e8f0", "fontSize": 11,
                      "formatter": "{@[2]}"},
            "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.5)"}},
            "itemStyle": {"borderColor": "#1e1e3a", "borderWidth": 1},
        }]
    }


def create_radar_chart(df: pd.DataFrame, x: Optional[str] = None, y: Optional[str] = None,
                       title: str = "雷达图", **ignored) -> Dict[str, Any]:
    """创建雷达图"""
    cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    dim_cols = df.select_dtypes(include=['number']).columns.tolist()

    if not dim_cols:
        raise ValueError("雷达图需要数值列")

    if len(dim_cols) > 8:
        dim_cols = dim_cols[:8]  # 雷达图最多8个维度

    title = f"雷达图（{' · '.join(dim_cols)}）"

    group_col = x if x and x in cat_cols else (cat_cols[0] if cat_cols else None)

    indicator = [{"name": c, "max": float(df[c].max() * 1.2)} for c in dim_cols]

    if group_col:
        agg = df.groupby(group_col)[dim_cols].mean().reset_index()
        series_list = []
        for i, (_, row) in enumerate(agg.iterrows()):
            series_list.append({
                "name": str(row[group_col]),
                "type": "radar",
                "data": [{"value": [float(row[c]) for c in dim_cols],
                          "name": str(row[group_col])}],
                "lineStyle": {"color": WARM_COLORS[i % len(WARM_COLORS)]},
                "areaStyle": {"color": WARM_COLORS[i % len(WARM_COLORS)], "opacity": 0.15},
                "symbolSize": 6,
            })
    else:
        means = [float(df[c].mean()) for c in dim_cols]
        series_list = [{
            "name": "平均值", "type": "radar",
            "data": [{"value": means, "name": "平均值"}],
            "lineStyle": {"color": WARM_COLORS[0]},
            "areaStyle": {"color": WARM_COLORS[0], "opacity": 0.15},
            "symbolSize": 6,
        }]

    return {
        **_get_default_title(title),
        "tooltip": DARK_THEME["tooltip"],
        "legend": DARK_THEME["legend"],
        "toolbox": DARK_THEME["toolbox"],
        "radar": {
            "indicator": indicator,
            "center": ["50%", "55%"],
            "radius": "65%",
            "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}},
            "splitArea": {"areaStyle": {"color": ["rgba(56,189,248,0.03)", "rgba(56,189,248,0.06)"]}},
        },
        "series": series_list,
    }


def create_stacked_bar(df: pd.DataFrame, x: str, y: Optional[str] = None,
                       color: Optional[str] = None, title: str = "堆叠柱状图", **ignored) -> Dict[str, Any]:
    """创建堆叠柱状图"""
    option = create_bar_chart(df, x, y, title, color)
    for s in option.get("series", []):
        s["stack"] = "total"
    return option


def create_waterfall(df: pd.DataFrame, x: str, y: Optional[str] = None,
                     title: str = "瀑布图", **ignored) -> Dict[str, Any]:
    """创建瀑布图（用堆叠柱状图模拟）— 自动对省份/地区列分组聚合"""
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    if y is None:
        if not numeric_cols:
            raise ValueError("瀑布图需要数值列")
        y = numeric_cols[0]

    # ★ 自动分组：X 轴是省份/地区等分类列时 groupby 聚合
    df_plot = _auto_groupby(df, x, y)

    values = df_plot[y].fillna(0).tolist()
    x_data = df_plot[x].astype(str).tolist()

    # 瀑布图：base = 前几项累积和
    base = [0]
    for i in range(len(values) - 1):
        base.append(base[-1] + values[i])

    option = {
        **_get_default_title(title),
        "tooltip": DARK_THEME["tooltip"],
        "toolbox": DARK_THEME["toolbox"],
        "grid": {"top": 60, "left": 60, "right": 20, "bottom": 40},
        "xAxis": {"type": "category", "data": x_data,
                  "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}},
        "yAxis": {"type": "value", "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}},
        "series": [
            {"name": "占位", "type": "bar", "stack": "waterfall",
             "data": base, "itemStyle": {"color": "transparent"},
             "label": {"show": False}},
            {"name": "变化", "type": "bar", "stack": "waterfall",
             "data": [{"value": v, "itemStyle": {"color": GALAXY["primary"] if v >= 0 else GALAXY["danger"]}}
                      for v in values]}
        ]
    }
    return option


def create_bubble_chart(df: pd.DataFrame, x: str, y: Optional[str] = None,
                        size: Optional[str] = None, color: Optional[str] = None,
                        title: str = "气泡图", **ignored) -> Dict[str, Any]:
    """创建气泡图"""
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    if not x or y is None:
        raise ValueError("气泡图需要 X 轴和 Y 轴")
    if size is None and len(numeric_cols) >= 3:
        size = numeric_cols[2]

    size_vals = df[size].fillna(10).tolist() if size else [10] * len(df)
    max_s = max(size_vals) if size_vals else 1
    scaled_sizes = [max(5, min(50, (s / max_s) * 40)) for s in size_vals]

    option = {
        **_get_default_title(title),
        "tooltip": DARK_THEME["tooltip"],
        "toolbox": DARK_THEME["toolbox"],
        "grid": {"top": 60, "left": 50, "right": 20, "bottom": 40},
        "xAxis": {"type": "value", "name": x, "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}},
        "yAxis": {"type": "value", "name": y, "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.08)"}}},
    }

    if color and color in df.columns:
        groups = df[color].unique()
        series_list = []
        for i, g in enumerate(groups):
            group_data = df[df[color] == g]
            pts = []
            for idx, (_, row) in enumerate(group_data.iterrows()):
                if pd.notna(row[x]) and pd.notna(row[y]):
                    pts.append([float(row[x]), float(row[y]), scaled_sizes[idx % len(scaled_sizes)] if size else 10])
            series_list.append({
                "name": str(g), "type": "scatter",
                "data": pts,
                "symbolSize": "function(data) { return data[2]; }",
                "itemStyle": {"color": WARM_COLORS[i % len(WARM_COLORS)], "opacity": 0.7},
            })
        option["series"] = series_list
    else:
        pts = []
        for idx, (_, row) in enumerate(df.iterrows()):
            if pd.notna(row[x]) and pd.notna(row[y]):
                pts.append([float(row[x]), float(row[y]), scaled_sizes[idx] if size else 10])
        option["series"] = [{
            "name": f"{x}-{y}", "type": "scatter",
            "data": pts,
            "symbolSize": "function(data) { return data[2]; }",
            "itemStyle": {"color": WARM_COLORS[0], "opacity": 0.7},
        }]
    return option


def create_treemap(df: pd.DataFrame, x: Optional[str] = None, y: Optional[str] = None,
                   title: str = "树状图", **ignored) -> Dict[str, Any]:
    """创建树状图"""
    cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()

    path_col = x if x and x in cat_cols else (cat_cols[0] if cat_cols else None)
    values_col = y if y and y in numeric_cols else (numeric_cols[0] if numeric_cols else None)

    if not path_col:
        raise ValueError("树状图需要分类列")

    if values_col:
        agg = df.groupby(path_col)[values_col].sum().reset_index()
    else:
        agg = df[path_col].value_counts().reset_index()
        agg.columns = [path_col, 'count']
        values_col = 'count'

    treemap_data = []
    for i, (_, row) in enumerate(agg.iterrows()):
        treemap_data.append({
            "name": str(row[path_col]),
            "value": float(row[values_col]),
            "itemStyle": {"color": WARM_COLORS[i % len(WARM_COLORS)]}
        })

    return {
        **_get_default_title(title),
        "tooltip": DARK_THEME["tooltip"],
        "series": [{
            "type": "treemap",
            "data": treemap_data,
            "label": {"color": "#e2e8f0"},
            "upperLabel": {"show": True, "height": 30},
            "itemStyle": {"borderColor": "#1e1e3a", "borderWidth": 2},
        }]
    }


def create_wordcloud(df: pd.DataFrame, x: Optional[str] = None, y: Optional[str] = None,
                     title: str = "词云图", **ignored) -> Dict[str, Any]:
    """创建词云图（用 ECharts 词云扩展，回退到柱状图）

    关键约束（基于 echarts-wordcloud 2.1.0 官方支持范围）：
    - 颜色 textStyle.color 必须是 string 或 function（**不支持 array**）。
      解决：用合法 JS 字符串拼 function 形式，从 BLUE_PALETTE 闭包取色。
    - 大小：value 直接传出现次数即可，echarts-wordcloud 会按 value 比例计算
      fontSize（value 越大 → 字越大 → 越靠中心）。通过 sizeRange 控制字号上下限。
    - 形状：默认 circle 已能让词分布开；适当减小 gridSize 让字能填更多位置。

    支持两种输入模式（2026-07-13 修复 value=1 链路后新增）：
    - **已聚合模式**（df 形如 [{name, value}, ...] 或 [{<text>, <count>}, ...]）：
      直接用 df 已有聚合结果，不重做 value_counts。
      判定：df 含 'name' 列或 (x,y) 真实列名都存在 → 已聚合。
    - **明细模式**：df 仍按文本列做 value_counts().head(50)。
    """
    # ===== 模式 1：已聚合数据 — df 已有 [{name, value}] 或 [{<text>, <count>}] =====
    if "name" in df.columns and "value" in df.columns:
        # 模板 build_charts 直接输出 ECharts 原生格式
        records = df[["name", "value"]].to_dict("records")
        cloud_data = [
            {"name": str(r["name"]), "value": int(r["value"])}
            for r in records if r.get("name") and r.get("value") is not None
        ]
    else:
        # ===== 模式 2：明细数据 — 选文本列后做 value_counts =====
        cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        text_col = x if x and x in cat_cols else (cat_cols[0] if cat_cols else None)

        if not text_col:
            raise ValueError("词云图需要文本/分类列")

        word_counts = df[text_col].value_counts().head(50)
        # value 直接是出现次数，ECharts 词云会按 value 自动算 fontSize
        cloud_data = [
            {"name": str(w), "value": int(c)}
            for w, c in zip(word_counts.index, word_counts.values)
        ]

    if not cloud_data:
        raise ValueError("词云图无可用数据")

    # ★★ 颜色方案根治（2026-07-13 修复「看板词云全黑、无报错」）★★
    # 根因（读 echarts-wordcloud 2.1.0 源码确认）：
    #   - WordCloudSeries.js: visualStyleAccessPath='textStyle'，visualStyleMapper 返回
    #     { fill: model.get('color') }，即颜色取自 textStyle.color；
    #   - WordCloudView.js L31: fill = data.getItemVisual(dataIdx, 'style').fill，
    #     直接把该 fill 交给 zrender 的 Text 元素。
    #   → 若 textStyle.color 是 **function**，zrender 拿到 function 当作无效填充色，
    #     所有词回退成默认黑色，且**不抛错**（这就是「全黑但 Console 无报错」的原因）。
    #   旧版（1.x + echarts4）靠把 color 传给 wordcloud2 的 settings.color 才使 function 生效，
    #   2.1.0 重构后已废弃该通路，故 color function 方案在 2.1.0 完全失效。
    #
    # 正解：**给每个 data item 直接附静态颜色**（合法字符串，非 function）。
    #   item 含 textStyle → echarts List.hasItemOption=True → 逐 item setItemVisual，
    #   getItemVisual(idx,'style').fill 得到静态色字符串 → zrender 正确逐词着色。
    #   无需前端水合、无 function 序列化坑，JSON 无损。
    for i, item in enumerate(cloud_data):
        item["textStyle"] = {"color": BLUE_PALETTE[i % len(BLUE_PALETTE)]}

    return {
        **_get_default_title(title),
        "tooltip": DARK_THEME["tooltip"],
        "series": [{
            "type": "wordCloud",
            "shape": "circle",
            "left": "center",
            "top": "center",
            "width": "95%",
            "height": "90%",
            "sizeRange": [16, 80],          # 字号范围，让头部/尾部视觉差异明显
            "rotationRange": [-30, 30],
            "rotationStep": 15,
            "gridSize": 6,                  # 调小让字能填更多位置，避免堆中心
            "drawOutOfBound": False,
            "shrinkToFit": True,
            "textStyle": {
                "fontFamily": "sans-serif",
                "fontWeight": "bold",
                # ★ series 级兜底静态色（合法字符串，绝不用 function）：
                #   万一某环境未逐 item 应用 per-item 色，series 级也是合法蓝、不会黑。
                "color": BLUE_PALETTE[0],
            },
            "emphasis": {
                "focus": "self",
                "textStyle": {
                    "textShadowBlur": 12,
                    "textShadowColor": GALAXY["ai"],
                }
            },
            "data": cloud_data,
        }]
    }


# ==================== 3D 地图（ECharts GL） ====================

# GeoJSON 省份全称映射（DataV 格式）
_GEO_PROVINCE_NAMES = {
    '北京': '北京市', '北京市': '北京市',
    '上海': '上海市', '上海市': '上海市',
    '天津': '天津市', '天津市': '天津市',
    '重庆': '重庆市', '重庆市': '重庆市',
    '河北': '河北省', '河北省': '河北省',
    '山西': '山西省', '山西省': '山西省',
    '辽宁': '辽宁省', '辽宁省': '辽宁省',
    '吉林': '吉林省', '吉林省': '吉林省',
    '黑龙江': '黑龙江省', '黑龙江省': '黑龙江省',
    '江苏': '江苏省', '江苏省': '江苏省',
    '浙江': '浙江省', '浙江省': '浙江省',
    '安徽': '安徽省', '安徽省': '安徽省',
    '福建': '福建省', '福建省': '福建省',
    '江西': '江西省', '江西省': '江西省',
    '山东': '山东省', '山东省': '山东省',
    '河南': '河南省', '河南省': '河南省',
    '湖北': '湖北省', '湖北省': '湖北省',
    '湖南': '湖南省', '湖南省': '湖南省',
    '广东': '广东省', '广东省': '广东省',
    '海南': '海南省', '海南省': '海南省',
    '四川': '四川省', '四川省': '四川省',
    '贵州': '贵州省', '贵州省': '贵州省',
    '云南': '云南省', '云南省': '云南省',
    '陕西': '陕西省', '陕西省': '陕西省',
    '甘肃': '甘肃省', '甘肃省': '甘肃省',
    '青海': '青海省', '青海省': '青海省',
    '台湾': '台湾省', '台湾省': '台湾省',
    '广西': '广西壮族自治区', '广西壮族自治区': '广西壮族自治区',
    '内蒙古': '内蒙古自治区', '内蒙古自治区': '内蒙古自治区',
    '西藏': '西藏自治区', '西藏自治区': '西藏自治区',
    '宁夏': '宁夏回族自治区', '宁夏回族自治区': '宁夏回族自治区',
    '新疆': '新疆维吾尔自治区', '新疆维吾尔自治区': '新疆维吾尔自治区',
    '香港': '香港特别行政区', '香港特别行政区': '香港特别行政区',
    '澳门': '澳门特别行政区', '澳门特别行政区': '澳门特别行政区',
}

# 省份中心坐标（用于 bar3D 放置柱子）
_PROVINCE_CENTROIDS = {
    '北京市': [116.4, 39.9], '天津市': [117.2, 39.1], '上海市': [121.5, 31.2], '重庆市': [106.5, 29.6],
    '河北省': [114.5, 38.0], '山西省': [112.5, 37.9], '辽宁省': [123.4, 41.8], '吉林省': [125.3, 43.9],
    '黑龙江省': [126.6, 45.8], '江苏省': [119.8, 33.0], '浙江省': [120.2, 30.3], '安徽省': [117.3, 31.8],
    '福建省': [119.3, 26.1], '江西省': [115.9, 27.7], '山东省': [117.0, 36.7], '河南省': [113.7, 33.9],
    '湖北省': [112.4, 31.2], '湖南省': [112.0, 27.1], '广东省': [113.5, 23.5], '海南省': [110.0, 19.2],
    '四川省': [102.2, 30.6], '贵州省': [106.7, 26.6], '云南省': [102.7, 25.0], '陕西省': [108.9, 34.3],
    '甘肃省': [103.8, 36.1], '青海省': [96.0, 36.5], '台湾省': [121.0, 24.0],
    '广西壮族自治区': [108.3, 22.8], '内蒙古自治区': [111.8, 40.8], '西藏自治区': [89.1, 31.5],
    '宁夏回族自治区': [106.3, 37.1], '新疆维吾尔自治区': [85.6, 42.1],
    '香港特别行政区': [114.2, 22.3],     '澳门特别行政区': [113.5, 22.2],
}

# ★ 省份→大区映射（用于按地区着色地图）
_PROVINCE_TO_REGION = {
    # 华东
    '上海市': '华东', '江苏省': '华东', '浙江省': '华东', '安徽省': '华东',
    '福建省': '华东', '江西省': '华东', '山东省': '华东',
    # 华北
    '北京市': '华北', '天津市': '华北', '河北省': '华北', '山西省': '华北',
    '内蒙古自治区': '华北',
    # 华中
    '河南省': '华中', '湖北省': '华中', '湖南省': '华中',
    # 华南
    '广东省': '华南', '广西壮族自治区': '华南', '海南省': '华南',
    # 西南
    '重庆市': '西南', '四川省': '西南', '贵州省': '西南', '云南省': '西南',
    '西藏自治区': '西南',
    # 东北
    '辽宁省': '东北', '吉林省': '东北', '黑龙江省': '东北',
    # 西北
    '陕西省': '西北', '甘肃省': '西北', '青海省': '西北',
    '宁夏回族自治区': '西北', '新疆维吾尔自治区': '西北',
    # 港澳台
    '香港特别行政区': '港澳台', '澳门特别行政区': '港澳台', '台湾省': '港澳台',
}

# ★ 大区中心坐标（用于地区模式下散点/标签）
_REGION_CENTROIDS = {
    '华东': [118.5, 32.5],
    '华北': [115.0, 40.0],
    '华中': [113.0, 32.0],
    '华南': [112.0, 23.0],
    '西南': [104.0, 29.0],
    '东北': [125.0, 44.0],
    '西北': [97.0, 38.0],
    '港澳台': [118.0, 24.0],
}


_CITY_TO_PROVINCE = {
    '深圳': '广东省', '广州': '广东省', '东莞': '广东省', '佛山': '广东省',
    '杭州': '浙江省', '宁波': '浙江省', '温州': '浙江省',
    '南京': '江苏省', '苏州': '江苏省', '无锡': '江苏省',
    '成都': '四川省', '武汉': '湖北省', '西安': '陕西省',
    '郑州': '河南省', '青岛': '山东省', '济南': '山东省',
    '长沙': '湖南省', '合肥': '安徽省', '福州': '福建省',
    '厦门': '福建省', '南昌': '江西省', '大连': '辽宁省',
    '沈阳': '辽宁省', '长春': '吉林省', '哈尔滨': '黑龙江省',
    '石家庄': '河北省', '太原': '山西省', '南宁': '广西壮族自治区',
    '昆明': '云南省', '贵阳': '贵州省', '兰州': '甘肃省',
    '呼和浩特': '内蒙古自治区', '乌鲁木齐': '新疆维吾尔自治区',
    '拉萨': '西藏自治区', '银川': '宁夏回族自治区',
    '海口': '海南省', '台北': '台湾省', '高雄': '台湾省',
}

def _to_geo_name(name: str) -> str:
    """将各种形式的省份名/城市名转为 GeoJSON 标准名称"""
    name_str = str(name).strip()
    
    if name_str in _CITY_TO_PROVINCE:
        return _CITY_TO_PROVINCE[name_str]
    
    cleaned = name_str.replace('省', '').replace('市', '').replace('自治区', '').replace('特别行政区', '').replace('壮族', '').replace('回族', '').replace('维吾尔', '').strip()
    return _GEO_PROVINCE_NAMES.get(name_str, _GEO_PROVINCE_NAMES.get(cleaned, name_str))


def _province_short_name(params: dict) -> str:
    """geo3D label formatter：将省份全称缩短为 2-3 字简称"""
    name = str(params.get('name', '') or params.get('properties', {}).get('name', ''))
    # 移除后缀
    short = name.replace('省', '').replace('市', '').replace('自治区', '').replace('特别行政区', '')
    short = short.replace('壮族', '').replace('回族', '').replace('维吾尔', '')
    short = short.strip()
    # 缩短长名
    if short == '内蒙古':
        short = '蒙'
    elif short == '黑龙江':
        short = '黑'
    elif len(short) > 3:
        short = short[:2]
    return short


def _build_geo3d_regions(map_data: list, min_val: float, max_val: float) -> list:
    """为 geo3D 构建 regions 配置，按数据值给省份上色"""
    val_range = max_val - min_val or 1
    gradient_colors = ["#13243F", "#0c4a6e", "#0369a1", "#0ea5e9", "#38BDF8", "#67E8F9", "#22D3EE"]
    regions = []
    for item in map_data:
        name = item["name"]
        val = item["value"]
        # 计算颜色索引
        ratio = (val - min_val) / val_range
        idx = int(ratio * (len(gradient_colors) - 1))
        idx = max(0, min(idx, len(gradient_colors) - 1))
        color = gradient_colors[idx]
        regions.append({
            "name": name,
            "itemStyle": {"areaColor": color, "opacity": 0.8},
            "label": {"show": True, "color": "#e2e8f0", "fontSize": 11, "formatter": "{b}"},
        })
    return regions


def _format_number(n: float) -> str:
    """格式化数字：万/亿 单位"""
    if abs(n) >= 1e8:
        return f"{n/1e8:.2f}亿"
    elif abs(n) >= 1e4:
        return f"{n/1e4:.1f}万"
    elif abs(n) >= 1000:
        return f"{n:,.0f}"
    elif abs(n) >= 1:
        return f"{n:.2f}"
    else:
        return f"{n:.4f}"


def _color_by_value(val: float, min_val: float, max_val: float) -> str:
    """星空渐变色：深空紫 → 星云蓝 → 星光青 → 超新星白"""
    gradient = [
        "#020617",  # 深空
        "#0B1B3A",  # 暗星云蓝
        "#0c4a6e",  # 蓝星云
        "#0369a1",  # 蓝星
        "#0ea5e9",  # 亮蓝
        "#38BDF8",  # 星光蓝
        "#22D3EE",  # 极光青
        "#67E8F9",  # 亮星蓝
        "#7DD3FC",  # 星白蓝
        "#BFE9FF",  # 浅蓝
        "#E6F7FF",  # 星白
    ]
    ratio = (val - min_val) / (max_val - min_val) if max_val != min_val else 0.5
    idx = int(ratio * (len(gradient) - 1))
    idx = max(0, min(idx, len(gradient) - 1))
    return gradient[idx]


def create_gl_map(df: pd.DataFrame, x: Optional[str] = None, y: Optional[str] = None,
                  title: str = "数据地图", **ignored) -> Dict[str, Any]:
    """星空主题 2D 数据地图：geo + effectScatter，省份标签 + 星光散点
    
    自动回退：如果 X 列值无法匹配 GeoJSON 省份名（如 X='地区' 值是华东/华北），
    会自动查找并切换到「省份」/「城市」等能匹配的列。
    """

    cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    num_cols = df.select_dtypes(include=['number']).columns.tolist()

    if not num_cols:
        raise ValueError("地图需要数值列")

    region_col = x if x and x in df.columns else (cat_cols[0] if cat_cols else None)
    value_col = y if y and y in num_cols else num_cols[0]
    if not region_col:
        raise ValueError("未找到地区/省份列，请选择包含省份或城市名称的列作为 X 轴")

    # ★ 检查当前 X 列的值是否能匹配 GeoJSON 省份名
    # 如果匹配率很低（如 X='地区' 时值是华东/华北），自动回退到「省份」列
    sample_names = df[region_col].dropna().astype(str).unique()[:20]
    match_count = sum(1 for n in sample_names if _to_geo_name(n) in _PROVINCE_CENTROIDS)
    match_rate = match_count / len(sample_names) if len(sample_names) > 0 else 0
    
    # ★ 地区→省份展开：X 值不是省份名时（如华东/华北），按大区聚合后展开到各省份
    is_region_mode = False
    region_province_map = {}   # region_name → [province_geo_names]
    province_region_map = {}   # province_geo_name → region_name (for tooltip)
    _original_region_col = region_col

    if match_rate < 0.3:
        # 尝试找 df 中的省份列来展开地区
        province_src_col = None
        for c in df.columns:
            cl = c.lower()
            if any(kw in cl for kw in ['省份', 'province', '省市', '城市', 'city']):
                province_src_col = c
                break

        if province_src_col and province_src_col != region_col:
            # 从数据中建立 地区→省份 映射
            _data_map = {}
            for _, row in df[[region_col, province_src_col]].drop_duplicates().iterrows():
                rname = str(row[region_col])
                pname = str(row[province_src_col])
                pgeo = _to_geo_name(pname)
                if pgeo and pgeo in _PROVINCE_CENTROIDS:
                    _data_map.setdefault(rname, []).append(pgeo)

            if _data_map:
                # 按地区聚合值
                region_agg = df.groupby(region_col, as_index=False)[value_col].sum()
                region_vals = dict(zip(region_agg[region_col].astype(str), region_agg[value_col]))

                # 展开：每个省份继承其所属地区的值
                expanded_rows = []
                for rname, prov_list in _data_map.items():
                    rval = region_vals.get(rname, 0)
                    for pgeo in prov_list:
                        expanded_rows.append({'province_geo': pgeo, value_col: rval})
                        province_region_map[pgeo] = rname
                    region_province_map[rname] = prov_list

                df_agg = pd.DataFrame(expanded_rows)
                region_col = 'province_geo'
                is_region_mode = True
                import logging
                logging.getLogger(__name__).info(
                    f"地图地区展开：X「{_original_region_col}」→ 省份级着色，"
                    f"{len(_data_map)} 个大区映射到 {len(expanded_rows)} 个省份"
                )

    # 非 region mode 的常规聚合
    if not is_region_mode:
        try:
            df_agg = df.groupby(region_col, as_index=False).agg({value_col: 'sum'})
        except Exception:
            df_agg = df[[region_col, value_col]].copy()
            df_agg.columns = [region_col, value_col]

        if not value_col or value_col not in df_agg.columns:
            raise ValueError(f"数值列 {value_col} 不存在或无法聚合")

        # 过滤掉映射失败的地名
        valid_rows = []
        skipped_count = 0
        for _, row in df_agg.iterrows():
            raw_name = str(row[region_col])
            geo_name = _to_geo_name(raw_name)
            if geo_name in _PROVINCE_CENTROIDS or _GEO_PROVINCE_NAMES.get(geo_name):
                valid_rows.append(row)
            else:
                skipped_count += 1
        if skipped_count > 0 and valid_rows:
            import logging
            skipped_names = [str(row[region_col]) for _, row in df_agg.iterrows()
                             if _to_geo_name(str(row[region_col])) not in _PROVINCE_CENTROIDS
                             and _GEO_PROVINCE_NAMES.get(_to_geo_name(str(row[region_col]))) is None]
            logging.getLogger(__name__).warning(
                f"地图过滤了 {skipped_count} 条无法匹配 GeoJSON 的地名"
                f"（如：{', '.join(n[:8] for n in skipped_names[:5])}）"
            )
            df_agg = pd.DataFrame(valid_rows)
        if df_agg.empty:
            raise ValueError(
                f"列「{region_col}」中的值（如 {', '.join(sample_names[:5])}）"
                f"无法匹配中国地图省份名。请尝试用「省份」列作为 X 轴。"
            )

    # 确保列存在
    if not value_col or value_col not in df_agg.columns:
        raise ValueError(f"数值列 {value_col} 不存在或无法聚合")

    max_val = float(df_agg[value_col].max())
    min_val = float(df_agg[value_col].min())

    regions = []
    scatter_data = []

    for _, row in df_agg.iterrows():
        if is_region_mode:
            # 已展开为 province_geo / value_col，直接从 df_agg 取值
            geo_name = str(row['province_geo'])
            val = float(row[value_col])
            rname = province_region_map.get(geo_name, '')
        else:
            raw_name = str(row[region_col])
            geo_name = _to_geo_name(raw_name)
            val = float(row[value_col])
            rname = ''

        color = _color_by_value(val, min_val, max_val)

        # 标签：region 模式显示地区名，否则显示省份名
        label_text = rname if is_region_mode and rname else geo_name
        regions.append({
            "name": geo_name,
            "itemStyle": {"areaColor": color},
            "label": {
                "show": True,
                "color": "#7DD3FC",
                "fontSize": 11,
            },
        })

        # 散点：region 模式用大区中心，省份模式用省份中心
        if is_region_mode and rname:
            centroid = _REGION_CENTROIDS.get(rname)
            point_name = rname
        else:
            centroid = _PROVINCE_CENTROIDS.get(geo_name)
            point_name = geo_name

        if centroid:
            scatter_data.append({
                "name": point_name,
                "value": [*centroid, val],
            })

    # region 模式下去重散点（同一大区的省份散点在同一坐标）
    if is_region_mode and scatter_data:
        _seen = {}
        _deduped = []
        for pt in scatter_data:
            key = pt["name"]
            if key not in _seen:
                _seen[key] = True
                _deduped.append(pt)
        scatter_data = _deduped

    # ★ 构建 region mode 下的 tooltip formatter：显示「地区名 → 省份名」
    _fmt_base = (title or value_col)
    if is_region_mode and province_region_map:
        tooltip_fmt = (
            "function(p) {"
            "  var pm = " + json.dumps(province_region_map, ensure_ascii=False) + ";"
            "  var r = pm[p.name] || '';"
            "  return '<b>' + p.name + '</b>"
            "        + (r ? '（' + r + '）' : '')"
            "        + '<br/>" + _fmt_base + ": ' + p.value[2];"
            "}"
        )
    else:
        tooltip_fmt = "{b}<br/>" + _fmt_base + ": {c}"

    # ★ region mode：隐藏省份标签，只显示大区名
    if is_region_mode:
        for r in regions:
            r.setdefault("label", {})["show"] = False

    result = {
        "backgroundColor": "transparent",
        "title": {
            "text": title,
            "left": "center",
            "top": 8,
            "textStyle": {"color": "#7DD3FC", "fontSize": 18, "fontWeight": "bold",
                          "textShadowBlur": 10, "textShadowColor": "rgba(59,130,246,0.5)"},
        },
        "tooltip": {
            "trigger": "item",
            "backgroundColor": "rgba(15,12,41,0.95)",
            "borderColor": "#38BDF8",
            "borderWidth": 1,
            "textStyle": {"color": "#F8FAFC", "fontSize": 13},
            "formatter": tooltip_fmt,
        },
        "visualMap": {
            "show": True,
            "min": min_val,
            "max": max_val,
            "calculable": False,
            "inRange": {"color": ["#13243F", "#0c4a6e", "#0369a1", "#0ea5e9", "#38BDF8", "#67E8F9", "#22D3EE"]},
            "textStyle": {"color": "#7DD3FC"},
            "orient": "horizontal",
            "left": "center",
            "bottom": 10,
        },
        "geo": {
            "map": "china",
            "roam": True,
            "zoom": 1.15,
            "center": [104.5, 36],
            "aspectScale": 0.85,
            "regions": regions,
            "itemStyle": {
                "areaColor": "#23304E",
                "borderColor": "rgba(255,255,255,0.08)",
                "borderWidth": 1,
                "shadowBlur": 6,
                "shadowColor": "rgba(56,189,248,0.25)",
            },
            "emphasis": {
                "itemStyle": {
                    "areaColor": "#38BDF8",
                    "shadowBlur": 25,
                    "shadowColor": "rgba(56,189,248,0.7)",
                },
                "label": {
                    "show": True,
                    "color": "#F8FAFC",
                    "fontSize": 14,
                    "fontWeight": "bold",
                    "textShadowBlur": 8,
                    "textShadowColor": "rgba(56,189,248,0.8)",
                },
            },
        },
        "series": [
            {
                "type": "effectScatter",
                "coordinateSystem": "geo",
                "data": scatter_data,
                "symbol": "circle",
                "symbolSize": 6,
                "showEffectOn": "render",
                "rippleEffect": {
                    "brushType": "stroke",
                    "scale": 4,
                    "period": 4,
                    "color": "#7DD3FC",
                },
                "itemStyle": {"color": "#F8FAFC", "shadowBlur": 10, "shadowColor": "rgba(56,189,248,0.8)"},
                "label": {
                    "show": True,
                    "position": "top",
                    "distance": 10,
                    "color": "#7DD3FC",
                    "fontSize": 11,
                    "fontWeight": "bold",
                    "formatter": "{c}",
                    "textShadowBlur": 6,
                    "textShadowColor": "rgba(56,189,248,0.6)",
                },
                "emphasis": {
                    "scale": 2,
                    "itemStyle": {"color": "#F8FAFC", "shadowBlur": 20, "shadowColor": "rgba(56,189,248,0.9)"},
                    "label": {"fontSize": 15, "color": "#F8FAFC"},
                },
            },
        ],
    }

    # ★ region mode 覆盖：隐藏省份标签，突出大区名称
    if is_region_mode:
        # 隐藏所有省份标签（包括 hover 时）
        result["geo"]["label"] = {"show": False}
        result["geo"]["emphasis"]["label"]["show"] = False
        # 放大散点并显示大区名 + 数值
        result["series"][0]["symbolSize"] = 14
        result["series"][0]["label"].update({
            "show": True,
            "fontSize": 15,
            "fontWeight": "bold",
            "color": "#F8FAFC",
            "formatter": "{b}\n{c}",
            "textShadowBlur": 10,
            "textShadowColor": "rgba(56,189,248,0.9)",
        })

    return result


# ==================== 降采样工具函数 ====================

def _downsample_indices(n: int, max_n: int) -> list:
    """返回 [0, n) 内均匀分布的 <=max_n 个下标（含首尾，按 np.linspace 取整去重）。"""
    if n <= max_n:
        return list(range(n))
    indices = np.linspace(0, n - 1, max_n, dtype=int)
    return sorted(set(int(i) for i in indices))


def _cap_option_data(option: dict) -> dict:
    """统一护栏：对类目轴 / 数值散点 / 饼图 / 热力图超大序列做均匀降采样。
    仅在超出阈值时原地修改 option，小数据零影响。
    """
    if not option:
        return option

    series_list = option.get("series", [])
    if not series_list:
        return option

    # ---- 1. 类目轴图表（bar / line / area / histogram / waterfall / stacked_bar） ----
    x_axis = option.get("xAxis")
    if isinstance(x_axis, dict):
        x_data = x_axis.get("data")
    elif isinstance(x_axis, list) and len(x_axis) > 0:
        x_data = x_axis[0].get("data") if isinstance(x_axis[0], dict) else None
    else:
        x_data = None

    if x_data and isinstance(x_data, list) and len(x_data) > _MAX_CATEGORY:
        keep_idxs = _downsample_indices(len(x_data), _MAX_CATEGORY)
        # 裁剪 xAxis.data
        x_axis["data"] = [x_data[i] for i in keep_idxs]
        # 同步裁剪每个 series.data
        for s in series_list:
            s_data = s.get("data")
            if isinstance(s_data, list):
                s["data"] = [s_data[i] for i in keep_idxs if i < len(s_data)]
        return option

    # ---- 2. 数值轴散点/气泡（data 为 [x,y] 或 [x,y,size] 数组） ----
    #    无 xAxis.data 但有系列 data 超过上限 → 均匀采样
    for s in series_list:
        s_type = str(s.get("type", ""))
        s_data = s.get("data", [])
        if not isinstance(s_data, list) or len(s_data) <= _MAX_SERIES_POINTS:
            continue
        # 只对散点/气泡类做采样（折线/柱状的数值轴情况 → 通常类目轴已处理，此处仅保护）
        if s_type in ("scatter", "bubble", "effectScatter"):
            keep_idxs = _downsample_indices(len(s_data), _MAX_SERIES_POINTS)
            s["data"] = [s_data[i] for i in keep_idxs]
        elif s_type in ("bar", "line", "area"):
            # 无类目轴的数值型 → 仍需采样
            keep_idxs = _downsample_indices(len(s_data), _MAX_SERIES_POINTS)
            s["data"] = [s_data[i] for i in keep_idxs]
        # 箱线图 series.data 通常很小，跳过
        # 其他类型：仅当 data 是纯数组时采样
        elif all(isinstance(d, (int, float)) for d in s_data[:10] if d is not None):
            keep_idxs = _downsample_indices(len(s_data), _MAX_SERIES_POINTS)
            s["data"] = [s_data[i] for i in keep_idxs]

    # ---- 3. 饼图 / 树图 / 词云：Top N + "其他" ----
    for s in series_list:
        s_type = str(s.get("type", ""))
        if s_type not in ("pie", "treemap", "wordCloud"):
            continue
        s_data = s.get("data", [])
        if not isinstance(s_data, list) or len(s_data) <= _MAX_PIE_SLICES:
            continue
        # 按 value 降序取 Top N
        def _val(d):
            if isinstance(d, dict):
                return float(d.get("value", 0) or 0)
            return float(d) if isinstance(d, (int, float)) else 0
        sorted_data = sorted(s_data, key=_val, reverse=True)
        top = sorted_data[:_MAX_PIE_SLICES - 1]
        rest = sorted_data[_MAX_PIE_SLICES - 1:]
        other_val = sum(_val(d) for d in rest)
        if other_val > 0:
            top.append({"name": "其他(合计)", "value": other_val,
                        "itemStyle": {"color": "rgba(255,255,255,0.08)"}})
        s["data"] = top

    # ---- 4. 热力图：缩小类目矩阵 ----
    has_heatmap = any(str(s.get("type")) == "heatmap" for s in series_list)
    if has_heatmap:
        for axis_key in ("xAxis", "yAxis"):
            ax = option.get(axis_key)
            if isinstance(ax, dict):
                ax_data = ax.get("data")
                if isinstance(ax_data, list) and len(ax_data) > _MAX_CATEGORY:
                    keep_idxs = _downsample_indices(len(ax_data), _MAX_CATEGORY)
                    idx_set = set(keep_idxs)
                    ax["data"] = [ax_data[i] for i in keep_idxs]
                    # 同步裁剪 heatmap series.data（格式 [col_idx, row_idx, val]）
                    for s in series_list:
                        if str(s.get("type")) != "heatmap":
                            continue
                        hd = s.get("data", [])
                        if isinstance(hd, list):
                            s["data"] = [
                                d for d in hd
                                if (isinstance(d, (list, tuple)) and len(d) >= 2
                                    and d[0] in idx_set and d[1] in idx_set)
                            ]
            elif isinstance(ax, list) and len(ax) > 0 and isinstance(ax[0], dict):
                ax_data = ax[0].get("data")
                if isinstance(ax_data, list) and len(ax_data) > _MAX_CATEGORY:
                    keep_idxs = _downsample_indices(len(ax_data), _MAX_CATEGORY)
                    idx_set = set(keep_idxs)
                    ax[0]["data"] = [ax_data[i] for i in keep_idxs]
                    for s in series_list:
                        if str(s.get("type")) != "heatmap":
                            continue
                        hd = s.get("data", [])
                        if isinstance(hd, list):
                            s["data"] = [
                                d for d in hd
                                if (isinstance(d, (list, tuple)) and len(d) >= 2
                                    and d[0] in idx_set and d[1] in idx_set)
                            ]

    return option


# ==================== 统一入口 ====================

CHART_FUNCTIONS = {
    "bar": create_bar_chart,
    "stacked_bar": create_stacked_bar,
    "line": create_line_chart,
    "area": create_area_chart,
    "scatter": create_scatter_chart,
    "bubble": create_bubble_chart,
    "pie": create_pie_chart,
    "histogram": create_histogram,
    "box": create_box_plot,
    "heatmap": create_heatmap,
    "radar": create_radar_chart,
    "waterfall": create_waterfall,
    "treemap": create_treemap,
    "wordcloud": create_wordcloud,
    "gl_map": create_gl_map,
    "map_3d": create_gl_map,  # 别名：数据洞察规则中"地区分布→3D地图"使用的类型名
}


def create_chart(df: pd.DataFrame, chart_type: str, **kwargs) -> Optional[Dict[str, Any]]:
    """统一 ECharts 图表创建入口，返回 ECharts option 字典（自动降采样护栏）"""
    if chart_type not in CHART_FUNCTIONS:
        raise ValueError(f"不支持的图表类型: {chart_type}。支持: {list(CHART_FUNCTIONS.keys())}")

    option = CHART_FUNCTIONS[chart_type](df, **kwargs)
    if option is not None:
        option = _cap_option_data(option)
    return option
