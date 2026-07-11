"""
Composition Graph Builder —— 从 Widget 关系构建 Composition Graph

核心职责：
- 将 SemanticWidget 的 related_widgets 转换为 CompositionGraph
- 识别 Widget Cluster（围绕核心 Widget 的关联集合）
- 为 Layout Engine 提供 Widget 组合依据

设计原则：
- Composition Graph 是 Composition Planner 的内部数据结构
- 不依赖 RelationshipEngine（RelationshipEngine 是 Semantic Widget Generator 的一部分）
- Composition Graph 从已有的 related_widgets 构建，不重新识别关系
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict

from src.dashboard.semantic_models import (
    SemanticWidget, RelationType, VisualRole,
)
from src.dashboard.composition_schema import (
    CompositionGraph, CompositionEdge, CompositionCluster,
)


# ============================================================
# Cluster Type Mapping —— visual_role 组合 → 簇类型
# ============================================================

CLUSTER_TYPE_MAP: Dict[str, str] = {
    "primary_trend": "trend_cluster",
    "ranking": "ranking_cluster",
    "composition": "structure_cluster",
    "geographic": "geo_cluster",
    "warning": "anomaly_cluster",
    "overview_metric": "kpi_cluster",
    "comparison": "comparison_cluster",
    "distribution": "distribution_cluster",
    "concentration": "concentration_cluster",
    "correlation": "correlation_cluster",
    "detail": "detail_cluster",
    "summary_card": "summary_cluster",
}


# ============================================================
# Composition Graph Builder
# ============================================================

class CompositionGraphBuilder:
    """从 SemanticWidget 的 related_widgets 构建 CompositionGraph

    使用方式：
        builder = CompositionGraphBuilder()
        graph = builder.build(widgets)
    """

    def build(self, widgets: List[SemanticWidget]) -> CompositionGraph:
        """构建 Composition Graph

        Args:
            widgets: SemanticWidget 列表（已含 related_widgets）

        Returns:
            CompositionGraph（含 nodes, edges, clusters）
        """
        graph = CompositionGraph()

        # Step 1: 注册所有 Widget 为 nodes
        for w in widgets:
            graph.nodes[w.id] = f"{w.title} ({w.visual_role.value})"

        # Step 2: 从 related_widgets 构建 edges
        for w in widgets:
            for rel in w.related_widgets:
                edge = CompositionEdge(
                    source=w.id,
                    target=rel.target_widget_id,
                    relation_type=rel.relation_type.value,
                    description=rel.description,
                )
                graph.edges.append(edge)

        # Step 3: 识别 Widget Cluster
        clusters = self._identify_clusters(widgets)
        graph.clusters = clusters

        return graph

    def _identify_clusters(self, widgets: List[SemanticWidget]) -> List[CompositionCluster]:
        """识别 Widget Cluster——围绕核心 Widget 的关联集合

        算法：
        1. 对每个有 related_widgets 的 Widget，尝试构建 Cluster
        2. 核心 Widget = importance_score 最高
        3. 成员 = related_widgets 中所有 target Widget
        4. 合并重叠的 Cluster（共享成员的 Cluster 合并为一个）
        """
        # 构建 widget_id → widget 映射
        widget_map: Dict[str, SemanticWidget] = {w.id: w for w in widgets}

        # 找出所有有关系的 Widget
        connected_widgets = [w for w in widgets if w.related_widgets]

        if not connected_widgets:
            # 没有关系 → 每个 Widget 自成一个单节点
            return []

        # 按 importance_score 降序排列
        connected_widgets.sort(key=lambda w: w.importance_score, reverse=True)

        # 对每个核心 Widget 构建 Cluster
        raw_clusters: List[CompositionCluster] = []
        used_widgets: Set[str] = set()

        for core in connected_widgets:
            if core.id in used_widgets:
                continue

            members = [core.id]
            for rel in core.related_widgets:
                if rel.target_widget_id in widget_map and rel.target_widget_id not in used_widgets:
                    members.append(rel.target_widget_id)

            if len(members) < 2:
                continue

            # 标记已使用
            for m in members:
                used_widgets.add(m)

            # 确定 Cluster 类型
            cluster_type = CLUSTER_TYPE_MAP.get(core.visual_role.value, "general_cluster")

            # 构建 Cluster 描述
            member_widgets = [widget_map[m] for m in members if m in widget_map]
            desc_parts = [w.title for w in member_widgets[:3]]
            description = " + ".join(desc_parts)
            if len(members) > 3:
                description += f" 等{len(members)}个组件"

            cluster = CompositionCluster(
                core_widget_id=core.id,
                cluster_type=cluster_type,
                member_ids=members,
                description=description,
            )
            raw_clusters.append(cluster)

        # 未被 Cluster 收编的独立 Widget 也需要记录
        # （但不创建单节点 Cluster，因为没有组合意义）

        return raw_clusters
