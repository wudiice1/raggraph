"""知识图谱模块：全图点线数据（ECharts 直出）+ 节点详情（含一跳邻居与证据句）。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.api.v1.deps import get_current_user
from app.database import get_db
from app.models import Document, Entity, EntityType, Evidence, Relation, RelationType, User
from app.schemas.graph import (
    CategoryOut,
    EvidenceOut,
    GraphEdgeOut,
    GraphNodeOut,
    GraphOverviewOut,
    NeighborOut,
    NodeDetailOut,
    NodeEntityOut,
    NodeRelationOut,
)

router = APIRouter()


@router.get("/overview", response_model=GraphOverviewOut, summary="图谱总览（点线数据）")
def graph_overview(
    limit: int = Query(500, ge=1, le=2000, description="返回的边数上限（采样保护）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    head = aliased(Entity)
    tail = aliased(Entity)

    total_edges = (
        db.scalar(
            select(func.count())
            .select_from(Relation)
            .join(head, Relation.head_id == head.id)
            .where(head.user_id == current_user.id)
        )
        or 0
    )

    # 按权重取边（每条边带两端实体与关系类型）
    rows = db.execute(
        select(Relation, head, tail, RelationType.name)
        .join(head, Relation.head_id == head.id)
        .join(tail, Relation.tail_id == tail.id)
        .join(RelationType, Relation.relation_type_id == RelationType.id)
        .where(head.user_id == current_user.id)
        .order_by(Relation.weight.desc(), Relation.id.desc())
        .limit(limit)
    ).all()

    node_map: dict[int, Entity] = {}
    edges: list[GraphEdgeOut] = []
    for rel, h, t, rt_name in rows:
        node_map.setdefault(h.id, h)
        node_map.setdefault(t.id, t)
        edges.append(
            GraphEdgeOut(
                id=rel.id,
                source=h.id,
                target=t.id,
                relation_type_name=rt_name,
                weight=rel.weight,
            )
        )

    # 补孤立实体（无任何关系的实体按频次补足节点上限）
    if len(node_map) < limit:
        used = list(node_map) or [-1]
        isolated = db.scalars(
            select(Entity)
            .where(Entity.user_id == current_user.id, Entity.id.not_in(used))
            .order_by(Entity.frequency.desc())
            .limit(limit - len(node_map))
        ).all()
        for ent in isolated:
            node_map[ent.id] = ent

    types = db.scalars(select(EntityType).order_by(EntityType.id)).all()
    type_by_id = {t.id: t for t in types}

    nodes = [
        GraphNodeOut(
            id=e.id,
            name=e.name,
            value=e.frequency,
            category=e.type_id,
            color=type_by_id[e.type_id].color if e.type_id in type_by_id else "#999999",
            type_name=type_by_id[e.type_id].name if e.type_id in type_by_id else "未知",
        )
        for e in node_map.values()
    ]

    total_nodes = (
        db.scalar(select(func.count()).select_from(Entity).where(Entity.user_id == current_user.id)) or 0
    )

    return GraphOverviewOut(
        nodes=nodes,
        edges=edges,
        categories=[CategoryOut(id=t.id, name=t.name, color=t.color) for t in types],
        relation_types=[
            {"id": rt.id, "name": rt.name}
            for rt in db.scalars(select(RelationType).order_by(RelationType.id)).all()
        ],
        total_nodes=total_nodes,
        total_edges=total_edges,
        sampled=len(edges) >= limit or len(node_map) >= limit,
    )


@router.get("/node/{entity_id}", response_model=NodeDetailOut, summary="节点详情（关系+邻居+证据句）")
def node_detail(
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ent = db.get(Entity, entity_id)
    if ent is None or ent.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="实体不存在")

    et = db.get(EntityType, ent.type_id)

    def _neighbors(self_fk, other_fk, direction: str) -> list[NodeRelationOut]:
        other = aliased(Entity)
        oet = aliased(EntityType)
        rows = db.execute(
            select(Relation, other, oet, RelationType)
            .join(other, other_fk == other.id)
            .join(oet, other.type_id == oet.id)
            .join(RelationType, Relation.relation_type_id == RelationType.id)
            .where(self_fk == ent.id)
            .order_by(Relation.weight.desc(), Relation.id.desc())
        ).all()
        return [
            NodeRelationOut(
                id=rel.id,
                relation_type_name=rt.name,
                direction=direction,
                weight=rel.weight,
                other=NeighborOut(id=o.id, name=o.name, type_name=oet.name, color=oet.color),
            )
            for rel, o, oet, rt in rows
        ]

    relations = _neighbors(Relation.head_id, Relation.tail_id, "out") + _neighbors(
        Relation.tail_id, Relation.head_id, "in"
    )

    # 证据句（该实体涉及的所有关系，限 50 条，携带来源文档名）
    ev_rows: list[EvidenceOut] = []
    if relations:
        rel_ids = [r.id for r in relations]
        for ev, filename in db.execute(
            select(Evidence, Document.filename)
            .join(Document, Evidence.document_id == Document.id)
            .where(Evidence.relation_id.in_(rel_ids))
            .order_by(Evidence.id.desc())
            .limit(50)
        ).all():
            ev_rows.append(
                EvidenceOut(
                    id=ev.id,
                    sentence=ev.sentence,
                    document_id=ev.document_id,
                    document_filename=filename,
                    segment_id=ev.segment_id,
                )
            )

    return NodeDetailOut(
        entity=NodeEntityOut(
            id=ent.id,
            name=ent.name,
            type={"id": et.id, "name": et.name, "color": et.color} if et else {"id": 0, "name": "未知", "color": "#999999"},
            frequency=ent.frequency,
            attributes=ent.attributes,
        ),
        relations=relations,
        evidences=ev_rows,
    )
