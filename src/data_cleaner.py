"""
数据清洗模块 - 缺失值处理、类型修正、异常值检测
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple

def get_missing_value_report(df: pd.DataFrame) -> Dict[str, Any]:
    """生成缺失值报告"""
    missing = df.isnull().sum()
    missing = missing[missing > 0]
    
    report = {
        "缺失值列数": len(missing),
        "总缺失值数": int(missing.sum()),
        "缺失详情": {col: int(cnt) for col, cnt in missing.items()}
    }
    return report

def handle_missing_values(df: pd.DataFrame, column: str, method: str) -> pd.DataFrame:
    """
    处理缺失值
    method: 'drop', 'fill_mean', 'fill_median', 'fill_mode', 'fill_0', 'fill_unknown'
    """
    df_new = df.copy()
    
    # 均值/中位数填充只能用于数值列
    if method in ('fill_mean', 'fill_median'):
        if not pd.api.types.is_numeric_dtype(df_new[column]):
            raise ValueError(
                f"列「{column}」不是数值类型，无法使用{'均值' if method == 'fill_mean' else '中位数'}填充。"
                f"请改用「众数填充」或「填充未知」。"
            )
    
    if method == 'drop':
        df_new = df_new.dropna(subset=[column])
    elif method == 'drop_column':
        df_new = df_new.drop(columns=[column])
    elif method == 'fill_mean':
        df_new[column] = df_new[column].fillna(df_new[column].mean())
    elif method == 'fill_median':
        df_new[column] = df_new[column].fillna(df_new[column].median())
    elif method == 'fill_mode':
        df_new[column] = df_new[column].fillna(df_new[column].mode()[0] if len(df_new[column].mode()) > 0 else 'Unknown')
    elif method == 'fill_0':
        if pd.api.types.is_numeric_dtype(df_new[column]):
            df_new[column] = df_new[column].fillna(0)
        else:
            df_new[column] = df_new[column].fillna('0')
    elif method == 'fill_unknown':
        df_new[column] = df_new[column].fillna('Unknown')
    
    return df_new

def detect_data_type_issues(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """检测数据类型问题"""
    issues = []
    
    for col in df.columns:
        # 检测可能的日期列
        if df[col].dtype == 'object':
            try:
                parsed = pd.to_datetime(df[col], errors='coerce')
                if parsed.notna().sum() / len(df) > 0.7:
                    issues.append({
                        "列名": col,
                        "问题": "可能被误识别为文本，实际是日期类型",
                        "建议": "转换为日期时间类型"
                    })
            except:
                pass
        
        # 检测可能的数值列
        if df[col].dtype == 'object':
            try:
                pd.to_numeric(df[col], errors='coerce')
                non_na = pd.to_numeric(df[col], errors='coerce').dropna()
                if len(non_na) / len(df) > 0.7:
                    issues.append({
                        "列名": col,
                        "问题": "可能被误识别为文本，实际是数值类型",
                        "建议": "转换为数值类型"
                    })
            except:
                pass
    
    return issues

def convert_column_type(df: pd.DataFrame, column: str, target_type: str) -> pd.DataFrame:
    """转换列数据类型，拒绝会导致大量数据丢失的转换"""
    df_new = df.copy()
    
    if target_type == 'datetime':
        converted = pd.to_datetime(df_new[column], errors='coerce')
    elif target_type == 'numeric':
        converted = pd.to_numeric(df_new[column], errors='coerce')
    elif target_type == 'string':
        df_new[column] = df_new[column].astype('str')
        return df_new
    elif target_type == 'category':
        df_new[column] = df_new[column].astype('category')
        return df_new
    else:
        return df_new
    
    # 检查转换是否导致大量数据丢失（datetime/numeric 转换）
    original_non_null = df_new[column].notna().sum()
    converted_non_null = converted.notna().sum()
    loss_count = original_non_null - converted_non_null
    
    if loss_count > 0 and original_non_null > 0:
        loss_pct = loss_count / original_non_null * 100
        if loss_pct > 0:
            # 转换失败的值列表（最多显示 3 个示例）
            failed_mask = df_new[column].notna() & converted.isna()
            failed_values = df_new.loc[failed_mask, column].head(3).tolist()
            failed_str = '、'.join(str(v) for v in failed_values)
            raise ValueError(
                f"无法将列「{column}」转换为{target_type}类型："
                f"{loss_count}/{original_non_null}（{loss_pct:.0f}%）个值无法转换"
                f"{'（如：' + failed_str + '）' if failed_str else ''}。"
                f"请确认该列数据确实是{target_type}类型。"
            )
    
    df_new[column] = converted
    return df_new

def detect_outliers(df: pd.DataFrame, method: str = 'iqr') -> Dict[str, Any]:
    """检测异常值"""
    from src.utils.helpers import detect_outliers_zscore, detect_outliers_iqr
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    outlier_report = {}
    
    for col in numeric_cols:
        if method == 'zscore':
            mask = detect_outliers_zscore(df[col])
        else:  # iqr
            mask = detect_outliers_iqr(df[col])
        
        outlier_count = mask.sum()
        if outlier_count > 0:
            outlier_report[col] = {
                "异常值数量": int(outlier_count),
                "异常值占比": f"{outlier_count / len(df) * 100:.1f}%",
                "最小值": df.loc[mask, col].min() if outlier_count > 0 else None,
                "最大值": df.loc[mask, col].max() if outlier_count > 0 else None
            }
    
    return outlier_report

def handle_outliers(df: pd.DataFrame, column: str, method: str, action: str = 'remove') -> pd.DataFrame:
    """处理异常值"""
    from src.utils.helpers import detect_outliers_zscore, detect_outliers_iqr
    
    df_new = df.copy()
    
    if method == 'zscore':
        outlier_mask = detect_outliers_zscore(df_new[column])
    else:  # iqr
        outlier_mask = detect_outliers_iqr(df_new[column])
    
    if action == 'remove':
        df_new = df_new[~outlier_mask]
    elif action == 'cap':
        if method == 'iqr':
            Q1 = df_new[column].quantile(0.25)
            Q3 = df_new[column].quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR
        else:  # zscore
            mean_val = df_new[column].mean()
            std_val = df_new[column].std()
            lower = mean_val - 3 * std_val
            upper = mean_val + 3 * std_val
        df_new[column] = df_new[column].clip(lower=lower, upper=upper)
    
    return df_new

def drop_duplicate_rows(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """删除重复行，返回删除后的数据和删除的行数"""
    before = len(df)
    df_new = df.drop_duplicates()
    after = len(df_new)
    return df_new, before - after
