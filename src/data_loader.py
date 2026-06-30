"""
数据加载模块 - 支持 CSV/Excel/JSON/SQLite 文件读取
"""
import pandas as pd
import sqlite3
import json
import io
import tempfile
import os
from typing import Optional, Dict, Any

def load_csv(file_content: bytes, filename: str) -> pd.DataFrame:
    """加载 CSV 文件，自动检测编码"""
    # 检查是否是 xlsx 文件伪装成 csv
    if file_content[:4] == b'PK\x03\x04':
        raise ValueError("文件内容是 Excel 格式（.xlsx），但扩展名是 .csv。请将文件另存为 CSV 格式，或修改扩展名为 .xlsx")

    # 尝试多种编码
    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'latin-1']
    last_error = None
    for encoding in encodings:
        try:
            df = pd.read_csv(io.BytesIO(file_content), encoding=encoding)
            return df
        except UnicodeDecodeError:
            continue
        except Exception as e:
            last_error = e
            continue
    # 如果所有编码都失败，用默认方式
    try:
        return pd.read_csv(io.BytesIO(file_content))
    except Exception as e:
        if last_error:
            raise ValueError(f"无法读取 CSV 文件: {last_error}")
        raise ValueError(f"无法读取 CSV 文件: {e}")

def load_excel(file_content: bytes) -> pd.DataFrame:
    """加载 Excel 文件"""
    return pd.read_excel(io.BytesIO(file_content))

def load_json(file_content: bytes) -> pd.DataFrame:
    """加载 JSON 文件，支持多种格式"""
    try:
        data = json.loads(file_content.decode('utf-8'))
    except json.JSONDecodeError:
        # JSON 解析失败，尝试 JSON Lines 格式
        try:
            return pd.read_json(io.BytesIO(file_content), lines=True)
        except Exception as e:
            raise ValueError(f"无法解析 JSON 文件：{str(e)}")
    
    # 格式1: JSON 数组 [{...}, {...}]
    if isinstance(data, list) and len(data) > 0:
        return pd.DataFrame(data)
    
    # 格式2: 嵌套对象，找第一个列表值 {"data": [...], "columns": [...]}
    if isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, list) and len(val) > 0:
                if isinstance(val[0], dict):
                    return pd.DataFrame(val)
                return pd.DataFrame({key: val})
        
        # 格式3: dict of lists {"col1": [1,2], "col2": [3,4]}
        if all(isinstance(v, list) for v in data.values()):
            return pd.DataFrame(data)
        
        # 格式4: 扁平的 key-value 对
        return pd.DataFrame([data])
    
    raise ValueError("JSON 格式不支持，请检查文件内容。支持：[{...}]数组、{key: [...]}嵌套、JSON Lines")

def load_sqlite(file_content: bytes) -> Dict[str, pd.DataFrame]:
    """加载 SQLite 文件，返回所有表的数据"""
    # 使用系统临时目录（兼容 Windows/Linux/Mac）
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as tmp:
        tmp.write(file_content)
        temp_path = tmp.name

    try:
        conn = sqlite3.connect(temp_path)
        cursor = conn.cursor()

        # 获取所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        result = {}
        for (table_name,) in tables:
            result[table_name] = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)

        conn.close()
    finally:
        # 清理临时文件
        try:
            os.unlink(temp_path)
        except OSError:
            pass

    return result

def get_data_info(df: pd.DataFrame) -> Dict[str, Any]:
    """获取数据基本信息"""
    return {
        "行数": len(df),
        "列数": len(df.columns),
        "内存占用": f"{df.memory_usage(deep=True).sum() / 1024**2:.2f} MB",
        "缺失值总数": df.isnull().sum().sum(),
        "重复行数": df.duplicated().sum(),
    }

def get_column_info(df: pd.DataFrame) -> pd.DataFrame:
    """获取每列的详细信息"""
    # 处理重复列名：df[重复列名] 会返回 DataFrame，.mean()/.sum() 返回 Series 导致格式化报错
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated()]
    info = pd.DataFrame({
        "列名": df.columns,
        "数据类型": [str(dtype) for dtype in df.dtypes],
        "缺失值": [df[col].isnull().sum() for col in df.columns],
        "缺失率": [f"{df[col].isnull().mean()*100:.1f}%" for col in df.columns],
        "唯一值数": [df[col].nunique() for col in df.columns],
        "示例值": [str(df[col].dropna().iloc[0]) if len(df[col].dropna()) > 0 else "N/A" for col in df.columns]
    })
    return info
