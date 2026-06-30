"""
图表生成模块 - 基础图表 + AI 智能推荐
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Any, Optional, List
import numpy as np

# 暖色调配色方案
WARM_COLORS = {
    "primary": "#E8833A",
    "secondary": "#F4A261",
    "accent": "#D4825A",
    "success": "#66BB6A",
    "warning": "#FFA726",
    "info": "#42A5F5",
    "palette": ["#E8833A", "#F4A261", "#D4825A", "#FFA726", "#66BB6A", "#42A5F5", "#AB47BC", "#EC407A"]
}

# ---- 图表和表格推荐规则（8 条核心规则） ----
# 规则 1: 趋势/走势类 → 折线图（看整体走向）
# 规则 2: 同比/环比类 → 折线图 + 排序表格（图看趋势，表看具体增减%）
# 规则 3: 对比/排名类 → 柱状图 + 排序表格（图看高低，表看精确数值）
# 规则 4: 占比/比例类 → 饼图 + 汇总表格（图看比例，表看各分类具体值）
# 规则 5: 地区分布类 → 3D 地图 + 汇总表格（图看全国分布，表看各省数据）
# 规则 6: 交叉分析类 → 堆叠柱状图 + 交叉表格（图看大致，表看交叉明细）
# 规则 7: 相关性类 → 散点图 + 相关系数表格
# 规则 8: 分布类 → 直方图（纯图即可）

GEO_KEYWORDS_CHART = ["省", "市", "区", "县", "地区", "区域", "省份", "城市", "province", "city", "region"]

# ★ 地图推荐时优先匹配的列名（拼音序：省份 > 城市 > 地区 > 区域）
# 因为「地区」列的值往往是华东/华北等大区名，不能匹配 GeoJSON 省份名
MAP_PREFERRED_GEO_COLS = ['省份', 'province', '城市', 'city', '省市', '省', '市']


def _is_geo_column(col: str) -> bool:
    """判断列名是否为地区/地理类"""
    return any(kw in col.lower() for kw in GEO_KEYWORDS_CHART)


def get_chart_recommendations(df: pd.DataFrame, target_col: Optional[str] = None) -> List[Dict[str, Any]]:
    """按照 8 条核心规则智能推荐图表类型 + 表格配对"""
    recommendations = []
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    datetime_cols = df.select_dtypes(include=['datetime64']).columns.tolist()

    # ---- 规则 1: 趋势/走势类 → 折线图 ----
    if datetime_cols and numeric_cols:
        for m in numeric_cols[:3]:
            recommendations.append({
                "type": "line",
                "title": f"{m}趋势分析",
                "x": datetime_cols[0],
                "y": m,
                "table_type": None,
                "reason": "趋势/走势类 → 折线图（看整体走向）",
            })

    # ---- 规则 2: 同比/环比类 → 排序表格（同环比专用） ----
    if datetime_cols and numeric_cols:
        for m in numeric_cols[:3]:
            recommendations.append({
                "type": "table",
                "title": f"{m}同环比分析表",
                "x": datetime_cols[0],
                "y": m,
                "table_type": "sort",
                "analysis_type": "yoy_mom",
                "reason": "同比/环比类 → 排序表格（表看具体增减%）",
            })

    # ---- 规则 3: 对比/排名类 → 柱状图 + 排序表格 ----
    if categorical_cols and numeric_cols:
        non_geo_cats = [c for c in categorical_cols if not _is_geo_column(c)]
        for cat in non_geo_cats[:2]:
            for m in numeric_cols[:2]:
                recommendations.append({
                    "type": "bar",
                    "title": f"各{cat}{m}排名",
                    "x": cat,
                    "y": m,
                    "table_type": "sort",
                    "reason": "对比/排名类 → 柱状图 + 排序表格（图看高低，表看精确数值）",
                })

    # ---- 规则 4: 占比/比例类 → 饼图 + 汇总表格 ----
    if categorical_cols:
        non_geo_cats = [c for c in categorical_cols if not _is_geo_column(c) and df[c].nunique() <= 15]
        for cat in non_geo_cats[:2]:
            val = numeric_cols[0] if numeric_cols else None
            recommendations.append({
                "type": "pie",
                "title": f"各{cat}{val + '占比' if val else '分布'}",
                "x": cat,
                "y": val,
                "table_type": "summary",
                "reason": "占比/比例类 → 饼图 + 汇总表格（图看比例，表看各分类具体值）",
            })

    # ---- 规则 5: 地区分布类 → 3D 地图 + 汇总表格 ----
    if categorical_cols and numeric_cols:
        geo_cats = [c for c in categorical_cols if _is_geo_column(c)]
        # ★ 排序：省份类列优先于地区/区域类列（因为「地区」值如华东/华北不能匹配 GeoJSON）
        geo_cats.sort(key=lambda c: (
            # 优先分：列名精确匹配「省份」得 0，「城市」得 1，「地区」得 2，其他得 3
            0 if any(kw == c for kw in ['省份', 'province', '省市']) else
            1 if any(kw in c.lower() for kw in ['城市', 'city']) else
            2 if '地区' == c or '区域' == c else 3
        ))
        for cat in geo_cats[:2]:
            for m in numeric_cols[:2]:
                recommendations.append({
                    "type": "map_3d",
                    "title": f"全国{cat}{m}分布",
                    "x": cat,
                    "y": m,
                    "table_type": "summary",
                    "reason": "地区分布类 → 3D 地图 + 汇总表格（图看全国分布，表看各省数据）",
                })

    # ---- 规则 6: 交叉分析类 → 堆叠柱状图 + 交叉表格 ----
    non_geo_cats = [c for c in categorical_cols if not _is_geo_column(c)]
    if len(non_geo_cats) >= 2 and numeric_cols:
        d1, d2 = non_geo_cats[0], non_geo_cats[1]
        recommendations.append({
            "type": "stacked_bar",
            "title": f"{d1}×{d2} {numeric_cols[0]}交叉分析",
            "x": d1,
            "y": numeric_cols[0],
            "color": d2,
            "table_type": "cross",
            "reason": "交叉分析类 → 堆叠柱状图 + 交叉表格（图看大致，表看交叉明细）",
        })

    # ---- 规则 7: 相关性类 → 散点图 + 相关系数表格 ----
    if len(numeric_cols) >= 2:
        for i in range(min(len(numeric_cols), 3)):
            for j in range(i + 1, min(len(numeric_cols), 4)):
                recommendations.append({
                    "type": "scatter",
                    "title": f"{numeric_cols[i]} vs {numeric_cols[j]} 相关性分析",
                    "x": numeric_cols[i],
                    "y": numeric_cols[j],
                    "table_type": "correlation",
                    "reason": "相关性类 → 散点图 + 相关系数表格",
                })

    # ---- 规则 8: 分布类 → 直方图（纯图即可） ----
    for m in numeric_cols[:3]:
        recommendations.append({
            "type": "histogram",
            "title": f"{m}分布分析",
            "x": m,
            "table_type": None,
            "reason": "分布类 → 直方图（纯图即可）",
        })

    # ---- TopN 扩展：横向条形图 + 排序表格 ----
    if non_geo_cats and numeric_cols:
        for cat in non_geo_cats[:2]:
            for m in numeric_cols[:2]:
                recommendations.append({
                    "type": "horizontal_bar",
                    "title": f"{cat} Top10 - {m}",
                    "x": cat,
                    "y": m,
                    "table_type": "sort",
                    "top": 10,
                    "reason": "对比/排名类扩展 → 横向条形图 + 排序表格",
                })

    # 去重
    seen_titles = set()
    unique_results = []
    for r in recommendations:
        if r["title"] not in seen_titles:
            seen_titles.add(r["title"])
            unique_results.append(r)

    return unique_results[:10]  # 最多 10 个推荐

def create_bar_chart(df: pd.DataFrame, x: str, y: Optional[str] = None, title: str = "柱状图", 
                     color: Optional[str] = None, orientation: str = "v", **ignored) -> go.Figure:
    """创建柱状图"""
    if y is None:
        # 未指定 Y 轴时，自动计数
        counts = df[x].value_counts().reset_index()
        counts.columns = [x, 'count']
        y = 'count'
        df_plot = counts
    else:
        df_plot = df
    
    if orientation == "h":
        fig = px.bar(df_plot, y=x, x=y, title=title, orientation="h", color=color,
                     color_discrete_sequence=WARM_COLORS["palette"])
    else:
        fig = px.bar(df_plot, x=x, y=y, title=title, color=color,
                     color_discrete_sequence=WARM_COLORS["palette"])
    
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#F5E6D3",
        title_font_size=16,
        margin=dict(t=50, l=50, r=50, b=50)
    )
    return fig

def create_line_chart(df: pd.DataFrame, x: str, y: Optional[str] = None, title: str = "折线图",
                      color: Optional[str] = None, **ignored) -> go.Figure:
    """创建折线图"""
    if y is None:
        counts = df[x].value_counts().sort_index().reset_index()
        counts.columns = [x, 'count']
        y = 'count'
        df_plot = counts
    else:
        df_plot = df
    
    fig = px.line(df_plot, x=x, y=y, title=title, color=color,
                  color_discrete_sequence=WARM_COLORS["palette"])
    
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#F5E6D3",
        title_font_size=16,
        margin=dict(t=50, l=50, r=50, b=50)
    )
    return fig

def create_scatter_chart(df: pd.DataFrame, x: str, y: Optional[str] = None, title: str = "散点图",
                         color: Optional[str] = None, size: Optional[str] = None, **ignored) -> go.Figure:
    """创建散点图"""
    if y is None:
        raise ValueError("散点图需要同时指定 X 轴和 Y 轴")
    fig = px.scatter(df, x=x, y=y, title=title, color=color, size=size,
                     color_discrete_sequence=WARM_COLORS["palette"])
    
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#F5E6D3",
        title_font_size=16,
        margin=dict(t=50, l=50, r=50, b=50)
    )
    return fig

def create_pie_chart(df: pd.DataFrame, names: Optional[str] = None, values: Optional[str] = None,
                     x: Optional[str] = None, y: Optional[str] = None, title: str = "饼图", **ignored) -> go.Figure:
    """创建饼图（names/x = 分类列，values/y = 数值列）"""
    # 兼容 x/names, y/values 两种参数名
    names = names or x
    values = values or y
    
    if names is None:
        raise ValueError("饼图需要指定分类列（X 轴）")
    
    if values:
        # 指定了数值列：聚合求和
        data = df.groupby(names)[values].sum().reset_index()
    else:
        # 未指定数值列：直接计数
        data = df[names].value_counts().reset_index()
        data.columns = [names, 'count']
        values = 'count'
    
    fig = px.pie(data, values=values, names=names, title=title,
                 color_discrete_sequence=WARM_COLORS["palette"])
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#F5E6D3",
        title_font_size=16,
        margin=dict(t=50, l=50, r=50, b=50)
    )
    return fig

def create_histogram(df: pd.DataFrame, x: str, title: str = "直方图",
                     nbins: Optional[int] = None, **ignored) -> go.Figure:
    """创建直方图"""
    fig = px.histogram(df, x=x, title=title, nbins=nbins,
                       color_discrete_sequence=[WARM_COLORS["primary"]])
    
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#F5E6D3",
        title_font_size=16,
        margin=dict(t=50, l=50, r=50, b=50)
    )
    return fig

def create_box_plot(df: pd.DataFrame, y: str, x: Optional[str] = None, title: str = "箱线图", **ignored) -> go.Figure:
    """创建箱线图（异常值检测可视化）"""
    fig = px.box(df, x=x, y=y, title=title,
                 color_discrete_sequence=WARM_COLORS["palette"])
    
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#F5E6D3",
        title_font_size=16,
        margin=dict(t=50, l=50, r=50, b=50)
    )
    return fig

def create_heatmap(df: pd.DataFrame, title: str = "相关性热力图", **ignored) -> go.Figure:
    """创建相关性热力图"""
    numeric_df = df.select_dtypes(include=[np.number])
    if len(numeric_df.columns) < 2:
        return None
    
    corr = numeric_df.corr()
    
    fig = px.imshow(corr, text_auto=".2f", title=title,
                    color_continuous_scale=["#1A0F0A", "#E8833A", "#F4A261"],
                    aspect="auto")
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#F5E6D3",
        title_font_size=16,
        margin=dict(t=50, l=50, r=50, b=50)
    )
    return fig

# ==================== BI 常用图表类型 ====================

def create_stacked_bar(df: pd.DataFrame, x: str, y: Optional[str] = None, color: Optional[str] = None,
                       title: str = "堆叠柱状图", **ignored) -> go.Figure:
    """创建堆叠柱状图（对比构成比例）"""
    kwargs: dict = {"x": x, "title": title, "color_discrete_sequence": WARM_COLORS["palette"]}
    if y:
        kwargs["y"] = y
    if color:
        kwargs["color"] = color
    fig = px.bar(df, **kwargs, barmode='stack')
    fig.update_layout(
        template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font_color="#F5E6D3", title_font_size=16, margin=dict(t=50, l=50, r=50, b=50),
    )
    return fig


def create_area_chart(df: pd.DataFrame, x: str, y: Optional[str] = None, color: Optional[str] = None,
                      title: str = "面积图", **ignored) -> go.Figure:
    """创建面积图（趋势 + 量级）"""
    if y is None:
        counts = df[x].value_counts().sort_index().reset_index()
        counts.columns = [x, 'count']
        y = 'count'
        df_plot = counts
    else:
        df_plot = df
    fig = px.area(df_plot, x=x, y=y, title=title, color=color,
                  color_discrete_sequence=WARM_COLORS["palette"])
    fig.update_layout(
        template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font_color="#F5E6D3", title_font_size=16, margin=dict(t=50, l=50, r=50, b=50),
    )
    return fig


def create_radar_chart(df: pd.DataFrame, x: Optional[str] = None, y: Optional[str] = None,
                       title: str = "雷达图", **ignored) -> go.Figure:
    """创建雷达图（多维度对比）
    X 轴 = 分组列（如 department），Y 轴 = 指定数值列（单选或多选，不选则全部数值列）"""
    cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    
    # 确定要展示的数值维度（雷达图默认用全部数值列，不依赖 Y 轴选择）
    dim_cols = df.select_dtypes(include=['number']).columns.tolist()
    
    if not dim_cols:
        raise ValueError("雷达图需要数值列")
    
    # 标题追加维度信息
    if '雷达图' in title:
        title = f"雷达图（{' · '.join(dim_cols)}）"
    
    # 分组列
    group_col = x if x and x in cat_cols else (cat_cols[0] if cat_cols else None)
    
    if group_col:
        agg = df.groupby(group_col)[dim_cols].mean().reset_index()
        fig = go.Figure()
        for _, row in agg.iterrows():
            fig.add_trace(go.Scatterpolar(
                r=[row[c] for c in dim_cols],
                theta=dim_cols,
                fill='toself',
                name=str(row[group_col]),
                mode='lines+markers+text',
                marker=dict(size=8),
                text=dim_cols,
                textposition='top center',
                hoveron='fills+points',
            ))
    else:
        # 单组数据：取数值列的均值做雷达
        means = [df[c].mean() for c in dim_cols]
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=means, theta=dim_cols, fill='toself',
            name='平均值',
            mode='lines+markers+text',
            marker=dict(size=8),
            text=dim_cols,
            textposition='top center',
            hoveron='fills+points',
        ))
    
    fig.update_layout(
        title=title, template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)", font_color="#F5E6D3",
        polar=dict(
            radialaxis=dict(visible=True, gridcolor='rgba(255,255,255,0.1)'),
            angularaxis=dict(gridcolor='rgba(255,255,255,0.1)'),
        ),
        margin=dict(t=60, l=40, r=40, b=40),
    )
    return fig


def create_waterfall(df: pd.DataFrame, x: str, y: Optional[str] = None,
                     title: str = "瀑布图", **ignored) -> go.Figure:
    """创建瀑布图（展示增减变化）"""
    if y is None:
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if not numeric_cols:
            raise ValueError("瀑布图需要数值列")
        y = numeric_cols[0]
    
    data = df[[x, y]].copy()
    measure = ['relative'] * len(data)
    measure[0] = 'absolute'
    
    fig = go.Figure(go.Waterfall(
        name='变化', orientation='v',
        measure=measure,
        x=data[x],
        y=data[y],
        text=[f'{v:,.0f}' for v in data[y]],
        connector={'line': {'color': 'rgba(255,255,255,0.2)'}},
    ))
    fig.update_layout(
        title=title, template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font_color="#F5E6D3", margin=dict(t=50, l=50, r=50, b=50),
    )
    return fig


def create_bubble_chart(df: pd.DataFrame, x: str, y: Optional[str] = None,
                        size: Optional[str] = None, color: Optional[str] = None,
                        title: str = "气泡图", **ignored) -> go.Figure:
    """创建气泡图（三维数据关系）"""
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    if not x or y is None:
        raise ValueError("气泡图需要 X 轴和 Y 轴")
    if size is None and len(numeric_cols) >= 3:
        size = numeric_cols[2]
    fig = px.scatter(df, x=x, y=y, size=size, color=color,
                     title=title, color_discrete_sequence=WARM_COLORS["palette"])
    fig.update_layout(
        template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font_color="#F5E6D3", title_font_size=16, margin=dict(t=50, l=50, r=50, b=50),
    )
    return fig


def create_treemap(df: pd.DataFrame, x: Optional[str] = None, y: Optional[str] = None,
                   title: str = "树状图", **ignored) -> go.Figure:
    """创建树状图（层级占比）"""
    cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    
    path_col = x if x and x in cat_cols else (cat_cols[0] if cat_cols else None)
    values_col = y if y and y in numeric_cols else (numeric_cols[0] if numeric_cols else None)
    
    if not path_col:
        raise ValueError("树状图需要分类列")
    
    if values_col:
        agg = df.groupby(path_col)[values_col].sum().reset_index()
        fig = px.treemap(agg, path=[path_col], values=values_col, title=title,
                         color=values_col, color_continuous_scale=["#1A0F0A", "#E8833A", "#F4A261"])
    else:
        counts = df[path_col].value_counts().reset_index()
        counts.columns = [path_col, 'count']
        fig = px.treemap(counts, path=[path_col], values='count', title=title,
                         color_discrete_sequence=WARM_COLORS["palette"])
    
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        font_color="#F5E6D3", margin=dict(t=50, l=10, r=10, b=10),
    )
    return fig


def create_wordcloud(df: pd.DataFrame, x: Optional[str] = None, y: Optional[str] = None,
                     title: str = "词云图", **ignored) -> go.Figure:
    """创建词云图（基于文本列词频，用 Plotly 原生实现。只使用 x 文本列，y 参数忽略）"""
    cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    text_col = x if x and x in cat_cols else (cat_cols[0] if cat_cols else None)
    
    if not text_col:
        raise ValueError("词云图需要文本/分类列")
    
    # 统计词频
    word_counts = df[text_col].value_counts().head(30)
    words = word_counts.index.tolist()
    counts = word_counts.values
    
    # 计算字体大小（映射到 12-48 范围）
    max_count = counts.max()
    min_count = counts.min()
    if max_count > min_count:
        sizes = 12 + (counts - min_count) / (max_count - min_count) * 36
    else:
        sizes = [24] * len(counts)
    
    # 随机排列布局（模拟词云效果）
    np_sizes = np.array(sizes)
    import random
    random.seed(42)
    
    # 生成螺旋布局
    positions = []
    for i, w in enumerate(words):
        angle = i * 2.4  # 黄金角
        radius = (i + 1) ** 0.6 * 0.8
        x_pos = np.cos(angle) * radius
        y_pos = np.sin(angle) * radius
        positions.append((x_pos, y_pos))
    
    # 用散点 + 文字注释模拟词云
    fig = go.Figure()
    colors = [WARM_COLORS["palette"][i % len(WARM_COLORS["palette"])] for i in range(len(words))]
    
    for i, (w, c, s) in enumerate(zip(words, counts, sizes)):
        x_pos, y_pos = positions[i]
        fig.add_annotation(
            x=x_pos, y=y_pos,
            text=w,
            showarrow=False,
            font=dict(size=int(s), color=colors[i]),
            align='center',
        )
    
    # 添加不可见的散点来确定坐标范围
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    fig.add_trace(go.Scatter(
        x=xs, y=ys,
        mode='text',
        text=[''] * len(words),
        showlegend=False,
    ))
    
    fig.update_layout(
        title=title,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#F5E6D3",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, visible=False),
        margin=dict(t=50, l=20, r=20, b=20),
        height=400,
    )
    return fig


def create_chart(df: pd.DataFrame, chart_type: str, **kwargs) -> go.Figure:
    """统一图表创建入口"""
    chart_functions = {
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
    }
    
    if chart_type not in chart_functions:
        raise ValueError(f"不支持的图表类型: {chart_type}")
    
    return chart_functions[chart_type](df, **kwargs)
