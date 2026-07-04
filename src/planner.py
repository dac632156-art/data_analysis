"""
Planner —— 薄调度器：Library 查询 → 列推断 → Template 调度

V2 设计原则：
- 绝不包含业务知识——所有业务知识已移至 analysis_library/*.yaml
- 绝不硬编码模板列表——所有模板通过 Library + 动态导入管理
- 只负责：列推断、算法推断、Schema 检查、Fallback 降级
"""

import pandas as pd
from typing import Optional
from src.column_classifier import ColumnClassifier
from src.analysis_library import AnalysisLibrary


class Planner:
    """薄调度器：Library.lookup → 列推断 → 返回 plan"""

    # ---- 模板动态加载映射 ----
    # 模板文件的模块路径（用于动态导入）
    # 新增模板只需在此表加一行 + 写一个 YAML，不用改 Planner 逻辑
    TEMPLATE_MODULES = {
        "growth_analysis":        "src.analysis_templates.growth_analysis.GrowthAnalysis",
        "ranking_analysis":       "src.analysis_templates.ranking_analysis.RankingAnalysis",
        "structure_analysis":     "src.analysis_templates.structure_analysis.StructureAnalysis",
        "concentration_analysis": "src.analysis_templates.concentration_analysis.ConcentrationAnalysis",
        "distribution_analysis":  "src.analysis_templates.distribution_analysis.DistributionAnalysis",
        "correlation_analysis":   "src.analysis_templates.correlation_analysis.CorrelationAnalysis",
        "anomaly_analysis":       "src.analysis_templates.anomaly_analysis.AnomalyAnalysis",
        "proportion_analysis":    "src.analysis_templates.proportion_analysis.ProportionAnalysis",
        "retention_analysis":     "src.analysis_templates.retention_analysis.RetentionAnalysis",
        "comparison_analysis":    "src.analysis_templates.comparison_analysis.ComparisonAnalysis",
        "geo_analysis":           "src.analysis_templates.geo_analysis.GeoAnalysis",
    }

    def __init__(self):
        self.classifier = ColumnClassifier()
        self.library = AnalysisLibrary()

    def plan(self, intent: dict, df: pd.DataFrame) -> dict:
        """
        输入：{"business_question": "...", "analysis_goal": "分析增长趋势", ...}
        输出：{"analysis_method": "growth_analysis", "algorithm": "yoy",
               "dimension": "日期", "metric": "销售额"}

        流程：Library.lookup(analysis_goal) → can_run()前置校验 → 加载 Template → 列推断 → 校验
        """
        question = intent.get("business_question", "")
        analysis_goal = intent.get("analysis_goal", question)

        # Step 1: Library 查询 —— 中文目标 → AnalysisIntent
        # 优先使用 analysis_goal，但若匹配不到高优先级意图，回退到 business_question
        matched = self.library.lookup(analysis_goal)
        
        # 如果 analysis_goal 匹配到的优先级较低（<80），尝试用 business_question 重新匹配
        if matched is not None and matched.priority < 80 and question and question != analysis_goal:
            question_matched = self.library.lookup(question)
            if question_matched is not None and question_matched.priority > matched.priority:
                matched = question_matched
        
        if matched is None:
            # 尝试用原始问题匹配
            if question and question != analysis_goal:
                matched = self.library.lookup(question)
            if matched is None:
                return self._unsupported_result(question,
                    f"未找到匹配的分析类型。分析目标：「{analysis_goal}」")

        # Step 1.5: 遍历 fallback 链，找到第一个 can_run() 通过的模板
        # 从当前匹配的 intent 开始，依次尝试每个 fallback
        intents_to_try = [matched]
        if matched.fallback:
            for fallback_intent_name in matched.fallback:
                fallback_matched = self.library.lookup(fallback_intent_name)
                if fallback_matched:
                    intents_to_try.append(fallback_matched)

        selected_matched = None
        for candidate in intents_to_try:
            template_cls = self._load_template_class(candidate.template)
            if template_cls:
                template = template_cls()
                if template.can_run(df):
                    selected_matched = candidate
                    break

        if selected_matched is None:
            return self._unsupported_result(question,
                f"当前数据不支持「{analysis_goal}」分析及其降级方案")

        analysis_method = selected_matched.template
        algorithm = selected_matched.default_algorithm

        # Step 2: 加载模板获取 REQUIRED_SCHEMA
        template_spec = self._load_spec(analysis_method)
        if template_spec is None:
            return self._unsupported_result(question,
                f"分析模板「{analysis_method}」尚未实现")

        # Step 3: 按 REQUIRED_SCHEMA 推断列（增强版：识别业务语义列）
        dimension, metric = self._infer_columns(df, template_spec, selected_matched.intent, analysis_goal)

        # Step 4: Schema Validator —— 验证选出的列确实存在
        valid, reason = self._validate_columns(df, dimension, metric, analysis_method)
        if not valid:
            return {
                "analysis_method": "unsupported",
                "algorithm": algorithm,
                "dimension": dimension,
                "metric": metric,
                "unsupported_reason": reason,
                "fallback_intents": selected_matched.fallback,
            }

        return {
            "analysis_method": analysis_method,
            "algorithm": algorithm,
            "dimension": dimension,
            "metric": metric,
        }

    # ===== 列推断 =====

    def _infer_columns(self, df: pd.DataFrame, spec, intent_name: str, analysis_goal: str = "") -> tuple:
        """根据 TemplateRuntime.REQUIRED_SCHEMA 自动推断 dim/metric 列
        
        增强版：不仅匹配类型，还识别业务语义列（客户ID、订单日期等）
        """
        required = spec if isinstance(spec, dict) else {}
        dim_type = required.get("dimension_type", "")
        min_metric = required.get("min_metric", 1)

        dimension = None
        metric = None

        # 业务语义关键词映射
        customer_keywords = ["客户", "customer", "user", "buyer", "member", "cid", "uid"]
        order_keywords = ["订单", "order", "交易", "sale", "bill"]
        date_keywords = ["日期", "时间", "date", "time", "dt"]
        amount_keywords = ["金额", "销售额", "收入", "price", "amount", "revenue"]
        geo_keywords = ["省份", "省", "城市", "市", "地区", "区域", "地理", "geo", "city", "province"]

        # 推断维度列
        if dim_type == "time":
            time_cols = self.classifier.get_time_columns(df)
            # 优先选择包含日期关键词的列
            for col in time_cols:
                if any(kw in str(col).lower() for kw in date_keywords):
                    dimension = col
                    break
            if dimension is None and time_cols:
                dimension = time_cols[0]
        elif dim_type == "category":
            cat_cols = self.classifier.get_category_columns(df)
            # 对于地理分析，优先选择省份列，然后是城市列，最后是地区列
            if intent_name and ("geo" in intent_name or "地理" in intent_name or "地图" in intent_name):
                province_keywords = ["省份", "省", "province"]
                city_keywords = ["城市", "市", "city"]
                region_keywords = ["地区", "区域", "地理", "geo", "region"]
                
                for col in cat_cols:
                    if any(kw in str(col).lower() for kw in province_keywords):
                        dimension = col
                        break
                if dimension is None:
                    for col in cat_cols:
                        if any(kw in str(col).lower() for kw in city_keywords):
                            dimension = col
                            break
                if dimension is None:
                    for col in cat_cols:
                        if any(kw in str(col).lower() for kw in region_keywords):
                            dimension = col
                            break
            # 对于复购分析，优先选择客户ID列
            elif intent_name and "复购" in intent_name:
                for col in cat_cols:
                    if any(kw in str(col).lower() for kw in customer_keywords):
                        dimension = col
                        break
            if dimension is None and cat_cols:
                dimension = cat_cols[0]

        # 推断指标列
        numeric_cols = self.classifier.get_numeric_columns(df)
        if len(numeric_cols) >= min_metric:
            # 根据分析目标智能选择指标
            goal_to_check = analysis_goal or intent_name
            if goal_to_check:
                goal_lower = goal_to_check.lower()
                # 复购相关
                repurchase_keywords = ["复购", "回购", "重复购买", "retention", "repeat"]
                # 利润相关
                profit_keywords = ["利润", "盈利", "profit"]
                # 退货相关
                return_keywords = ["退货", "退款", "return"]
                # 客户相关
                customer_keywords_metric = ["客户数", "用户数", "人数", "count", "num"]
                
                if any(kw in goal_lower for kw in repurchase_keywords):
                    for col in numeric_cols:
                        if any(kw in str(col).lower() for kw in repurchase_keywords):
                            metric = col
                            break
                elif any(kw in goal_lower for kw in profit_keywords):
                    for col in numeric_cols:
                        if any(kw in str(col).lower() for kw in profit_keywords):
                            metric = col
                            break
                elif any(kw in goal_lower for kw in return_keywords):
                    for col in numeric_cols:
                        if any(kw in str(col).lower() for kw in return_keywords):
                            metric = col
                            break
                elif any(kw in goal_lower for kw in customer_keywords_metric):
                    for col in numeric_cols:
                        if any(kw in str(col).lower() for kw in customer_keywords_metric):
                            metric = col
                            break
            
            # 如果没有根据目标匹配到，使用默认逻辑
            if metric is None:
                for col in numeric_cols:
                    if any(kw in str(col).lower() for kw in amount_keywords):
                        metric = col
                        break
                if metric is None:
                    metric = numeric_cols[0]

        return dimension, metric

    def _load_template_class(self, analysis_method: str):
        """动态加载模板类（用于 can_run() 前置校验）
        
        返回模板类对象，便于实例化并调用 can_run(df)
        """
        module_path = self.TEMPLATE_MODULES.get(analysis_method)
        if module_path is None:
            return None

        try:
            import importlib
            parts = module_path.rsplit(".", 1)
            module = importlib.import_module(parts[0])
            cls = getattr(module, parts[1])
            return cls
        except Exception:
            return None

    def _load_spec(self, analysis_method: str) -> Optional[dict]:
        """动态加载模板的 REQUIRED_SCHEMA

        返回 TemplateRuntime 的 REQUIRED_SCHEMA 字段（dict 形式），
        供 _infer_columns 使用。
        对于占位 intent（模板还未实现），返回 None。
        """
        module_path = self.TEMPLATE_MODULES.get(analysis_method)
        if module_path is None:
            return None

        try:
            import importlib
            parts = module_path.rsplit(".", 1)
            module = importlib.import_module(parts[0])
            cls = getattr(module, parts[1])
            # V2：使用 runtime（TemplateRuntime）替代 spec（TemplateSpec）
            if hasattr(cls, 'runtime'):
                return cls.runtime.REQUIRED_SCHEMA
        except Exception:
            return None

        return None

    # ===== 列校验 =====

    def _validate_columns(self, df, dimension, metric, method) -> tuple:
        """验证 dim/metric 在 df 中真实存在。返回 (valid: bool, reason: str)"""
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

    # ===== 默认意图生成（纯规则兜底，AI 不可用时） =====

    def generate_default_intents(self, df: pd.DataFrame) -> list:
        """基于数据列特征自动生成默认 intents（AI 无法返回 JSON 时的纯规则兜底）

        根据 ColumnClassifier 识别的 time/category/numeric 列组合，
        生成 2-6 个覆盖基础分析方向的 intent。
        每个 intent 的字段格式与 INSIGHTS_SYSTEM_PROMPT 要求一致。
        """
        time_cols = self.classifier.get_time_columns(df)
        cat_cols = self.classifier.get_category_columns(df)
        num_cols = self.classifier.get_numeric_columns(df)
        intents = []

        # 1. 增长趋势（有时间列 + 数值列）
        if time_cols and num_cols:
            intents.append({
                "business_question": f"{num_cols[0]}的增长趋势如何？",
                "analysis_goal": f"分析{num_cols[0]}的增长趋势",
                "priority": "high",
                "reason": "有时间和数值列，趋势是核心关注点"
            })

        # 2. 排名对比（有分类列 + 数值列）
        if cat_cols and num_cols:
            intents.append({
                "business_question": f"哪个{cat_cols[0]}的{num_cols[0]}最高？",
                "analysis_goal": f"{cat_cols[0]}的{num_cols[0]}排名对比",
                "priority": "high",
                "reason": "了解各分类维度的表现差异"
            })

        # 3. 结构占比（有分类列 + 数值列）
        if cat_cols and num_cols:
            intents.append({
                "business_question": f"各{cat_cols[0]}的{num_cols[0]}占比如何？",
                "analysis_goal": f"各{cat_cols[0]}的{num_cols[0]}占比分析",
                "priority": "medium",
                "reason": "占比是基础分析维度"
            })

        # 4. 相关关系（≥2 个数值列）
        if len(num_cols) >= 2:
            intents.append({
                "business_question": f"{num_cols[0]}和{num_cols[1]}是否相关？",
                "analysis_goal": f"{num_cols[0]}和{num_cols[1]}的相关关系",
                "priority": "medium",
                "reason": "多指标之间可能存在关联"
            })

        # 5. 异常检测（有数值列）
        if num_cols:
            intents.append({
                "business_question": f"{num_cols[0]}是否存在异常值？",
                "analysis_goal": f"{num_cols[0]}的异常值检测",
                "priority": "low",
                "reason": "识别数据中的离群点"
            })

        # 6. 集中度（有分类列 + 数值列）
        if cat_cols and num_cols:
            intents.append({
                "business_question": f"{num_cols[0]}在{cat_cols[0]}上是否集中？",
                "analysis_goal": f"{num_cols[0]}的集中度分析",
                "priority": "low",
                "reason": "判断是否存在帕累托效应"
            })

        # 7. 地理空间分析（有省份/地区列 + 数值列）
        geo_keywords = ["省份", "省", "城市", "市", "地区", "区域", "地理", "geo", "city", "province"]
        geo_cols = [c for c in cat_cols if any(kw in str(c).lower() for kw in geo_keywords)]
        if geo_cols and num_cols:
            intents.append({
                "business_question": f"哪些{geo_cols[0]}的{num_cols[0]}最高？",
                "analysis_goal": f"{geo_cols[0]}{num_cols[0]}的地理空间分布分析",
                "priority": "high",
                "reason": "了解数据在地理空间上的分布特征，识别高价值区域"
            })

        return intents[:7]
