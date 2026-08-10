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
    '产品类别', '产品名称', '产品', '类目',
    # ★ 2026-07-13 移除「品类」:它是「产品类别」的子串(产品**品类**类),
    #   保留「类目」:仅在「类目」「产品类目」等独立列名出现,不会与「产品类别」冲突。
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

# 业务实体语义词典：业务概念 → 列名同义词关键词
# 用途：让 Planner 能根据 business_question 中提到的业务实体（产品/利润/渠道…）
#       反查数据中真实存在的对应列，从而把分析问题对齐到正确的维度/指标列，
#       而不是无脑取「第一个分类列 + 第一个数值列」。
SEMANTIC_ENTITIES = {
    '产品':   ['产品', 'product', 'sku', '商品', '品目', '品类'],
    '利润':   ['利润', 'profit', '毛利', '净利', 'margin'],
    '收入':   ['销售额', '销售金额', '营收', '营业额', 'revenue', 'gmv'],
    '成本':   ['成本', 'cost'],
    '数量':   ['数量', 'quantity', '件数'],
    '金额':   ['金额', 'sales', 'amount'],
    '价格':   ['价格', '客单价', 'price', '单价'],
    '渠道':   ['渠道', 'channel', '线上', '线下', 'online', 'offline', '网店', '门店'],
    '地区':   ['地区', '区域', '省份', '省', '城市', '市', 'region', 'area', 'zone'],
    '客户':   ['客户', 'customer', '用户', '会员', 'client', 'user', 'member'],
    '退货':   ['退货', 'return', '退款', '退换', '退单'],
    '复购':   ['复购', '回购', 'repurchase', 'repeat'],
    '时间':   ['日期', '时间', '月份', '年份', 'date', 'time', 'month', 'year'],
}

# ID/编码列关键词 —— 这些列即使类型是数值也不应参与分析
ID_KEYWORDS = [
    '编码', '代码', '编号', 'id', 'code', 'key',
    'uuid', 'guid', 'serial', '序列号', '序号', '行号',
    '订单号', '工单号', '流水号', '交易号', '流水',
]


class ColumnClassifier:
    """全系统统一的列类型识别器"""

    def has_time_column(self, df: pd.DataFrame) -> bool:
        """判断 DataFrame 中是否存在时间列"""
        return self._find_time_column(df) is not None

    def has_category_column(self, df: pd.DataFrame) -> bool:
        """判断 DataFrame 中是否存在分类维度列"""
        return self._find_category_columns(df) != []

    def get_numeric_columns(self, df: pd.DataFrame) -> List[str]:
        """获取所有数值类型列名（排除 ID/编码列）"""
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated()]
        numeric_cols = []
        for col in df.columns:
            col_stripped = col.strip()
            # 排除 ID/编码列 —— 即使类型是数值也不参与分析
            if self._is_id_column(col_stripped):
                continue
            if pd.api.types.is_numeric_dtype(df[col]):
                numeric_cols.append(col_stripped)
        return numeric_cols

    def get_time_columns(self, df: pd.DataFrame) -> List[str]:
        """获取所有时间类型列名（按列名关键词 + datetime/period 数据类型双重识别）"""
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated()]
        time_cols = []
        for col in df.columns:
            col_lower = col.lower().strip()
            if any(kw in col_lower for kw in TIME_KEYWORDS):
                time_cols.append(col.strip())
                continue
            # 也接受 datetime / period 类型的列（如系统自动派生的日期列）
            if pd.api.types.is_datetime64_any_dtype(df[col]) or pd.api.types.is_period_dtype(df[col]):
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
            if pd.api.types.is_datetime64_any_dtype(df[col]) or pd.api.types.is_period_dtype(df[col]):
                time_cols.append(col_stripped)
                continue

            # 2) 排除 ID/编码列（即使类型是数值也不作为分析指标）
            if self._is_id_column(col_lower):
                other.append(col_stripped)
                continue

            # 3) 数值类型
            if pd.api.types.is_numeric_dtype(df[col]):
                numeric_cols.append(col_stripped)
                continue

            # 4) 分类维度
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

    # --- 业务实体语义匹配（支撑 Planner 语义感知列推断） ---

    def extract_question_entities(self, question: str) -> List[str]:
        """从 business_question 中提取其『显式提到』的业务实体（产品/利润/渠道…）。

        返回实体 key 列表（顺序按 SEMANTIC_ENTITIES 定义）。空列表表示问题
        未携带可识别的业务实体（此时列推断应回退到首个匹配列）。
        """
        if not question:
            return []
        q = str(question).lower()
        found = []
        for entity, kws in SEMANTIC_ENTITIES.items():
            if any(kw.lower() in q for kw in kws):
                found.append(entity)
        return found

    def resolve_entity_columns(self, df: pd.DataFrame, entity: str) -> List[str]:
        """返回 df 中与某业务实体语义匹配的实际列名列表（空 = 数据里没有该实体）。

        已排除 ID/编码列（如「客户ID」不会误当成「客户」指标列）。
        """
        kws = SEMANTIC_ENTITIES.get(entity, [])
        if not kws:
            return []
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated()]
        result = []
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if self._is_id_column(col_lower):
                continue
            if any(kw.lower() in col_lower for kw in kws):
                result.append(str(col).strip())
        return result

    # --- 私有方法 ---
    @staticmethod
    def _is_id_column(col_name: str) -> bool:
        """判断列名是否为 ID/编码列（即使数值类型也不应参与分析）"""
        col_lower = col_name.lower().strip()
        return any(kw in col_lower for kw in ID_KEYWORDS)

    def _find_time_column(self, df: pd.DataFrame) -> Optional[str]:
        time_cols = self.get_time_columns(df)
        return time_cols[0] if time_cols else None

    def _find_category_columns(self, df: pd.DataFrame) -> List[str]:
        return self.get_category_columns(df)
