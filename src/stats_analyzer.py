"""
统计分析模块 - 描述性统计、分组对比、相关性分析
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

def get_descriptive_stats(df: pd.DataFrame) -> pd.DataFrame:
    """获取描述性统计"""
    numeric_df = df.select_dtypes(include=[np.number])
    if len(numeric_df.columns) == 0:
        return pd.DataFrame()
    
    stats = numeric_df.describe().T
    # 重命名列（英文 → 中文）
    rename_map = {
        'count': '总数',
        'mean': '平均值',
        'std': '标准差',
        'min': '最小值',
        '25%': '25%分位',
        '50%': '中位数',
        '75%': '75%分位',
        'max': '最大值',
    }
    stats = stats.rename(columns=lambda c: rename_map.get(c, c))
    stats['缺失值'] = [numeric_df[col].isnull().sum() for col in numeric_df.columns]
    stats['缺失率'] = [f"{numeric_df[col].isnull().mean()*100:.1f}%" for col in numeric_df.columns]
    stats['唯一值数'] = [numeric_df[col].nunique() for col in numeric_df.columns]
    
    return stats

def get_group_stats(df: pd.DataFrame, group_col: str, agg_cols: Optional[list] = None) -> pd.DataFrame:
    """分组统计分析"""
    if group_col not in df.columns:
        return pd.DataFrame()
    
    if agg_cols is None:
        agg_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    # 过滤掉分组列
    agg_cols = [col for col in agg_cols if col != group_col]
    
    if len(agg_cols) == 0:
        return df[group_col].value_counts().reset_index(name='计数')
    
    grouped = df.groupby(group_col)[agg_cols].agg(['mean', 'sum', 'count', 'min', 'max'])
    grouped.columns = [f"{col[0]}_{col[1]}" for col in grouped.columns]
    grouped = grouped.reset_index()
    
    return grouped

def get_correlation_matrix(df: pd.DataFrame, method: str = 'pearson') -> pd.DataFrame:
    """获取相关性矩阵"""
    numeric_df = df.select_dtypes(include=[np.number])
    if len(numeric_df.columns) < 2:
        return pd.DataFrame()
    
    corr = numeric_df.corr(method=method)
    return corr

def get_column_distribution(df: pd.DataFrame, column: str) -> Dict[str, Any]:
    """获取列的分布信息"""
    if column not in df.columns:
        return {}
    
    series = df[column]
    
    if pd.api.types.is_numeric_dtype(series):
        return {
            "类型": "数值",
            "均值": series.mean(),
            "中位数": series.median(),
            "标准差": series.std(),
            "偏度": series.skew(),
            "峰度": series.kurtosis(),
        }
    else:
        return {
            "类型": "分类",
            "唯一值数": series.nunique(),
            "最常见值": series.mode().iloc[0] if len(series.mode()) > 0 else None,
            "最常见值占比": f"{series.value_counts(normalize=True).iloc[0]*100:.1f}%" if len(series) > 0 else "N/A",
            "值分布": series.value_counts().head(10).to_dict()
        }

def get_quick_insights(df: pd.DataFrame) -> list:
    """生成快速数据洞察"""
    insights = []
    
    # 数据规模
    insights.append(f"数据集包含 {len(df):,} 行 x {len(df.columns)} 列")
    
    # 缺失值
    total_missing = df.isnull().sum().sum()
    if total_missing > 0:
        missing_pct = total_missing / (df.shape[0] * df.shape[1]) * 100
        insights.append(f"发现 {total_missing:,} 个缺失值（占比 {missing_pct:.1f}%）")
    
    # 重复行
    dup_count = df.duplicated().sum()
    if dup_count > 0:
        insights.append(f"发现 {dup_count:,} 行重复数据")
    
    # 数值列洞察
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) > 0:
        insights.append(f"包含 {len(numeric_cols)} 个数值型字段，适合进行统计分析")
    
    # 分类列洞察
    cat_cols = df.select_dtypes(include=['object', 'category']).columns
    if len(cat_cols) > 0:
        insights.append(f"包含 {len(cat_cols)} 个文本/分类字段，适合进行分组分析")
    
    return insights
