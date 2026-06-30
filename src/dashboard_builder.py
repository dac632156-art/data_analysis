"""
仪表盘构建模块 - 关键指标卡片 + 图表平铺展示 + 可视化看板导出
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

def _calc_change(df: pd.DataFrame, col: str) -> Optional[float]:
    """尝试计算列的环比变化率（最后期 vs 前一期），返回百分比"""
    try:
        date_cols = df.select_dtypes(include=['datetime64', 'datetime']).columns
        if len(date_cols) == 0:
            # 尝试转换 object 类型日期列
            for c in df.select_dtypes(include=['object']).columns:
                try:
                    _ = pd.to_datetime(df[c], errors='coerce')
                    if _.notna().sum() > len(df) * 0.5:
                        date_cols = [c]  # type: ignore
                        break
                except Exception:
                    continue
        if len(date_cols) == 0:
            return None
        dcol = date_cols[0]
        df_sorted = df.copy()
        df_sorted['_tmp_date_'] = pd.to_datetime(df_sorted[dcol], errors='coerce')
        df_sorted = df_sorted.dropna(subset=['_tmp_date_']).sort_values('_tmp_date_').tail(20)
        if len(df_sorted) < 6:
            return None
        periods = df_sorted['_tmp_date_'].unique()
        if len(periods) < 2:
            return None
        # 最新一期 vs 上一期
        latest = periods[-1]
        prev = periods[-2]
        curr_avg = df_sorted[df_sorted['_tmp_date_'] == latest][col].mean()
        prev_avg = df_sorted[df_sorted['_tmp_date_'] == prev][col].mean()
        if pd.isna(curr_avg) or pd.isna(prev_avg) or prev_avg == 0:
            return None
        return round(float((curr_avg - prev_avg) / abs(prev_avg) * 100), 1)
    except Exception:
        return None


def calculate_kpis(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """计算关键指标（KPI），含环比变化率"""
    import numpy as np
    kpis = []
    numeric_cols = df.select_dtypes(include=['number']).columns
    
    # 基础 KPI
    kpis.append({
        "title": "总记录数",
        "value": f"{len(df):,}",
        "icon": "📊",
        "color": "#E8833A",
        "change": 0,
        "trend": "flat",
    })
    
    kpis.append({
        "title": "字段数",
        "value": f"{len(df.columns)}",
        "icon": "📋",
        "color": "#F4A261",
        "change": 0,
        "trend": "flat",
    })
    
    # 数值列 KPI（取前两个关键数值列，带环比变化）
    if len(numeric_cols) > 0:
        for i, col in enumerate(numeric_cols[:2]):
            mean_val = df[col].mean()
            total_val = df[col].sum()
            change = _calc_change(df, col)
            
            fmt_mean = f"{mean_val:,.2f}" if abs(mean_val) < 10000 else f"{mean_val:,.0f}"
            fmt_total = f"{total_val:,.0f}"
            
            trend = "flat"
            if change is not None:
                trend = "up" if change > 0 else "down" if change < 0 else "flat"
            
            kpis.append({
                "title": f"{col} 平均值",
                "value": fmt_mean,
                "icon": "📈",
                "color": "#E76F51",
                "change": change,
                "trend": trend,
            })
            
            trend = "flat"
            if change is not None:
                trend = "up" if change > 0 else "down"
            
            kpis.append({
                "title": f"{col} 总和",
                "value": fmt_total,
                "icon": "💰",
                "color": "#D4825A",
                "change": change,
                "trend": trend,
            })
    
    # 分类列 KPI
    cat_cols = df.select_dtypes(include=['object', 'category']).columns
    if len(cat_cols) > 0:
        first_cat = cat_cols[0]
        kpis.append({
            "title": f"{first_cat} 唯一值个数",
            "value": f"{df[first_cat].nunique()}",
            "icon": "🏷️",
            "color": "#8B6F47",
            "change": 0,
            "trend": "flat",
        })
    
    return kpis[:6]  # 最多返回 6 个 KPI

def create_chart_configs(df: pd.DataFrame, configs: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """根据配置列表生成图表（支持自定义选择）"""
    from src.chart_generator import create_chart
    charts = []
    for cfg in configs:
        chart_type = cfg.get("chart_type", "bar")
        x_col = cfg.get("x", "")
        y_col = cfg.get("y", "")
        title = cfg.get("title", "图表")
        
        if x_col not in df.columns:
            continue
        
        kwargs = {"x": x_col, "title": title}
        if y_col and y_col in df.columns:
            kwargs["y"] = y_col
        
        try:
            fig = create_chart(df, chart_type, **kwargs)
            if fig:
                charts.append({"title": title, "figure": fig})
        except Exception:
            continue
    
    return charts


def get_default_charts(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """获取默认仪表盘图表（覆盖常用 BI 图表类型）"""
    from src.chart_generator import (create_bar_chart, create_pie_chart,
                                      create_histogram, create_box_plot,
                                      create_heatmap, create_area_chart,
                                      create_radar_chart, create_treemap,
                                      create_wordcloud)
    charts = []
    
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    
    # 图表 1：分类列柱状图
    if cat_cols and numeric_cols:
        try:
            fig = create_bar_chart(df, x=cat_cols[0], y=numeric_cols[0],
                                    title=f"{cat_cols[0]} × {numeric_cols[0]} 对比")
            charts.append({"title": f"{cat_cols[0]} × {numeric_cols[0]} 对比", "figure": fig})
        except Exception:
            pass
    
    # 图表 2：饼图（类别占比）
    if cat_cols:
        try:
            fig = create_pie_chart(df, x=cat_cols[0], title=f"{cat_cols[0]} 占比")
            charts.append({"title": f"{cat_cols[0]} 占比", "figure": fig})
        except Exception:
            pass
    
    # 图表 3：数值列分布直方图
    if numeric_cols:
        try:
            fig = create_histogram(df, x=numeric_cols[0], title=f"{numeric_cols[0]} 分布")
            charts.append({"title": f"{numeric_cols[0]} 分布", "figure": fig})
        except Exception:
            pass
    
    # 图表 4：箱线图（异常值检测）
    if numeric_cols:
        try:
            fig = create_box_plot(df, y=numeric_cols[0],
                                   x=cat_cols[0] if cat_cols else None,
                                   title=f"{numeric_cols[0]} 箱线图")
            charts.append({"title": f"{numeric_cols[0]} 箱线图", "figure": fig})
        except Exception:
            pass
    
    # 图表 5：面积图（趋势）
    if cat_cols and numeric_cols:
        try:
            fig = create_area_chart(df, x=cat_cols[0], y=numeric_cols[0],
                                     title=f"{numeric_cols[0]} 变化趋势")
            charts.append({"title": f"{numeric_cols[0]} 变化趋势", "figure": fig})
        except Exception:
            pass
    
    # 图表 6：雷达图（多维度）
    if len(numeric_cols) >= 3:
        try:
            fig = create_radar_chart(df, title="多维度雷达图")
            charts.append({"title": "多维度雷达图", "figure": fig})
        except Exception:
            pass
    
    # 图表 7：热力图（相关性）
    if len(numeric_cols) >= 2:
        try:
            fig = create_heatmap(df, title="数值列相关性热力图")
            charts.append({"title": "相关性热力图", "figure": fig})
        except Exception:
            pass
    
    # 图表 8：树状图（层级占比）
    if cat_cols:
        try:
            fig = create_treemap(df, x=cat_cols[0],
                                  y=numeric_cols[0] if numeric_cols else None,
                                  title=f"{cat_cols[0]} 树状分布")
            charts.append({"title": f"{cat_cols[0]} 树状分布", "figure": fig})
        except Exception:
            pass
    
    # 图表 9：词云图
    if cat_cols:
        try:
            fig = create_wordcloud(df, x=cat_cols[0], title=f"{cat_cols[0]} 词云")
            charts.append({"title": f"{cat_cols[0]} 词云", "figure": fig})
        except Exception:
            pass
    
    return charts


def get_default_echart_configs(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """获取默认 ECharts 仪表盘图表配置（覆盖更全面的 BI 图表类型）"""
    configs = []
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()

    # 1. 柱状图：分类对比
    if cat_cols and numeric_cols:
        configs.append({"chart_type": "bar", "x": cat_cols[0], "y": numeric_cols[0],
                        "title": f"{cat_cols[0]} × {numeric_cols[0]} 柱状图"})
    # 2. 饼图：类别占比
    if cat_cols:
        configs.append({"chart_type": "pie", "x": cat_cols[0],
                        "title": f"{cat_cols[0]} 占比饼图"})
    # 3. 直方图：数值分布
    if numeric_cols:
        configs.append({"chart_type": "histogram", "x": numeric_cols[0],
                        "title": f"{numeric_cols[0]} 分布直方图"})
    # 4. 箱线图：异常值检测
    if numeric_cols:
        if cat_cols:
            configs.append({"chart_type": "box", "x": cat_cols[0],
                            "y": numeric_cols[0], "title": f"{numeric_cols[0]} 箱线图"})
        else:
            configs.append({"chart_type": "box", "x": numeric_cols[0],
                            "y": numeric_cols[0], "title": f"{numeric_cols[0]} 分布箱线图"})
    # 5. 散点图：数值关系
    if len(numeric_cols) >= 2:
        configs.append({"chart_type": "scatter", "x": numeric_cols[0],
                        "y": numeric_cols[1], "title": f"{numeric_cols[0]} vs {numeric_cols[1]} 散点图"})
    # 6. 折线图：趋势
    if cat_cols and numeric_cols:
        configs.append({"chart_type": "line", "x": cat_cols[0], "y": numeric_cols[0],
                        "title": f"{numeric_cols[0]} 趋势折线图"})
    # 7. 面积图
    if cat_cols and numeric_cols:
        configs.append({"chart_type": "area", "x": cat_cols[0], "y": numeric_cols[0],
                        "title": f"{numeric_cols[0]} 面积趋势图"})
    # 8. 堆叠柱状图
    if cat_cols and len(numeric_cols) >= 2:
        configs.append({"chart_type": "stacked_bar", "x": cat_cols[0], "y": numeric_cols[0],
                        "title": f"{cat_cols[0]} × {numeric_cols[0]} 堆叠柱状图"})
    # 9. 雷达图：多维度对比
    if len(numeric_cols) >= 3:
        configs.append({"chart_type": "radar", "x": cat_cols[0] if cat_cols else None,
                        "title": "多维度雷达图"})
    # 10. 热力图：相关性
    if len(numeric_cols) >= 3:
        configs.append({"chart_type": "heatmap", "title": "特征相关性热力图"})
    # 11. 树状图：层级占比
    if cat_cols:
        configs.append({"chart_type": "treemap", "x": cat_cols[0],
                        "title": f"{cat_cols[0]} 树状分布图"})
    # 12. 3D 地图：地理空间可视化（ECharts GL）
    if cat_cols and numeric_cols:
        configs.append({"chart_type": "gl_map", "x": cat_cols[0], "y": numeric_cols[0],
                        "title": "3D 数据地图"})

    return configs


def build_dashboard_html(df: pd.DataFrame, kpis: List[Dict[str, Any]],
                          charts: List[Dict[str, Any]], title: str = "数据可视化看板") -> str:
    """生成包含 KPI 卡片 + Plotly 图表的独立 HTML 可视化看板"""
    # KPI 卡片 HTML
    kpi_cards = ""
    colors = ["#E8833A", "#F4A261", "#E76F51", "#D4825A", "#2A9D8F", "#8B6F47"]
    for i, kpi in enumerate(kpis):
        color = kpi.get("颜色", colors[i % len(colors)])
        change_html = ""
        change_val = kpi.get("change")
        if change_val is not None and change_val != 0:
            arrow = "▲" if change_val > 0 else "▼"
            cls = "up" if change_val > 0 else "down"
            change_html = f'<span class="change {cls}">{arrow} {abs(change_val)}%</span>'
        kpi_cards += f"""
        <div class="kpi-card">
            <div class="kpi-icon" style="color:{color};">{kpi.get('图标', '📊')}</div>
            <div class="kpi-title">{kpi.get('标题', '')}</div>
            <div class="kpi-value" style="color:{color};">{kpi.get('值', '')}</div>
            {change_html}
        </div>
        """

    # Plotly 图表 HTML（内嵌 JSON）
    charts_html = ""
    for i, chart in enumerate(charts):
        fig = chart.get("figure")
        if fig is None:
            continue
        chart_json = json.dumps(fig.to_dict(), ensure_ascii=False)
        chart_id = f"chart_{i}"
        charts_html += f"""
        <div class="chart-container">
            <h3 class="chart-title">{chart.get('title', '图表')}</h3>
            <div id="{chart_id}" class="plotly-chart"></div>
        </div>
        <script>
            (function() {{
                var data = {chart_json};
                Plotly.newPlot('{chart_id}', data.data, data.layout, {{responsive: true}});
            }})();
        </script>
        """

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_rows = len(df)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #0D1B2A 0%, #1B2838 50%, #0D1B2A 100%);
            color: #E0E6ED;
            min-height: 100vh;
            padding: 20px;
        }}
        .dashboard-container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .dashboard-header {{
            text-align: center;
            padding: 30px 0;
            border-bottom: 2px solid rgba(232,131,58,0.3);
            margin-bottom: 30px;
        }}
        .dashboard-header h1 {{
            font-size: 32px;
            color: #E8833A;
            margin-bottom: 8px;
        }}
        .dashboard-header .meta {{
            font-size: 14px;
            color: #78909C;
        }}
        /* KPI 卡片网格 */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 40px;
        }}
        .kpi-card {{
            background: linear-gradient(135deg, rgba(26,15,10,0.9), rgba(45,31,24,0.9));
            border: 1px solid rgba(232,131,58,0.2);
            border-radius: 12px;
            padding: 24px 20px;
            text-align: center;
            transition: transform 0.2s;
        }}
        .kpi-card:hover {{ transform: translateY(-2px); }}
        .kpi-icon {{ font-size: 32px; margin-bottom: 8px; }}
        .kpi-title {{ font-size: 13px; color: #78909C; margin-bottom: 6px; }}
        .kpi-value {{ font-size: 28px; font-weight: bold; }}
        .change {{ font-size: 13px; margin-top: 6px; }}
        .change.up {{ color: #4CAF50; }}
        .change.down {{ color: #EF5350; }}
        /* 图表区域 */
        .charts-section {{
            margin-top: 20px;
        }}
        .chart-container {{
            background: rgba(26,15,10,0.6);
            border: 1px solid rgba(232,131,58,0.15);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
        }}
        .chart-title {{
            font-size: 16px;
            color: #F4A261;
            margin-bottom: 12px;
            padding-left: 10px;
            border-left: 3px solid #E8833A;
        }}
        .plotly-chart {{
            width: 100%;
            min-height: 400px;
        }}
        .dashboard-footer {{
            text-align: center;
            padding: 30px 0 10px;
            margin-top: 40px;
            border-top: 1px solid rgba(232,131,58,0.15);
            font-size: 12px;
            color: #546E7A;
        }}
    </style>
</head>
<body>
    <div class="dashboard-container">
        <div class="dashboard-header">
            <h1>{title}</h1>
            <div class="meta">数据总量：{total_rows:,} 条 | 生成时间：{timestamp}</div>
        </div>

        <!-- KPI 指标卡片 -->
        <div class="kpi-grid">
            {kpi_cards}
        </div>

        <!-- 图表区域 -->
        <div class="charts-section">
            {charts_html}
        </div>

        <div class="dashboard-footer">
            Powered by DataMind AI | 数据可视化看板
        </div>
    </div>
</body>
</html>"""
    return html
