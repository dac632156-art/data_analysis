"""
Widget Relationship Engine —— Widget 间语义关系识别引擎

核心职责：
- 识别 SemanticWidget 之间的业务关系
- 构建 Dependency Graph（依赖关系图）
- 为后续 Dashboard Composition Planner 提供组合依据

设计原则：
- 关系不是硬编码的，而是从业务语义自动推断
- 基于 analysis_type 互补规则 + business_topic 相似度 + dimension 交叉识别
- 采用 RelationshipRule + TopicGraph 双引擎
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field

from src.dashboard.semantic_models import (
    SemanticWidget, WidgetRelation, RelationType,
    DependencyGraph, BusinessTopic, VisualRole, AnalyticalRole,
)


# ============================================================
# Relationship Rules —— 声明式关系规则
# ============================================================

@dataclass
class RelationshipRule:
    """关系规则——定义两个 analysis_type 之间的默认关系

    规则特点：
    - 声明式配置，不含逻辑分支
    - 定义 A → B 的默认关系类型和描述
    - Dashboard Composition Planner 可以据此组合 Widget
    """
    source_type: str = ""          # 来源 analysis_type
    target_type: str = ""          # 目标 analysis_type
    relation_type: RelationType = RelationType.COMPLEMENT
    description: str = ""          # 关系描述


# 关系规则注册表
# 定义：A 解释 B / A 依赖 B / A 补充 B / A 对比 B / A 下钻 B
RELATIONSHIP_RULES: List[RelationshipRule] = [
    # ===== 增长趋势 → 解释关系 =====
    # 销售趋势：区域排名解释变化来源
    RelationshipRule(
        source_type="growth_analysis",
        target_type="ranking_analysis",
        relation_type=RelationType.EXPLAIN,
        description="排名分析解释增长趋势的变化来源",
    ),
    # 销售趋势：结构分析解释结构原因
    RelationshipRule(
        source_type="growth_analysis",
        target_type="structure_analysis",
        relation_type=RelationType.EXPLAIN,
        description="结构分析揭示增长变化的构成原因",
    ),
    # 销售趋势：地理分析解释区域贡献
    RelationshipRule(
        source_type="growth_analysis",
        target_type="geo_analysis",
        relation_type=RelationType.EXPLAIN,
        description="地理分析揭示增长变化的区域贡献",
    ),
    # 销售趋势：异常分析揭示异常点
    RelationshipRule(
        source_type="growth_analysis",
        target_type="anomaly_analysis",
        relation_type=RelationType.COMPLEMENT,
        description="异常分析标记趋势中的离群点",
    ),

    # ===== 排名 → 下钻/补充关系 =====
    # 排名：结构分析提供占比细节
    RelationshipRule(
        source_type="ranking_analysis",
        target_type="structure_analysis",
        relation_type=RelationType.DRILL,
        description="结构分析提供排名对象的占比细节",
    ),
    # 排名：对比分析提供差异对比
    RelationshipRule(
        source_type="ranking_analysis",
        target_type="comparison_analysis",
        relation_type=RelationType.COMPLEMENT,
        description="对比分析提供排名对象的差异对比",
    ),
    # 排名：集中度分析评估分布集中度
    RelationshipRule(
        source_type="ranking_analysis",
        target_type="concentration_analysis",
        relation_type=RelationType.COMPLEMENT,
        description="集中度分析评估排名分布的集中程度",
    ),

    # ===== 结构 → 补充/依赖关系 =====
    # 结构：对比分析补充差异视角
    RelationshipRule(
        source_type="structure_analysis",
        target_type="comparison_analysis",
        relation_type=RelationType.COMPLEMENT,
        description="对比分析补充结构差异的量化视角",
    ),
    # 结构：排名分析提供排名参考
    RelationshipRule(
        source_type="structure_analysis",
        target_type="ranking_analysis",
        relation_type=RelationType.DEPEND,
        description="排名分析为结构分析提供排序参考",
    ),

    # ===== 对比 → 补充关系 =====
    # 对比：分布分析补充统计分布
    RelationshipRule(
        source_type="comparison_analysis",
        target_type="distribution_analysis",
        relation_type=RelationType.COMPLEMENT,
        description="分布分析补充对比对象的统计特征",
    ),

    # ===== 地理 → 下钻关系 =====
    # 地理：排名分析提供排序视角
    RelationshipRule(
        source_type="geo_analysis",
        target_type="ranking_analysis",
        relation_type=RelationType.DRILL,
        description="排名分析提供地理维度的排序视角",
    ),

    # ===== 异常 → 依赖/补充关系 =====
    # 异常：增长分析提供趋势背景
    RelationshipRule(
        source_type="anomaly_analysis",
        target_type="growth_analysis",
        relation_type=RelationType.DEPEND,
        description="增长趋势为异常检测提供背景参考",
    ),

    # ===== 留存 → 补充关系 =====
    # 留存：增长分析提供增长背景
    RelationshipRule(
        source_type="retention_analysis",
        target_type="growth_analysis",
        relation_type=RelationType.COMPLEMENT,
        description="增长趋势为留存分析提供宏观背景",
    ),
]


# ============================================================
# Topic Graph —— 业务主题关系图
# ============================================================

# 同一 BusinessTopic 下的 Widget 自动建立 COMPLEMENT 关系
TOPIC_COMPLEMENT_MAP: Dict[str, List[str]] = {
    "sales": ["growth_analysis", "ranking_analysis", "structure_analysis", "geo_analysis"],
    "customer": ["retention_analysis", "growth_analysis"],
    "finance": ["growth_analysis", "comparison_analysis", "concentration_analysis"],
    "operation": ["geo_analysis", "ranking_analysis", "efficiency_analysis"],
    "growth": ["growth_analysis", "anomaly_analysis", "comparison_analysis"],
    "risk": ["anomaly_analysis", "concentration_analysis", "distribution_analysis"],
}


# ============================================================
# Relationship Engine —— 关系识别引擎
# ============================================================

class RelationshipEngine:
    """Widget 关系识别引擎

    使用方式：
        engine = RelationshipEngine()
        graph = engine.build_relationships(widgets)
    """

    def __init__(self):
        self._rule_map: Dict[Tuple[str, str], RelationshipRule] = {}
        for rule in RELATIONSHIP_RULES:
            self._rule_map[(rule.source_type, rule.target_type)] = rule

    def build_relationships(self, widgets: List[SemanticWidget]) -> DependencyGraph:
        """构建 Widget 间的关系图

        算法：
        1. 遍历所有 Widget 组合
        2. 对每个组合尝试匹配关系规则
        3. 同一 BusinessTopic 的 Widget 自动建立 COMPLEMENT 关系
        4. 共享 dimension/metric 的 Widget 自动建立 DEPEND 关系

        Returns:
            DependencyGraph 包含 nodes 和 edges
        """
        graph = DependencyGraph()

        # 注册所有 Widget 为节点
        for w in widgets:
            graph.nodes[w.id] = f"{w.title} ({w.business_topic.value}/{w.visual_role.value})"

        # 两遍扫描：规则匹配 + 主题匹配
        # Pass 1: 规则匹配（显式关系规则）
        self._match_by_rules(widgets, graph)

        # Pass 2: 主题匹配（同一 BusinessTopic 的 Widget 互补）
        self._match_by_topic(widgets, graph)

        # Pass 3: 维度/指标匹配（共享 dimension 的 Widget 依赖）
        self._match_by_dimension(widgets, graph)

        return graph

    def attach_relationships(self, widgets: List[SemanticWidget],
                              graph: DependencyGraph) -> List[SemanticWidget]:
        """将 DependencyGraph 中的关系附加到 SemanticWidget 的 related_widgets 字段

        Args:
            widgets: SemanticWidget 列表
            graph: DependencyGraph

        Returns:
            更新了 related_widgets 的 SemanticWidget 列表
        """
        # 建立 widget_id → widget 的映射
        widget_map: Dict[str, SemanticWidget] = {w.id: w for w in widgets}

        # 为每个 Widget 附加相关关系
        for edge in graph.edges:
            source_id = edge["source"]
            target_id = edge["target"]
            relation_type_str = edge["type"]
            description = edge["description"]

            source_widget = widget_map.get(source_id)
            if source_widget is None:
                continue

            # 防止重复添加
            existing_targets = {r.target_widget_id for r in source_widget.related_widgets}
            if target_id in existing_targets:
                continue

            try:
                relation_type = RelationType(relation_type_str)
            except ValueError:
                relation_type = RelationType.COMPLEMENT

            source_widget.related_widgets.append(
                WidgetRelation(
                    target_widget_id=target_id,
                    relation_type=relation_type,
                    description=description,
                )
            )

        return widgets

    # ============================================================
    # 匹配策略
    # ============================================================

    def _match_by_rules(self, widgets: List[SemanticWidget], graph: DependencyGraph):
        """Pass 1: 规则匹配——查找显式定义的关系规则"""
        for i, w1 in enumerate(widgets):
            for j, w2 in enumerate(widgets):
                if i == j:
                    continue

                type1 = w1.analysis_type.replace("_analysis", "") + "_analysis"
                if not type1.endswith("_analysis"):
                    type1 = w1.analysis_type
                type2 = w2.analysis_type.replace("_analysis", "") + "_analysis"
                if not type2.endswith("_analysis"):
                    type2 = w2.analysis_type

                rule = self._rule_map.get((type1, type2))
                if rule:
                    graph.add_relation(
                        w1.id, w2.id,
                        rule.relation_type, rule.description,
                    )

    def _match_by_topic(self, widgets: List[SemanticWidget], graph: DependencyGraph):
        """Pass 2: 主题匹配——同一 BusinessTopic 的 Widget 互补"""
        # 按 BusinessTopic 分组
        topic_groups: Dict[str, List[SemanticWidget]] = {}
        for w in widgets:
            topic = w.business_topic.value
            if topic not in topic_groups:
                topic_groups[topic] = []
            topic_groups[topic].append(w)

        # 同一 topic 内的 Widget 建立 COMPLEMENT 关系（排除已有关系的）
        existing_edges = {(e["source"], e["target"]) for e in graph.edges}

        for topic, group in topic_groups.items():
            if len(group) < 2:
                continue

            for i, w1 in enumerate(group):
                for j, w2 in enumerate(group):
                    if i >= j:
                        continue
                    if (w1.id, w2.id) in existing_edges:
                        continue

                    # 不同 visual_role 的 Widget 互补更有价值
                    if w1.visual_role != w2.visual_role:
                        desc = f"同属{topic}领域，{w1.visual_role.value}与{w2.visual_role.value}视角互补"
                        graph.add_relation(w1.id, w2.id, RelationType.COMPLEMENT, desc)

    def _match_by_dimension(self, widgets: List[SemanticWidget], graph: DependencyGraph):
        """Pass 3: 维度匹配——共享 dimension 的 Widget 依赖"""
        existing_edges = {(e["source"], e["target"]) for e in graph.edges}

        # 提取 Widget 的 dimension 信息
        widget_dims: Dict[str, str] = {}
        for w in widgets:
            # dimension 信息可能在 metadata 或 analysis_type 中推断
            dim = w.metadata.get("dimension", "") or ""
            metric = w.metadata.get("metric", "") or ""
            if dim:
                widget_dims[w.id] = dim.lower()

        # 共享相同 dimension 的 Widget 建立 DEPEND 关系
        dim_groups: Dict[str, List[str]] = {}
        for wid, dim in widget_dims.items():
            if dim not in dim_groups:
                dim_groups[dim] = []
            dim_groups[dim].append(wid)

        for dim, wids in dim_groups.items():
            if len(wids) < 2:
                continue

            for i, id1 in enumerate(wids):
                for j, id2 in enumerate(wids):
                    if i >= j:
                        continue
                    if (id1, id2) in existing_edges:
                        continue

                    # Hero/Major Widget → Minor Widget 的 DEPEND 关系
                    w1 = next((w for w in widgets if w.id == id1), None)
                    w2 = next((w for w in widgets if w.id == id2), None)
                    if w1 and w2:
                        desc = f"共享维度'{dim}'，{w1.visual_role.value}依赖{w2.visual_role.value}"
                        graph.add_relation(id1, id2, RelationType.DEPEND, desc)


# ============================================================
# Simplified Dependency Graph Builder —— 快速生成依赖图
# ============================================================

def build_dependency_graph(widgets: List[SemanticWidget]) -> Dict[str, List[str]]:
    """简化版依赖图——生成 widget_id → [related_widget_ids] 的映射

    用于 Dashboard Composition Planner 快速查询 Widget 组合。

    Returns:
        {"sales_trend_001": ["region_sales_002", "product_sales_003"], ...}
    """
    engine = RelationshipEngine()
    graph = engine.build_relationships(widgets)

    # 转为简化映射
    result: Dict[str, List[str]] = {}
    for w in widgets:
        result[w.id] = []

    for edge in graph.edges:
        source = edge["source"]
        target = edge["target"]
        if source in result and target not in result[source]:
            result[source].append(target)

    return result
