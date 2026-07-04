"""
仪表盘构建模块 - 关键指标卡片 + 图表平铺展示 + 可视化看板导出
"""
import pandas as pd
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


