"""
Analysis Library Registry —— YAML 驱动的分析知识中心（V3）

核心职责升级：
1. 加载 analysis_library/ 目录下所有 .yaml 文件
2. lookup(analysis_goal) —— 中文目标 → AnalysisIntent
3. get_by_intent(intent) —— 精确查询
4. V3新增：suggest_intents_for_columns() —— 列组合 → 推荐意图（从 Planner 迁移）
5. V3新增：get_template_module_path() —— intent → Template 导入路径
6. V3新增：get_calculator_for() —— intent → Calculator
7. V3新增：get_derived_metrics() —— intent → 派生指标列表
8. V3新增：get_full_profile() —— 返回分析类型的完整知识

设计原则：
- 所有"关于分析的知识"都在此注册，Planner / Template / Report 不应该自行维护
- 新增分析类型 = 新增一个 YAML，零代码修改
"""

import os
import yaml
import importlib
from typing import List, Optional, Dict, Any, Tuple
from src.analysis_library.analysis_intent import AnalysisIntent, SchemaRequirement


class AnalysisLibrary:
    """YAML 驱动的分析知识中心——全系统的唯一分析知识来源"""

    # ===== 按约定自动推导 Template 类名 =====

    @staticmethod
    def _derive_class_name(template_name: str) -> str:
        """从 template 名推导类名：growth_analysis → GrowthAnalysis"""
        base = template_name.replace("_analysis", "")
        return "".join(w.capitalize() for w in base.split("_")) + "Analysis"

    @staticmethod
    def _derive_module_path(template_name: str) -> str:
        """从 template 名推导模块路径：growth_analysis → src.analysis_templates.growth_analysis.GrowthAnalysis"""
        cls = AnalysisLibrary._derive_class_name(template_name)
        return f"src.analysis_templates.{template_name}.{cls}"

    # ===== 初始化 =====

    def __init__(self, yaml_dir: str = None):
        if yaml_dir is None:
            yaml_dir = os.path.dirname(os.path.abspath(__file__))
        self.yaml_dir = yaml_dir
        self.intents: List[AnalysisIntent] = []
        self._intent_map: Dict[str, AnalysisIntent] = {}
        self._keyword_index: Dict[str, List[str]] = {}  # keyword → [intent, ...]
        self._load_all()

    def _load_all(self):
        """加载所有 YAML 并构建索引"""
        if not os.path.isdir(self.yaml_dir):
            return

        yaml_files = sorted([
            f for f in os.listdir(self.yaml_dir)
            if f.endswith(".yaml") or f.endswith(".yml")
        ])

        self.intents.clear()
        self._intent_map.clear()
        self._keyword_index.clear()

        for filename in yaml_files:
            filepath = os.path.join(self.yaml_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if data and isinstance(data, dict) and "intent" in data:
                    intent = AnalysisIntent.from_dict(data)
                    self.intents.append(intent)
                    self._intent_map[intent.intent] = intent
                    # 构建关键词索引
                    for kw in intent.keywords:
                        kw_lower = kw.lower()
                        if kw_lower not in self._keyword_index:
                            self._keyword_index[kw_lower] = []
                        self._keyword_index[kw_lower].append(intent.intent)
            except Exception as e:
                import logging as _logging; _logging.getLogger("library").warning(f"skip {filename}: {e}")

        # 按 priority 降序排列
        self.intents.sort(key=lambda x: x.priority, reverse=True)

    # ===== 查询 =====

    def lookup(self, analysis_goal: str) -> Optional[AnalysisIntent]:
        """中文分析目标 → AnalysisIntent"""
        if not analysis_goal:
            return None

        goal_lower = analysis_goal.lower()
        best_match: Optional[AnalysisIntent] = None
        best_priority = -1

        for intent in self.intents:
            for keyword in intent.keywords:
                if keyword.lower() in goal_lower:
                    if intent.priority > best_priority:
                        best_match = intent
                        best_priority = intent.priority
                    break

        return best_match

    def lookup_all(self, analysis_goal: str) -> List[AnalysisIntent]:
        """返回所有匹配的 intent（按 priority 降序），用于多意图场景"""
        if not analysis_goal:
            return []
        goal_lower = analysis_goal.lower()
        matches = []
        for intent in self.intents:
            for keyword in intent.keywords:
                if keyword.lower() in goal_lower:
                    matches.append(intent)
                    break
        matches.sort(key=lambda x: x.priority, reverse=True)
        return matches

    def get_by_intent(self, intent: str) -> Optional[AnalysisIntent]:
        """按 intent 标识精确获取"""
        return self._intent_map.get(intent)

    def list_intents(self) -> List[str]:
        """列出所有已注册的 intent 标识"""
        return [i.intent for i in self.intents]

    def get_all(self) -> List[AnalysisIntent]:
        """获取所有已注册的 AnalysisIntent（按 priority 降序）"""
        return list(self.intents)

    # ===== V3 新增：知识查询能力 =====

    def get_template_module_path(self, intent_name: str) -> Optional[str]:
        """intent → Template Python 导入路径

        优先使用 YAML 中的 template_module，否则按约定自动推导。
        """
        intent_obj = self._intent_map.get(intent_name)
        if intent_obj is None:
            return None
        if intent_obj.template_module:
            return intent_obj.template_module
        if intent_obj.template:
            return self._derive_module_path(intent_obj.template)
        return None

    def get_calculator_for(self, intent_name: str) -> Optional[str]:
        """intent → Calculator 类路径"""
        intent_obj = self._intent_map.get(intent_name)
        if intent_obj is None:
            return None
        return intent_obj.calculator or None

    def get_derived_metrics(self, intent_name: str) -> List[str]:
        """intent → 派生指标列表"""
        intent_obj = self._intent_map.get(intent_name)
        if intent_obj is None:
            return []
        return intent_obj.derived_metrics

    def get_schema_requirements(self, intent_name: str) -> Optional[SchemaRequirement]:
        """intent → 数据 Schema 要求"""
        intent_obj = self._intent_map.get(intent_name)
        if intent_obj is None:
            return None
        return intent_obj.schema_requirements

    def get_full_profile(self, intent_name: str) -> Optional[Dict[str, Any]]:
        """intent → 完整分析知识概要"""
        intent_obj = self._intent_map.get(intent_name)
        if intent_obj is None:
            return None
        return intent_obj.to_summary()

    def get_all_profiles(self) -> List[Dict[str, Any]]:
        """返回所有分析类型的概要列表（供 API 返回给前端）"""
        return [i.to_summary() for i in self.intents]

    # ===== V3 新增：列组合 → 推荐意图（从 Planner 迁移） =====

    def suggest_intents_for_columns(
        self,
        time_cols: List[str],
        category_cols: List[str],
        numeric_cols: List[str],
    ) -> List[Dict[str, Any]]:
        """基于数据列特征自动推荐分析意图

        策略：
        1. 优先使用 YAML 中配置的 generator_rules（规则驱动）
        2. 如果 YAML 未配置，使用内建的列-意图映射表
        3. 返回格式与 Planner.generate_default_intents 兼容
        """
        suggestions = []

        # 策略1：遍历已注册 intent 的 generator_rules
        for intent_obj in self.intents:
            for rule in intent_obj.generator_rules:
                requires = rule.get("requires", [])
                if self._match_column_rule(requires, time_cols, category_cols, numeric_cols):
                    suggestions.append({
                        "business_question": rule.get("question_template", "").format(
                            num0=numeric_cols[0] if numeric_cols else "指标",
                            cat0=category_cols[0] if category_cols else "分类",
                            time0=time_cols[0] if time_cols else "时间",
                        ),
                        "analysis_goal": rule.get("goal_template", ""),
                        "priority": rule.get("priority", "medium"),
                        "reason": rule.get("reason", ""),
                        "intent": intent_obj.intent,
                    })

        # 策略2：内建通用规则（YAML 未配置时的兜底）
        if not suggestions:
            suggestions = self._builtin_column_suggestions(time_cols, category_cols, numeric_cols)

        # 去重（按 intent）
        seen = set()
        unique = []
        for s in suggestions:
            if s.get("intent") not in seen:
                seen.add(s.get("intent"))
                unique.append(s)

        return unique[:7]

    @staticmethod
    def _match_column_rule(
        requires: List[str],
        time_cols: List[str],
        category_cols: List[str],
        numeric_cols: List[str],
    ) -> bool:
        """检查列组合是否满足规则要求"""
        for req in requires:
            if req == "time" and not time_cols:
                return False
            if req == "category" and not category_cols:
                return False
            if req == "numeric" and not numeric_cols:
                return False
            if req == "multi_numeric" and len(numeric_cols) < 2:
                return False
            if req == "geo" and not any(
                kw in str(c).lower()
                for c in category_cols
                for kw in ["省份", "省", "城市", "市", "地区", "区域", "geo", "city"]
            ):
                return False
        return True

    @staticmethod
    def _builtin_column_suggestions(
        time_cols: List[str],
        category_cols: List[str],
        numeric_cols: List[str],
    ) -> List[Dict[str, Any]]:
        """内建列-意图映射（兜底规则）"""
        suggestions = []
        # 增长
        if time_cols and numeric_cols:
            suggestions.append({
                "business_question": f"{numeric_cols[0]}的增长趋势如何？",
                "analysis_goal": f"分析{numeric_cols[0]}的增长趋势",
                "priority": "high", "reason": "有时间和数值列", "intent": "growth",
            })
        # 排名
        if category_cols and numeric_cols:
            suggestions.append({
                "business_question": f"哪个{category_cols[0]}的{numeric_cols[0]}最高？",
                "analysis_goal": f"{category_cols[0]}的{numeric_cols[0]}排名对比",
                "priority": "high", "reason": "有分类和数值列", "intent": "ranking",
            })
        # 结构
        if category_cols and numeric_cols:
            suggestions.append({
                "business_question": f"各{category_cols[0]}的{numeric_cols[0]}占比如何？",
                "analysis_goal": f"{category_cols[0]}的{numeric_cols[0]}占比分析",
                "priority": "medium", "reason": "了解结构占比", "intent": "structure",
            })
        # 相关
        if len(numeric_cols) >= 2:
            suggestions.append({
                "business_question": f"{numeric_cols[0]}和{numeric_cols[1]}是否相关？",
                "analysis_goal": f"{numeric_cols[0]}和{numeric_cols[1]}的相关关系",
                "priority": "medium", "reason": "多指标可探索关联", "intent": "correlation",
            })
        # 异常
        if numeric_cols:
            suggestions.append({
                "business_question": f"{numeric_cols[0]}是否存在异常值？",
                "analysis_goal": f"{numeric_cols[0]}的异常值检测",
                "priority": "low", "reason": "识别离群点", "intent": "anomaly",
            })
        # 集中度
        if category_cols and numeric_cols:
            suggestions.append({
                "business_question": f"{numeric_cols[0]}在{category_cols[0]}上是否集中？",
                "analysis_goal": f"{numeric_cols[0]}的集中度分析",
                "priority": "low", "reason": "帕累托效应判断", "intent": "concentration",
            })
        # 地理
        geo_kw = ["省份", "省", "城市", "市", "地区", "区域", "geo", "city"]
        geo_cols = [c for c in category_cols if any(kw in str(c).lower() for kw in geo_kw)]
        if geo_cols and numeric_cols:
            suggestions.append({
                "business_question": f"哪些{geo_cols[0]}的{numeric_cols[0]}最高？",
                "analysis_goal": f"{geo_cols[0]}{numeric_cols[0]}的地理空间分布分析",
                "priority": "high", "reason": "地理空间分布", "intent": "geo",
            })
        return suggestions

    # ===== 动态加载（从 Planner 移入） =====

    def load_template_class(self, intent_name: str):
        """动态加载 Template 类"""
        module_path = self.get_template_module_path(intent_name)
        if module_path is None:
            return None
        try:
            parts = module_path.rsplit(".", 1)
            module = importlib.import_module(parts[0])
            return getattr(module, parts[1])
        except Exception as e:
            import logging as _logging; _logging.getLogger("library").warning(f"load template {intent_name}: {e}")
            return None

    def load_template_spec(self, intent_name: str) -> Optional[Dict[str, Any]]:
        """加载 Template 的 runtime.REQUIRED_SCHEMA（向后兼容 Planner）"""
        template_cls = self.load_template_class(intent_name)
        if template_cls is None:
            return None
        try:
            if hasattr(template_cls, 'runtime'):
                return template_cls.runtime.REQUIRED_SCHEMA
        except Exception:
            pass
        return None

    # ===== 工具方法 =====

    def reload(self):
        """重新加载所有 YAML"""
        self._load_all()