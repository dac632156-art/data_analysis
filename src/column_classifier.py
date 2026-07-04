"""
公共列分类模块 —— 全系统统一的列类型识别
提取自 report_analyzer.identify_fields()，供 Planner、Analysis Engine、Report 等模块共用。
"""
import pandas as pd
from typing import List, Optional

# 时间字段关键词
TIME_KEYWORDS = [
    '日期', '时间', '月份', '年月', '年份', '年', '月', '季度', '周次', '周',
    'date', 'time', 'month', 'year', 'yearmonth', 'quarter', 'week',
    'day', 'hour', 'minute',
]

# 分类维度关键词
DIMENSION_KEYWORDS = [
    '地区', '省份', '省', '城市', '市', '区', '县', '区域',
    '产品类别', '产品名称', '产品', '品类', '类目',
    '渠道', '来源', '终端', '网点', '门店',
    '客户类型', '客户', '用户', '会员等级',
    '部门', '团队', '负责人', '销售',
    '品牌', '型号', '规格',
    '性别', '年龄', '学历', '职业',
    'province', 'city', 'region', 'district', 'area',
    'category', 'product', 'channel', 'source',
    'customer', 'client', 'user', 'member',
    'department', 'team', 'brand', 'model',
    'gender', 'age', 'education',
]

# 数值指标关键词
METRIC_KEYWORDS = [
    '销售额', '销售', '金额', '收入', '营收', '利润', '成本',
    '数量', '人数', '客户数', '用户数', '订单数',
    '退货数', '退货率', '复购率', '转化率', '增长率', '客单价',
    '同比', '环比', '占比', '百分比', '比率',
    'amount', 'sales', 'revenue', 'profit', 'cost',
    'count', 'quantity', 'rate', 'ratio', 'price',
]

# 地理关键词
GEO_KEYWORDS = ['省', '市', '区', '县', '地区', '区域', '城市', '省份', 'province', 'city', 'region', 'district']


class ColumnClassifier:
    """全系统统一的列类型识别器"""

    def has_time_column(self, df: pd.DataFrame) -> bool:
        """判断 DataFrame 中是否存在时间列"""
        return self._find_time_column(df) is not None

    def has_category_column(self, df: pd.DataFrame) -> bool:
        """判断 DataFrame 中是否存在分类维度列"""
        return self._find_category_columns(df) != []

    def get_numeric_columns(self, df: pd.DataFrame) -> List[str]:
        """获取所有数值类型列名"""
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated()]
        numeric_cols = []
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                numeric_cols.append(col.strip())
        return numeric_cols

    def get_time_columns(self, df: pd.DataFrame) -> List[str]:
        """获取所有时间类型列名"""
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated()]
        time_cols = []
        for col in df.columns:
            col_lower = col.lower().strip()
            if any(kw in col_lower for kw in TIME_KEYWORDS):
                time_cols.append(col.strip())
        return time_cols

    def get_category_columns(self, df: pd.DataFrame) -> List[str]:
        """获取所有分类维度列名"""
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated()]
        cat_cols = []
        for col in df.columns:
            col_lower = col.lower().strip()
            if pd.api.types.is_numeric_dtype(df[col]):
                continue
            if any(kw in col_lower for kw in DIMENSION_KEYWORDS):
                cat_cols.append(col.strip())
            elif pd.api.types.is_string_dtype(df[col]) or df[col].dtype == 'object':
                nunique = df[col].nunique()
                if nunique < max(20, len(df) * 0.3):
                    cat_cols.append(col.strip())
        return cat_cols

    def classify_all(self, df: pd.DataFrame) -> dict:
        """完整分类：返回 {time_cols, category_cols, numeric_cols, other}"""
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated()]
        time_cols = []
        numeric_cols = []
        category_cols = []
        other = []

        for col in df.columns:
            col_lower = col.lower().strip()
            col_stripped = col.strip()

            # 1) 时间字段
            if any(kw in col_lower for kw in TIME_KEYWORDS):
                time_cols.append(col_stripped)
                continue

            # 2) 数值类型
            if pd.api.types.is_numeric_dtype(df[col]):
                numeric_cols.append(col_stripped)
                continue

            # 3) 分类维度
            if any(kw in col_lower for kw in DIMENSION_KEYWORDS):
                category_cols.append(col_stripped)
            elif pd.api.types.is_string_dtype(df[col]) or df[col].dtype == 'object':
                nunique = df[col].nunique()
                if nunique < max(20, len(df) * 0.3):
                    category_cols.append(col_stripped)
                else:
                    other.append(col_stripped)
            else:
                other.append(col_stripped)

        return {
            "time_cols": time_cols,
            "category_cols": category_cols,
            "numeric_cols": numeric_cols,
            "other": other,
        }

    # --- 语义实体匹配 ---
    def match_by_keywords(self, df: pd.DataFrame, keywords: List[str],
                          prefer_type: str = "category") -> List[str]:
        """用关键词列表匹配 df 中的列名，返回匹配到的列名列表。
        prefer_type 限定列类型：'category'/'numeric'/'time'"""
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated()]
        matched = []
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if not any(kw.lower() in col_lower for kw in keywords):
                continue
            # 类型过滤
            if prefer_type == "numeric" and not pd.api.types.is_numeric_dtype(df[col]):
                continue
            if prefer_type == "time":
                if not any(kw in col_lower for kw in TIME_KEYWORDS):
                    # 列名含关键词但非时间类型，仍接受
                    pass
            if prefer_type == "category":
                if pd.api.types.is_numeric_dtype(df[col]):
                    continue
            matched.append(col.strip())
        return matched

    # --- 私有方法 ---
    def _find_time_column(self, df: pd.DataFrame) -> Optional[str]:
        time_cols = self.get_time_columns(df)
        return time_cols[0] if time_cols else None

    def _find_category_columns(self, df: pd.DataFrame) -> List[str]:
        return self.get_category_columns(df)
