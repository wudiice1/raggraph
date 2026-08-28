"""知识图谱模块响应模型（结构直接面向 ECharts 力导向图，零转换）。"""
from typing import Any

from pydantic import BaseModel


class CategoryOut(BaseModel):
    """实体类型图例（节点着色依据，GRA-03）。"""

    id: int
    name: str
    color: str


class GraphNodeOut(BaseModel):
    id: int
    name: str
    value: int  # 频次（ECharts symbolSize 依据）
    category: int  # 实体类型 id（ECharts categories 索引由前端按 categories 顺序映射）
    color: str
    type_name: str


class GraphEdgeOut(BaseModel):
    id: int
    source: int  # 节点 id
    target: int  # 节点 id
    relation_type_name: str
    weight: float  # 证据句条数


class GraphOverviewOut(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]
    categories: list[CategoryOut]  # 即实体类型，图例显隐直接用
    relation_types: list[dict[str, Any]]  # [{id, name}]
    total_nodes: int
    total_edges: int
    sampled: bool  # 达到采样上限时前端提示（GRA-01）


class NodeEntityOut(BaseModel):
    id: int
    name: str
    type: dict[str, Any]  # {id, name, color}
    frequency: int
    attributes: dict[str, Any] | None


class NeighborOut(BaseModel):
    id: int
    name: str
    type_name: str
    color: str


class NodeRelationOut(BaseModel):
    id: int
    relation_type_name: str
    direction: str  # out（该实体为头）/ in（该实体为尾）
    weight: float
    other: NeighborOut  # 一跳邻居


class EvidenceOut(BaseModel):
    id: int
    sentence: str
    document_id: int
    document_filename: str
    segment_id: int


class NodeDetailOut(BaseModel):
    entity: NodeEntityOut
    relations: list[NodeRelationOut]
    evidences: list[EvidenceOut]
