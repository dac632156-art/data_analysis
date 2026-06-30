"""
通用辅助函数
"""
import pandas as pd
import numpy as np

def format_number(num: float) -> str:
    """格式化数字显示"""
    if abs(num) >= 1e6:
        return f"{num/1e6:.2f}M"
    elif abs(num) >= 1e3:
        return f"{num/1e3:.2f}K"
    elif abs(num) >= 1:
        return f"{num:.2f}"
    else:
        return f"{num:.4f}"

def detect_outliers_zscore(series: pd.Series, threshold: float = 3.0) -> pd.Series:
    """使用 Z-Score 方法检测异常值"""
    if not pd.api.types.is_numeric_dtype(series):
        return pd.Series([False] * len(series), index=series.index)
    
    mean = series.mean()
    std = series.std()
    if std == 0:
        return pd.Series([False] * len(series), index=series.index)
    z_scores = np.abs((series - mean) / std)
    return z_scores > threshold

def detect_outliers_iqr(series: pd.Series) -> pd.Series:
    """使用 IQR 方法检测异常值"""
    if not pd.api.types.is_numeric_dtype(series):
        return pd.Series([False] * len(series), index=series.index)
    
    Q1 = series.quantile(0.25)
    Q3 = series.quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    return (series < lower_bound) | (series > upper_bound)

def get_numeric_columns(df: pd.DataFrame) -> list:
    """获取数值类型列名列表"""
    return df.select_dtypes(include=[np.number]).columns.tolist()

def get_categorical_columns(df: pd.DataFrame) -> list:
    """获取分类类型列名列表"""
    return df.select_dtypes(include=['object', 'category']).columns.tolist()

def get_datetime_columns(df: pd.DataFrame) -> list:
    """获取日期时间类型列名列表"""
    return df.select_dtypes(include=['datetime64']).columns.tolist()

def infer_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
    """尝试将字符串列转换为日期时间类型"""
    df_new = df.copy()
    for col in df.columns:
        if df[col].dtype == 'object':
            try:
                pd.to_datetime(df[col], errors='coerce')
                non_na = pd.to_datetime(df[col], errors='coerce').dropna()
                if len(non_na) / len(df[col]) > 0.7:  # 如果超过70%能转换
                    df_new[col] = pd.to_datetime(df[col], errors='coerce')
            except:
                pass
    return df_new
