"""
BusinessFactGraph —— 业务事实图谱

将多个 AnalysisPackage 中的 BusinessFinding 抽象为图结构，
建立跨分析类型的关联关系，支持 Cross Analysis 和 Knowledge Graph。

设计原则：
- 只保存 Finding 引用，不复制数据
- 关系类型可扩展
- 支持路径查询和子图提取
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional, Any
from enum import Enum


class RelationType(str, Enum):
    """事实之间的关系类型"""
    # 因果
    CAUSES = "causes"               # A 导致 B
    CONTRIBUTES_TO = "contributes"  # A 对 B 有贡献
    # 层级
    BELONGS_TO = "belongs_to"       # A 属于 B（子维度）
    CONTAINS = "contains"           # A 包含 B（父维度）
    # 关联
    CORRELATES_WITH = "correlates"  # A 与 B 相关
    CONTRADICTS = "contradicts"     # A 与 B 矛盾
    SUPPORTS = "supports"           # A 支持 B 的结论
    # 时序
    PRECEDES = "precedes"           # A 先于 B 发生


@dataclass
class GraphNode:
    """图节点——包装一个 BusinessFinding"""
    id: str                          # = BusinessFinding.id
    finding_title: str = ""          # BusinessFinding.title
    category: str = ""               # BusinessFinding.category.value
    analysis_type: str = ""
    package_index: int = 0           # 来自第几个 AnalysisPackage
    entity: str = ""                 # BusinessFinding.entity
    metric: str = ""                 # BusinessFinding.metric
    value: Optional[float] = None
    severity: str = ""               # BusinessFinding.severity.value
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def node_id(self) -> str:
        return self.id


@dataclass
class GraphEdge:
    """图边——两个 Finding 之间的关系"""
    source_id: str
    target_id: str
    relation: RelationType
    confidence: float = 1.0
    evidence: str = ""               # 关系存在的证据依据
    metadata: Dict[str, Any] = field(default_factory=dict)


class BusinessFactGraph:
    """业务事实图谱

    使用方式：
        graph = BusinessFactGraph()
        graph.add_nodes_from_package(package, package_index=0)
        graph.add_edge("id1", "id2", RelationType.CAUSES, confidence=0.85)
        root_causes = graph.find_root_causes()
    """

    def __init__(self, name: str = ""):
        self.name = name
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        # 索引
        self._outgoing: Dict[str, List[GraphEdge]] = {}    # source → edges
        self._incoming: Dict[str, List[GraphEdge]] = {}    # target → edges
        self._by_category: Dict[str, List[str]] = {}        # category → [node_id]
        self._by_entity: Dict[str, List[str]] = {}          # entity → [node_id]
        self._by_package: Dict[int, List[str]] = {}         # package_index → [node_id]

    # ===== 节点操作 =====

    def add_node(self, node: GraphNode):
        self.nodes[node.id] = node
        cat = node.category
        if cat not in self._by_category:
            self._by_category[cat] = []
        self._by_category[cat].append(node.id)
        if node.entity:
            ent = node.entity.lower()
            if ent not in self._by_entity:
                self._by_entity[ent] = []
            self._by_entity[ent].append(node.id)
        pi = node.package_index
        if pi not in self._by_package:
            self._by_package[pi] = []
        self._by_package[pi].append(node.id)

    def add_nodes_from_package(self, package, package_index: int = 0):
        """从 AnalysisPackage 导入所有 Finding 为节点"""
        from src.analysis_templates.base import AnalysisPackage
        for finding in getattr(package, 'findings', []):
            node = GraphNode(
                id=finding.id,
                finding_title=finding.title,
                category=finding.category.value if hasattr(finding.category, 'value') else str(finding.category),
                analysis_type=getattr(package, 'analysis_type', ''),
                package_index=package_index,
                entity=finding.entity,
                metric=finding.metric,
                value=finding.value,
                severity=finding.severity.value if hasattr(finding.severity, 'value') else str(getattr(finding, 'severity', '')),
                confidence=finding.confidence,
            )
            self.add_node(node)

    # ===== 边操作 =====

    def add_edge(self, source_id: str, target_id: str,
                 relation: RelationType, confidence: float = 1.0,
                 evidence: str = ""):
        """添加关系边"""
        if source_id not in self.nodes or target_id not in self.nodes:
            return
        edge = GraphEdge(
            source_id=source_id, target_id=target_id,
            relation=relation, confidence=confidence, evidence=evidence,
        )
        self.edges.append(edge)
        if source_id not in self._outgoing:
            self._outgoing[source_id] = []
        self._outgoing[source_id].append(edge)
        if target_id not in self._incoming:
            self._incoming[target_id] = []
        self._incoming[target_id].append(edge)

    # ===== 查询方法 =====

    def find_root_causes(self) -> List[Tuple[GraphNode, List[GraphNode]]]:
        """查找根因：所有入边为 CAUSES/CONTRIBUTES_TO 的目标节点

        返回 List[(根因节点, [导致原因列表])]
        """
        causes = []
        for node_id, in_edges in self._incoming.items():
            cause_edges = [e for e in in_edges
                           if e.relation in (RelationType.CAUSES, RelationType.CONTRIBUTES_TO)]
            if cause_edges and node_id in self.nodes:
                cause_nodes = [self.nodes[e.source_id]
                               for e in cause_edges if e.source_id in self.nodes]
                causes.append((self.nodes[node_id], cause_nodes))
        return causes

    def find_supporters(self, node_id: str) -> List[GraphNode]:
        """查找支持某结论的所有节点"""
        in_edges = self._incoming.get(node_id, [])
        support_edges = [e for e in in_edges if e.relation == RelationType.SUPPORTS]
        return [self.nodes[e.source_id] for e in support_edges
                if e.source_id in self.nodes]

    def find_contradictions(self, node_id: str) -> List[GraphNode]:
        """查找与某结论矛盾的所有节点"""
        in_edges = self._incoming.get(node_id, [])
        contra_edges = [e for e in in_edges if e.relation == RelationType.CONTRADICTS]
        return [self.nodes[e.source_id] for e in contra_edges
                if e.source_id in self.nodes]

    def get_nodes_by_category(self, category: str) -> List[GraphNode]:
        """按类别获取节点"""
        node_ids = self._by_category.get(category, [])
        return [self.nodes[nid] for nid in node_ids if nid in self.nodes]

    def get_nodes_by_entity(self, entity: str) -> List[GraphNode]:
        """按实体获取节点"""
        node_ids = self._by_entity.get(entity.lower(), [])
        return [self.nodes[nid] for nid in node_ids if nid in self.nodes]

    def get_package_nodes(self, package_index: int) -> List[GraphNode]:
        """获取某个包的所有节点"""
        node_ids = self._by_package.get(package_index, [])
        return [self.nodes[nid] for nid in node_ids if nid in self.nodes]

    def get_all_nodes(self) -> List[GraphNode]:
        return list(self.nodes.values())

    def get_all_edges(self) -> List[GraphEdge]:
        return list(self.edges)

    # ===== 分析 =====

    def get_cross_package_relations(self) -> List[GraphEdge]:
        """获取跨包的边"""
        cross = []
        for edge in self.edges:
            src_node = self.nodes.get(edge.source_id)
            tgt_node = self.nodes.get(edge.target_id)
            if src_node and tgt_node and src_node.package_index != tgt_node.package_index:
                cross.append(edge)
        return cross

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def to_summary(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "cross_package_edges": len(self.get_cross_package_relations()),
            "categories": {cat: len(ids) for cat, ids in self._by_category.items()},
            "entities": {ent: len(ids) for ent, ids in self._by_entity.items()},
        }