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

        # Step 1.5: 先基于 matched 的 schema 尝试派生缺失列（用户决策：缺失列由系统计算）
        #   —— 这样即便模板 can_run 初判失败，也能靠派生列恢复，而不是直接判 unsupported。
        schema0 = matched.schema_requirements
        dim0 = self._infer_dimension(df, schema0.dimension_type, question)
        met0 = self._infer_metric(df, question)
        d_dim, d_met, derived_df, _notes = self._derive_missing_columns(
            df, schema0, question, dim0, met0)
        work_df = derived_df if derived_df is not None else df
        dim = d_dim if d_dim is not None else dim0
        met = d_met if d_met is not None else met0

        # Step 1.6: Fallback 链遍历（在 work_df 上判断 can_run）
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
                if template.can_run(work_df):
                    selected = candidate
                    break

        if selected is None:
            return self._unsupported_result(
                question,
                f"当前数据不支持「{analysis_goal}」分析及其降级方案",
                suggestion=self._suggestion_for(matched, question),
            )

        # Step 2: 列推断（在 work_df 上，使用 selected 的 schema 要求 + 语义感知）
        #   列推断现在语义感知：business_question 提到的实体会优先对齐到对应列，
        #   例如「哪些产品利润最高？」会选 产品类别 + 利润金额，而非首个分类/数值列。
        schema = selected.schema_requirements
        dim = self._infer_dimension(work_df, schema.dimension_type, question) or dim
        met = self._infer_metric(work_df, question) or met

        # Step 2.5: 词云专项重选（2026-07-13 确定性语义解构选列）
        #   普通 _infer_dimension 对 category 只取 get_category_columns[0]，
        #   容易把订单号/流水号（每行唯一）当作词云维度。词云单独走
        #   select_wordcloud_column：排除 ID/时间/唯一列 + 维度关键词/问题实体/基数甜区打分。
        if selected.template == "wordcloud_analysis":
            wc_col = self.classifier.select_wordcloud_column(work_df, question)
            if wc_col:
                dim = wc_col

        # Step 3: 校验；若仍缺失，再针对 selected 的 schema 派生一次
        valid, reason = self._validate_columns(work_df, dim, met, selected.template)
        if not valid:
            d2_dim, d2_met, derived_df2, _n2 = self._derive_missing_columns(
                work_df, schema, question, dim, met)
            if d2_dim is not None or d2_met is not None:
                dim = d2_dim if d2_dim is not None else dim
                met = d2_met if d2_met is not None else met
                work_df = derived_df2 if derived_df2 is not None else work_df
                valid, reason = self._validate_columns(work_df, dim, met, selected.template)
            # 派生后再跑一次词云选列（维度可能从「唯一列」放宽到「任意文本」）
            if not valid and selected.template == "wordcloud_analysis":
                wc_col2 = self.classifier.select_wordcloud_column(work_df, question)
                if wc_col2:
                    dim = wc_col2
                    valid, reason = self._validate_columns(work_df, dim, met, selected.template)

        if not valid:
            return self._unsupported_result(
                question, reason,
                suggestion=self._suggestion_for(selected, question, reason),
            )

        return {
            "analysis_method": selected.template,
            "algorithm": selected.default_algorithm,
            "dimension": dim,
            "metric": met,
            # 仅本地执行使用，不会序列化返回前端
            "derived_df": work_df if work_df is not df else None,
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

    def _unsupported_result(self, question: str, reason: str, suggestion: str = "") -> dict:
        return {
            "analysis_method": "unsupported",
            "algorithm": None,
            "dimension": None,
            "metric": None,
            "unsupported_reason": reason,
            "suggestion": suggestion,
        }

    # ===== 缺失列自动派生（用户决策：缺失列由系统计算，而非直接判失败） =====

    def _derive_missing_columns(self, df: pd.DataFrame, schema, question: str,
                                dim, met):
        """尝试从现有列派生缺失的维度/指标。

        返回 (dim, met, derived_df, changed)：
        - 仅当成功派生出可用列（新增列或放宽选用维度）时才返回 changed=True；
        - derived_df 为（新增了派生列的）副本；若没有任何派生，返回 None（不复制）。
          这样调用方可以安全用 `derived_df if derived_df is not None else df`。

        当前支持的规则（确定性、零成本，无需调用 LLM）：
        1) 需要数值指标但缺失、且存在维度列 → 自动生成「计数」指标（每行记为 1）；
        2) 需要日期维度但缺失、且存在 年/月(日) 列 → 合并生成日期列；
        3) 需要分类维度但缺失、且存在任意文本列 → 放宽选用该文本列（适用于词云等高基数文本）。
        """
        derived_df = None
        changed = False
        dim_type = getattr(schema, "dimension_type", "")
        metric_type = getattr(schema, "metric_type", "numeric")

        # 规则 1：派生计数指标
        if metric_type == "numeric" and met is None:
            fallback_dim = dim or self._infer_dimension(df, "category", question)
            if fallback_dim is not None:
                if derived_df is None:
                    derived_df = df.copy()
                derived_df["__derived_count__"] = 1
                met = "__derived_count__"
                changed = True

        # 规则 2：由 年/月/日 列合并出日期维度
        if dim_type == "time" and dim is None:
            yc = [c for c in df.columns if any(k in str(c).lower() for k in ("年", "year"))]
            mc = [c for c in df.columns if any(k in str(c).lower() for k in ("月", "month"))]
            dc = [c for c in df.columns if any(k in str(c).lower() for k in ("日", "day", "号"))]
            if yc and mc:
                try:
                    col = (
                        df[yc[0]].astype(str).str.strip() + "-"
                        + df[mc[0]].astype(str).str.strip()
                        + ("-" + df[dc[0]].astype(str).str.strip() if dc else "-01")
                    )
                    d = pd.to_datetime(col, errors="coerce")
                    if d.notna().any():
                        if derived_df is None:
                            derived_df = df.copy()
                        derived_df["__derived_date__"] = d
                        dim = "__derived_date__"
                        changed = True
                except Exception:
                    pass

        # 规则 3：分类维度缺失时，放宽选用任意文本列（词云/词频场景友好，不产生新列）
        if dim is None and dim_type in ("category", ""):
            for c in df.columns:
                if not pd.api.types.is_numeric_dtype(df[c]) and df[c].nunique() >= 2:
                    dim = c
                    changed = True
                    break

        return dim, met, derived_df, changed

    def _suggestion_for(self, intent_obj, question: str, reason: str = "") -> str:
        """按分析类型生成准确的失败建议（替换原来统一的『检查数值列和时间列』）。

        intent_obj: 匹配到的 AnalysisIntent（或 None）。
        """
        if intent_obj is None:
            return "未识别到可用的分析类型，请换一种表述（如『词云图』『销售趋势』『地区排名』）。"

        t = intent_obj.template
        name = intent_obj.display_name

        if t == "wordcloud_analysis":
            return ("词云图需要至少一个文本/分类列（如产品名称、类别、地区、渠道、客户等）。"
                    "当前数据缺少可用的分类列，无法统计词频；请确认数据中包含可归类的文本字段。")
        if t == "growth_analysis":
            return ("趋势/增长分析需要日期列 + 数值列。若数据只有『年/月』等分列，系统会尝试自动合并为日期列；"
                    "请确认存在时间字段（如日期、月份）与数值指标（如销售额、数量）。")
        if t in ("ranking_analysis", "concentration_analysis"):
            return ("排名/集中度分析需要分类列 + 数值列。若缺少数值列，系统会尝试自动生成『计数』指标；"
                    "请确认数据包含分类维度（如产品、地区）与可汇总的数值。")
        if t == "structure_analysis":
            return ("结构/占比分析需要分类列 + 数值列，用于计算各部分占比。"
                    "请确认数据包含分类维度与数值指标。")
        if t == "geo_analysis":
            return ("地理分布分析需要含省份/城市名的分类列 + 数值列。"
                    "请确认数据包含地理字段（如省份、城市）。")
        if t == "correlation_analysis":
            return ("相关分析需要至少 2 个数值列。请确认数据包含多个可对比的数值指标。")
        if t == "anomaly_analysis":
            return ("异常分析需要至少 1 个数值列。请确认数据包含数值指标（如销售额、数量）。")

        # 兜底：基于 reason 中的关键信息给通用但准确的提示
        if "时间" in (reason or ""):
            return "该分析需要日期/时间列，请确认数据包含时间字段（如日期、月份）。"
        if "数值" in (reason or ""):
            return "该分析需要数值指标列，请确认数据包含可汇总的数值字段（如销售额、数量）。"
        if "维度" in (reason or "") or "分类" in (reason or ""):
            return "该分析需要分类维度列（如产品、地区、类别），请确认数据包含文本/分类字段。"
        return f"当前数据暂不支持「{name}」，建议补充对应的分类或数值字段后重试。"

    # ===== 默认意图生成（V3：委托 Library） =====

    def generate_default_intents(self, df: pd.DataFrame) -> list:
        """基于数据列特征自动生成默认 intents（AI 无法返回 JSON 时的纯规则兜底）

        V3：所有业务规则已移至 Library.suggest_intents_for_columns()。
        """
        time_cols = self.classifier.get_time_columns(df)
        cat_cols = self.classifier.get_category_columns(df)
        num_cols = self.classifier.get_numeric_columns(df)

        return self.library.suggest_intents_for_columns(time_cols, cat_cols, num_cols)