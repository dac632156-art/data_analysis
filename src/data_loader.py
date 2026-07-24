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

def _trim_bounds(raw: "pd.DataFrame"):
    """返回有效数据区的行列边界 (r0, r1, c0, c1)；全空返回 None"""
    if raw is None or raw.shape[0] == 0 or raw.shape[1] == 0:
        return None
    # 去除全空行/列，定位内容包围盒
    row_mask = raw.notna().any(axis=1)
    if not row_mask.any():
        return None
    col_mask = raw.notna().any(axis=0)
    if not col_mask.any():
        return None
    r0, r1 = row_mask.idxmax(), row_mask[::-1].idxmax()
    c0, c1 = col_mask.idxmax(), col_mask[::-1].idxmax()
    return int(r0), int(r1), int(c0), int(c1)


def _detect_header_row(raw: "pd.DataFrame", r0: int, r1: int, c0: int, c1: int) -> int:
    """在内容区前几行中挑选最佳表头行。

    规则：取「非空列数最多」且「其下有数据行」的那一行作为表头，
    从而天然跳过仅跨 1 列的标题行（如 '2023年销售报表'），
    而正确选中跨多列的真正表头行。
    """
    best_h, best_score = -1, -1  # -1 表示尚未找到候选表头
    for h in range(r0, min(r0 + 6, r1 + 1)):
        row = raw.iloc[h, c0:c1 + 1]
        nn = int(row.notna().sum())
        if nn == 0:
            continue
        below = raw.iloc[h + 1:r1 + 1, c0:c1 + 1] if h + 1 <= r1 else raw.iloc[0:0]
        below_nn = int(below.notna().sum().sum()) if below.shape[0] > 0 else 0
        if below_nn == 0:
            continue  # 该行之下的都是空行，不可能是表头
        if nn > best_score:
            best_score, best_h = nn, h
    # 没有任何行跨 ≥2 列且下方有数据 → 该 sheet 无真实表头，
    # 视为纯文字说明页/标题页，交由调用方当作非数据表跳过
    if best_score < 2:
        return -1
    return best_h


def _extract_table_from_raw(raw: "pd.DataFrame", sheet_name: str) -> "pd.DataFrame | None":
    """从单 sheet 的原始网格中识别并抽取数据表；非数据表返回 None。"""
    bounds = _trim_bounds(raw)
    if bounds is None:
        return None
    r0, r1, c0, c1 = bounds
    h = _detect_header_row(raw, r0, r1, c0, c1)
    if h == -1:
        return None  # 无真实表头，视为说明页/标题页，跳过

    header_vals = list(raw.iloc[h, c0:c1 + 1])
    data = raw.iloc[h + 1:r1 + 1, c0:c1 + 1].copy()
    # 表头空值/重复用占位名补齐，避免后续 df[col] 取 Series 失败
    cleaned = []
    seen = {}
    for i, v in enumerate(header_vals):
        if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "":
            name = f"列{i+1}"
        else:
            name = str(v).strip()
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        cleaned.append(name)
    data.columns = cleaned
    data = data.reset_index(drop=True)

    nrows, ncols = data.shape[0], data.shape[1]
    # 过滤非数据表：空表 / 极小 / 单格或短备注
    if ncols == 0 or nrows == 0:
        return None
    if ncols == 1 and nrows < 10:
        return None
    if ncols * nrows < 4:
        return None
    # 数据区至少应有 2 列含非空值，否则视为非结构化的说明/备注文字
    if data.notna().any(axis=0).sum() < 2:
        return None
    return data


def identify_excel_data_sheets(file_content: bytes, max_sheets: int = 50) -> list:
    """读取 Excel 全部 sheet，自动识别其中的数据表。

    返回 [{"sheet_name": str, "df": pd.DataFrame}, ...]，仅含被判定为
    真实数据表的 sheet（跳过空表、单格备注、标题页等非表格内容）。
    """
    xls = pd.read_excel(io.BytesIO(file_content), sheet_name=None, header=None)
    result = []
    for sheet_name, raw in xls.items():
        if len(result) >= max_sheets:
            break
        df = _extract_table_from_raw(raw, sheet_name)
        if df is None:
            continue
        result.append({"sheet_name": sheet_name, "df": df})
    return result

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
