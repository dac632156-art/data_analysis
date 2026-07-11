"""
Planner —— 纯调度器（V3 去业务化）

V3 设计原则：
- 所有业务知识已完全移至 AnalysisLibrary（YAML）
- TEMPLATE_MODULES 已移除 —— 使用 library.get_template_module_path()
- generate_default_intents 已迁移 —— 使用 library.suggest_intents_for_columns()
- _load_spec 已简化 —— 使用 library.get_schema_requirements()
- 只负责：Library 查询 → 列推断 → 数据校验 → 生成 Analysis Plan
"""

import pandas as pd
from typing import Optional, List, Dict, Any
from src.column_classifier import ColumnClassifier
from src.analysis_library import AnalysisLibrary


class Planner:
    """纯调度器：Library.lookup → 列推断 → 校验 → 返回 plan

    V3：不再维护任何业务知识。所有业务规则从 AnalysisLibrary 查询。
    """

    def __init__(self):
        self.classifier = ColumnClassifier()
        self.library = AnalysisLibrary()

    def plan(self, intent: dict, df: pd.DataFrame) -> dict:
        """输入：{"business_question": "...", "analysis_goal": "...", ...}
        输出：{"analysis_method": "growth_analysis", "algorithm": "yoy",
               "dimension": "...", "metric": "..."}

        流程：Library.lookup → can_run() 前置校验 → 列推断 → 校验
        """
        question = intent.get("business_question", "")
        analysis_goal = intent.get("analysis_goal", question)

        # Step 1: Library 查询
        matched = self.library.lookup(analysis_goal)

        # 低优先级匹配时尝试用 business_question
        if matched and matched.priority < 80 and question and question != analysis_goal:
            question_matched = self.library.lookup(question)
            if question_matched and question_matched.priority > matched.priority:
                matched = question_matched

        if matched is None and question and question != analysis_goal:
            matched = self.library.lookup(question)

        if matched is None:
            return self._unsupported_result(question,
                f"未找到匹配的分析类型。分析目标：「{analysis_goal}」")

        # Step 1.5: Fallback 链遍历
        intents_to_try = [matched]
        for fb_name in matched.fallback:
            fb = self.library.get_by_intent(fb_name)
            if fb:
                intents_to_try.append(fb)

        selected = None
        for candidate in intents_to_try:
            template_cls = self.library.load_template_class(candidate.intent)
            if template_cls:
                template = template_cls()
                if template.can_run(df):
                    selected = candidate
                    break

        if selected is None:
            return self._unsupported_result(question,
                f"当前数据不支持「{analysis_goal}」分析及其降级方案")

        # Step 2: 列推断（使用 Library 的 schema 要求 + ColumnClassifier）
        #   列推断现在语义感知：business_question 提到的实体会优先对齐到对应列，
        #   例如「哪些产品利润最高？」会选 产品类别 + 利润金额，而非首个分类/数值列。
        schema = selected.schema_requirements
        dim = self._infer_dimension(df, schema.dimension_type, question)
        met = self._infer_metric(df, question)

        # Step 3: 校验
        valid, reason = self._validate_columns(df, dim, met, selected.template)
        if not valid:
            return self._unsupported_result(question, reason)

        return {
            "analysis_method": selected.template,
            "algorithm": selected.default_algorithm,
            "dimension": dim,
            "metric": met,
        }

    # ===== 列推断（纯引擎逻辑，无业务知识，但支持语义感知） =====

    def _infer_dimension(self, df: pd.DataFrame, dim_type: str, question: str = "") -> Optional[str]:
        """根据 schema 要求的类型推断维度列。

        语义感知：若 business_question 提到了某分类实体（产品/地区/渠道…），
        优先选该实体在数据中匹配到的列，而不是无脑取第一个分类列。
        """
        if dim_type == "time":
            cols = self.classifier.get_time_columns(df)
            return cols[0] if cols else None
        elif dim_type == "category":
            if question:
                for entity in self.classifier.extract_question_entities(question):
                    for col in self.classifier.resolve_entity_columns(df, entity):
                        if not pd.api.types.is_numeric_dtype(df[col]):
                            return col
            cols = self.classifier.get_category_columns(df)
            return cols[0] if cols else None
        return None

    def _infer_metric(self, df: pd.DataFrame, question: str = "") -> Optional[str]:
        """推断指标列（语义感知：优先匹配问题中提到的数值实体列）。"""
        if question:
            for entity in self.classifier.extract_question_entities(question):
                for col in self.classifier.resolve_entity_columns(df, entity):
                    if pd.api.types.is_numeric_dtype(df[col]):
                        return col
        cols = self.classifier.get_numeric_columns(df)
        return cols[0] if cols else None

    # ===== 模板加载（委托 Library） =====

    def _load_template_class(self, template_name: str):
        """动态加载 Template 类（委托 Library）"""
        # 从 YAML 中查询 intent（通过 template 名反查）
        for intent_obj in self.library.get_all():
            if intent_obj.template == template_name:
                return self.library.load_template_class(intent_obj.intent)
        return None

    # ===== 列校验 =====

    def _validate_columns(self, df, dimension, metric, method) -> tuple:
        if dimension is not None and dimension not in df.columns:
            return False, f"数据中不存在维度列「{dimension}」"
        if metric is not None and metric not in df.columns:
            return False, f"数据中不存在指标列「{metric}」"
        return True, ""

    def _unsupported_result(self, question: str, reason: str) -> dict:
        return {
            "analysis_method": "unsupported",
            "algorithm": None,
            "dimension": None,
            "metric": None,
            "unsupported_reason": reason,
        }

    # ===== 默认意图生成（V3：委托 Library） =====

    def generate_default_intents(self, df: pd.DataFrame) -> list:
        """基于数据列特征自动生成默认 intents（AI 无法返回 JSON 时的纯规则兜底）

        V3：所有业务规则已移至 Library.suggest_intents_for_columns()。
        """
        time_cols = self.classifier.get_time_columns(df)
        cat_cols = self.classifier.get_category_columns(df)
        num_cols = self.classifier.get_numeric_columns(df)

        return self.library.suggest_intents_for_columns(time_cols, cat_cols, num_cols)