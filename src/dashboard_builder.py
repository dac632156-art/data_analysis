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
            "color": "#38BDF8",
        "change": 0,
        "trend": "flat",
    })
    
    kpis.append({
            "title": "字段数",
            "value": f"{len(df.columns)}",
            "icon": "📋",
            "color": "#7DD3FC",
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
                "color": "#0ea5e9",
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
                "color": "#7DD3FC",
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
            "color": "#67E8F9",
            "change": 0,
            "trend": "flat",
        })
    
    return kpis[:6]  # 最多返回 6 个 KPI




def get_default_echart_configs(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """获取默认 ECharts 仪表盘图表配置（仅在无分析结果时作为兜底）

    精简策略：只生成最核心的 4-5 种图表类型，而非堆砌 12 种。
    这样不同数据集的图表会因列结构不同而有所差异，避免"千篇一律"。
    """
    configs = []
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    # 识别时间列
    time_cols = [c for c in df.columns if any(
        kw in str(c).lower() for kw in ['日期', '时间', '月份', '年份', 'date', 'month', 'year']
    )]

    # 1. 趋势图：有时间列优先用折线图
    if time_cols and numeric_cols:
        configs.append({"chart_type": "line", "x": time_cols[0], "y": numeric_cols[0],
                        "title": f"{numeric_cols[0]} 趋势变化"})

    # 2. 分类柱状图：无时间列但有分类列时用柱状图
    if (not time_cols) and cat_cols and numeric_cols:
        configs.append({"chart_type": "bar", "x": cat_cols[0], "y": numeric_cols[0],
                        "title": f"{cat_cols[0]} × {numeric_cols[0]}"})

    # 3. 饼图：类别不太多时有意义（≤10个分类）
    if cat_cols and numeric_cols and len(df[cat_cols[0]].unique()) <= 10:
        configs.append({"chart_type": "pie", "x": cat_cols[0],
                        "title": f"{cat_cols[0]} 占比分布"})

    # 4. 纯数值序列：仅数值列时用折线展示
    if not cat_cols and numeric_cols:
        configs.append({"chart_type": "line", "x": numeric_cols[0],
                        "title": f"{numeric_cols[0]} 序列变化"})

    # 5. 散点图：两个数值列时展示相关性
    if len(numeric_cols) >= 2:
        configs.append({"chart_type": "scatter", "x": numeric_cols[0],
                        "y": numeric_cols[1], "title": f"{numeric_cols[0]} vs {numeric_cols[1]}"})

    # 6. 第二指标柱状图：有多指标数据时展示更多维度
    if cat_cols and numeric_cols and len(numeric_cols) >= 2:
        configs.append({"chart_type": "bar", "x": cat_cols[0], "y": numeric_cols[1],
                        "title": f"{cat_cols[0]} × {numeric_cols[1]}"})

    # 最多 5 个图表兜底
    return configs[:5]


