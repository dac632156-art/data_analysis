"""
Planner —— 规则引擎：business_question → analysis_method + algorithm + dimension + metric

设计原则：评分制匹配，不用顺序匹配。一个 question 可命中多个分析方向，取最高分。
"""
import re
import pandas as pd
from src.column_classifier import ColumnClassifier


class TemplateNotFound(Exception):
    """占位 intent（V1 暂无模板实现）"""
    pass


class Planner:
    """评分制意图识别器"""

    # 关键词 → (analysis_method, 权重) 映射（唯一事实来源）
    # 权重设计：更具体的词权重更高
    KEYWORD_SCORES = [
        # growth_analysis
        (r"增长|增速",                "growth_analysis", 5),
        (r"放缓|下降|上升|趋势|走势|变化","growth_analysis", 3),

        # ranking_analysis
        (r"最高|最低|排行|排名|TOP|top|靠前|靠后", "ranking_analysis", 5),
        (r"第一|最大|最小",                      "ranking_analysis", 3),

        # proportion_analysis
        (r"占比|饼图|比例|份额|百分比",          "proportion_analysis", 5),

        # concentration_analysis
        (r"二八|帕累托|pareto|hhi|基尼|gini",  "concentration_analysis", 5),
        (r"集中度|集中|少数",                   "concentration_analysis", 3),

        # correlation_analysis
        (r"相关|关联|关系|影响|伴随|相关系",     "correlation_analysis", 4),

        # anomaly_analysis
        (r"异常|离群|突变|怪异|异常值|outlier", "anomaly_analysis", 5),
        (r"波动",                              "anomaly_analysis", 3),

        # distribution_analysis
        (r"直方图|频率|区间|分箱",              "distribution_analysis", 5),
        (r"分布|分散",                          "distribution_analysis", 3),

        # structure_analysis（兜底）
        (r"构成|结构|组成",                     "structure_analysis", 4),

        # V2 预留 Intent（V1 无模板，fallback 到 ranking_analysis）
        (r"对比|差异|比较|区别|vs",             "comparison_analysis", 4),
        (r"贡献|贡献度|贡献率|驱动|推动|拉动",   "decomposition_analysis", 4),
    ]

    # 默认算法
    DEFAULT_ALGORITHMS = {
        "growth_analysis": "yoy",
        "concentration_analysis": "pareto",
        "correlation_analysis": "pearson",
        "anomaly_analysis": "zscore",
    }

    # 有模板实现的 analysis（其余为占位 intent）
    IMPLEMENTED = {
        "growth_analysis", "ranking_analysis", "structure_analysis",
        "proportion_analysis", "concentration_analysis", "correlation_analysis",
        "anomaly_analysis", "distribution_analysis",
    }

    def __init__(self):
        self.classifier = ColumnClassifier()

    def plan(self, intent: dict, df: pd.DataFrame) -> dict:
        """
        输入：{"business_question": "销售增长是否放缓？", ...}
        输出：{"analysis_method": "growth_analysis", "algorithm": "yoy", "dimension": "日期", "metric": "销售额"}
        """
        question = intent["business_question"]

        # Step 1: 评分制匹配 → analysis_method
        analysis_method = self._match_with_score(question)

        # Step 2: 默认 algorithm
        algorithm = self.DEFAULT_ALGORITHMS.get(analysis_method)

        # Step 3: 根据 REQUIRED_SCHEMA 推断 dimension / metric
        dimension, metric = self._select_columns(df, analysis_method)

        return {
            "analysis_method": analysis_method,
            "algorithm": algorithm,
            "dimension": dimension,
            "metric": metric,
        }

    def _match_with_score(self, question: str) -> str:
        """评分制匹配：所有命中关键词的 analysis 计入分数，返回最高分"""
        scores = {}
        for pattern, method, weight in self.KEYWORD_SCORES:
            if re.search(pattern, question):
                scores[method] = scores.get(method, 0) + weight
        if scores:
            return max(scores, key=scores.get)
        return "ranking_analysis"  # 默认兜底

    def _select_columns(self, df: pd.DataFrame, analysis_method: str) -> tuple:
        """根据模板 REQUIRED_SCHEMA 推断列。
        如果模板不存在（占位 intent），返回默认列，让 Engine 的 can_run+fallback 处理。"""
        method = analysis_method

        # 先判断是否为占位 intent（V1 无模板）
        if method not in self.IMPLEMENTED:
            return self._default_columns(df)

        # 对于已实现的模板，按类型需求选列
        if method == "growth_analysis":
            dimension = self._pick_dimension(df, prefer="time")
            metric = self._pick_metric(df)
        elif method in ("ranking_analysis", "proportion_analysis", "concentration_analysis", "structure_analysis"):
            dimension = self._pick_dimension(df, prefer="category")
            metric = self._pick_metric(df)
        elif method == "distribution_analysis":
            dimension = None
            metric = self._pick_metric(df)
        elif method == "correlation_analysis":
            numeric_cols = self.classifier.get_numeric_columns(df)
            dimension = numeric_cols[0] if len(numeric_cols) >= 2 else None
            metric = numeric_cols[1] if len(numeric_cols) >= 2 else None
        elif method == "anomaly_analysis":
            dimension = self._pick_dimension(df, prefer="category")
            metric = self._pick_metric(df)
        else:
            return self._default_columns(df)

        return dimension, metric

    def _pick_dimension(self, df: pd.DataFrame, prefer: str = "time") -> str | None:
        """按偏好选维度列"""
        if prefer == "time":
            time_cols = self.classifier.get_time_columns(df)
            if time_cols:
                return time_cols[0]
        cat_cols = self.classifier.get_category_columns(df)
        if cat_cols:
            return cat_cols[0]
        return None

    def _pick_metric(self, df: pd.DataFrame) -> str | None:
        """选第一个数值列"""
        numeric_cols = self.classifier.get_numeric_columns(df)
        return numeric_cols[0] if numeric_cols else None

    def _default_columns(self, df: pd.DataFrame) -> tuple:
        """默认：第一个分类列 + 第一个数值列"""
        cat_cols = self.classifier.get_category_columns(df)
        num_cols = self.classifier.get_numeric_columns(df)
        dim = cat_cols[0] if cat_cols else None
        met = num_cols[0] if num_cols else None
        return dim, met
