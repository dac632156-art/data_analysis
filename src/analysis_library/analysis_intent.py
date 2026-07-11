"""
AnalysisIntent —— 分析意图数据对象（V3：Analysis Knowledge Center 核心数据模型）

V3 扩展：
- 新增 required_fields / business_questions / calculator / derived_metrics / schema_requirements
- OutputSpec 升级为 OutputSpecDetail（含描述，不只是名称列表）
- 增加 generator_method 支持 Planner.generate_default_intents 逻辑迁移到 Library
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


# ============================================================
# 输出规范（升级版：含描述）
# ============================================================

@dataclass
class OutputItemSpec:
    """单个输出的详细定义"""
    name: str                     # 如 "growth_rate"
    label: str = ""               # 如 "增长率"（中文展示名）
    description: str = ""         # 如 "YoY同比增长率，单位为%"


@dataclass
class OutputSpecDetail:
    """分析输出的完整定义（V3 升级版：每个输出带有 label 和 description）

    替代 V2 的 OutputSpec（仅含名称列表）。
    """
    charts: List[OutputItemSpec] = field(default_factory=list)
    tables: List[OutputItemSpec] = field(default_factory=list)
    kpis: List[OutputItemSpec] = field(default_factory=list)


# ============================================================
# 字段要求
# ============================================================

@dataclass
class SchemaRequirement:
    """数据 Schema 要求——分析类型对输入数据列的约束

    替代原来分散在 Template.runtime.REQUIRED_SCHEMA 中的定义。
    现在 Library 是唯一权威来源。
    """
    dimension_type: str = ""      # "time" | "category" | "any" | ""
    metric_type: str = "numeric"  # "numeric" | "any"
    min_dimension: int = 0        # 最少需要的维度列数
    min_metric: int = 1           # 最少需要的指标列数
    min_rows: int = 2             # 最少数据行数
    min_distinct_values: int = 2  # 维度最少不同值数


# ============================================================
# AnalysisIntent（V3 全面扩展）
# ============================================================

@dataclass
class AnalysisIntent:
    """分析意图——Analysis Knowledge Center 的核心数据对象

    每个 YAML 描述了一个分析类型的全部业务知识。
    这是整个系统关于"分析是什么"的唯一权威来源。

    V3 新增字段：
    - business_questions: 典型业务问题（AI/用户意图匹配用）
    - calculator: Calculator 类路径
    - template_module: Template 的动态导入路径（从 Planner 移入）
    - derived_metrics: 该分析类型产出的派生指标列表
    - required_fields: 业务层面的字段需求关键词
    - schema_requirements: 数据 Schema 要求
    - generator_rules: 自动意图生成的列组合规则
    """

    # ===== 标识与描述 =====
    intent: str                      # 唯一标识，如 "growth"
    display_name: str                # 中文展示名，如 "增长分析"
    description: str = ""            # 一句话描述
    level: str = "L1"               # L1=描述统计, L2=派生统计, L3=业务分析

    # ===== 关键词与触发 =====
    keywords: List[str] = field(default_factory=list)         # 中文触发词
    business_questions: List[str] = field(default_factory=list)  # V3: 典型业务问题
    examples: List[str] = field(default_factory=list)         # 示例问句
    priority: int = 50                # 匹配优先级（越高越优先）

    # ===== Template 映射 =====
    template: str = ""               # Template 标识名，如 "growth_analysis"
    template_module: str = ""        # V3: 动态导入路径（从 Planner TEMPLATE_MODULES 移入）
                                      # 如 "src.analysis_templates.growth_analysis.GrowthAnalysis"

    # ===== Calculator 映射 =====
    calculator: str = ""             # V3: Calculator 类路径
                                      # 如 "src.calculators.growth.GrowthCalculator"

    # ===== 算法配置 =====
    default_algorithm: Optional[str] = None
    supported_algorithms: List[str] = field(default_factory=list)

    # ===== 数据要求 =====
    schema_requirements: SchemaRequirement = field(default_factory=SchemaRequirement)
                                      # V3: 从 Template.runtime 移入

    required_fields: List[str] = field(default_factory=list)
                                      # V3: 业务字段关键词（如 ["日期", "销售额", "客户ID"]）

    # ===== 输出规范 =====
    outputs: OutputSpecDetail = field(default_factory=OutputSpecDetail)
                                      # V3 升级版：含 label + description

    derived_metrics: List[str] = field(default_factory=list)
                                      # V3: 产出的派生指标（如 ["yoy", "mom", "hhi", "cr5"]）

    # ===== Fallback =====
    fallback: List[str] = field(default_factory=list)         # Fallback 意图链

    # ===== 自动意图生成规则 =====
    generator_rules: List[Dict[str, Any]] = field(default_factory=list)
                                      # V3: Planner.generate_default_intents 的逻辑迁移到 Library
                                      # 每条规则: {"requires": ["time", "numeric"], "priority": "high", "template": "growth"}

    # ===== 兼容字段（V2 → V3 平滑过渡） =====
    _raw: Dict[str, Any] = field(default_factory=dict)
                                      # 保留原始 YAML 数据，供向后兼容

    # ===== 构造方法 =====

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisIntent":
        """从 YAML 解析的字典构造 AnalysisIntent（V3 扩展版）

        兼容 V2 YAML 格式：缺失字段使用默认值。
        """
        # 输出规范（兼容 V2 格式）
        outputs_data = data.get("outputs", {})
        # V3 格式判断：outputs 的某个键对应的值是 list，且 list 第一个元素是 dict
        is_v3 = False
        if outputs_data:
            first_list = next(iter(outputs_data.values()), None)
            if isinstance(first_list, list) and first_list and isinstance(first_list[0], dict):
                is_v3 = True
        if is_v3:
            # V3 格式：每个输出是 {name, label, description}
            charts = [OutputItemSpec(**c) for c in outputs_data.get("charts", [])]
            tables = [OutputItemSpec(**t) for t in outputs_data.get("tables", [])]
            kpis = [OutputItemSpec(**k) for k in outputs_data.get("kpis", [])]
        else:
            # V2 兼容：简单字符串列表 → V3 格式
            charts = [OutputItemSpec(name=c) for c in outputs_data.get("charts", [])]
            tables = [OutputItemSpec(name=t) for t in outputs_data.get("tables", [])]
            kpis = [OutputItemSpec(name=k) for k in outputs_data.get("kpis", [])]

        output_spec = OutputSpecDetail(charts=charts, tables=tables, kpis=kpis)

        # Schema 要求
        schema_data = data.get("schema_requirements", {})
        schema = SchemaRequirement(
            dimension_type=schema_data.get("dimension_type", ""),
            metric_type=schema_data.get("metric_type", "numeric"),
            min_dimension=schema_data.get("min_dimension", 0),
            min_metric=schema_data.get("min_metric", 1),
            min_rows=schema_data.get("min_rows", 2),
            min_distinct_values=schema_data.get("min_distinct_values", 2),
        )

        # Template 模块路径：优先使用显式配置，否则按约定自动推导
        template_module = data.get("template_module", "")
        if not template_module and data.get("template"):
            tmpl = data["template"]
            # 约定：{name}_analysis → src.analysis_templates.{name}_analysis.{CapitalizedName}Analysis
            class_name = "".join(w.capitalize() for w in tmpl.replace("_analysis", "").split("_")) + "Analysis"
            template_module = f"src.analysis_templates.{tmpl}.{class_name}"

        return cls(
            intent=data.get("intent", ""),
            display_name=data.get("display_name", ""),
            description=data.get("description", ""),
            level=data.get("level", "L1"),
            keywords=data.get("keywords", []),
            business_questions=data.get("business_questions", []),
            examples=data.get("examples", []),
            priority=data.get("priority", 50),
            template=data.get("template", ""),
            template_module=template_module,
            calculator=data.get("calculator", ""),
            default_algorithm=data.get("default_algorithm"),
            supported_algorithms=data.get("supported_algorithms", []),
            schema_requirements=schema,
            required_fields=data.get("required_fields", []),
            outputs=output_spec,
            derived_metrics=data.get("derived_metrics", []),
            fallback=data.get("fallback", []),
            generator_rules=data.get("generator_rules", []),
            _raw=data,
        )

    def to_summary(self) -> Dict[str, Any]:
        """返回意图摘要（供 API 返回给前端）"""
        return {
            "intent": self.intent,
            "display_name": self.display_name,
            "description": self.description,
            "level": self.level,
            "keywords": self.keywords[:10],
            "business_questions": self.business_questions[:5],
            "template": self.template,
            "default_algorithm": self.default_algorithm,
            "supported_algorithms": self.supported_algorithms,
            "derived_metrics": self.derived_metrics,
            "priority": self.priority,
            "kpis": [k.name for k in self.outputs.kpis],
            "charts": [c.name for c in self.outputs.charts],
            "tables": [t.name for t in self.outputs.tables],
            "fallback": self.fallback,
            "required_fields": self.required_fields,
        }


# ============================================================
# 兼容别名（V2 代码不需要修改）
# ============================================================

# OutputSpec 向后兼容别名
OutputSpec = OutputSpecDetail