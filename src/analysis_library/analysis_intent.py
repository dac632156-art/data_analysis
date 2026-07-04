"""
AnalysisIntent —— 分析意图数据对象

每个 YAML 配置文件解析后生成一个 AnalysisIntent 实例。
它是 Library 和 Planner 之间的唯一数据契约。
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class OutputSpec:
    """分析输出的类型定义"""
    charts: List[str] = field(default_factory=list)   # ["line", "bar", "area"]
    tables: List[str] = field(default_factory=list)   # ["growth_table"]
    kpis: List[str] = field(default_factory=list)     # ["growth_rate", "total_growth"]


@dataclass
class AnalysisIntent:
    """分析意图——Library 的核心数据对象

    每个 YAML 配置文件描述了一个分析类型的所有业务知识。
    Planner 通过 lookup() 获取此对象后，从中读取 template 名和 algorithm，
    然后加载对应 Template 执行计算。
    """
    # 唯一标识
    intent: str                      # "growth"

    # 展示信息
    display_name: str                # "增长分析"
    description: str = ""            # "用于分析指标增长趋势"

    # 模板映射
    template: str = ""               # "growth_analysis"

    # 算法配置
    default_algorithm: Optional[str] = None   # "yoy"
    supported_algorithms: List[str] = field(default_factory=list)  # ["yoy", "mom", "qoq"]

    # 关键词（中文触发词）
    keywords: List[str] = field(default_factory=list)  # ["增长", "趋势", "同比", ...]

    # 优先级（lookup 多匹配时取最高分）
    priority: int = 50

    # 输出规范
    outputs: OutputSpec = field(default_factory=OutputSpec)

    # 示例问题
    examples: List[str] = field(default_factory=list)

    # Fallback 策略（intent 列表，按顺序尝试）
    fallback: List[str] = field(default_factory=list)

    # 分析层级：L1=描述统计, L2=派生统计, L3=业务分析
    level: str = "L1"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisIntent":
        """从 YAML 解析的字典构造 AnalysisIntent"""
        outputs_data = data.get("outputs", {})
        return cls(
            intent=data.get("intent", ""),
            display_name=data.get("display_name", ""),
            description=data.get("description", ""),
            template=data.get("template", ""),
            default_algorithm=data.get("default_algorithm"),
            supported_algorithms=data.get("supported_algorithms", []),
            keywords=data.get("keywords", []),
            priority=data.get("priority", 50),
            outputs=OutputSpec(
                charts=outputs_data.get("charts", []),
                tables=outputs_data.get("tables", []),
                kpis=outputs_data.get("kpis", []),
            ),
            examples=data.get("examples", []),
            fallback=data.get("fallback", []),
            level=data.get("level", "L1"),
        )
