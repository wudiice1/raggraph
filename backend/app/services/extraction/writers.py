"""共享写库层：抽取结果的落库唯一入口（引擎同学不碰本文件）。

职责（对应 PRD EXT-05 / EXT-06）：
- 实体按 (user_id, name) 合并：同名实体跨文档合并为同一节点，频次累加；
- 关系按 (head_id, tail_id, relation_type_id) 去重：重复来源只累加证据句；
- 每条关系关联证据句与来源文档，可追溯；
- 完成后 weight 重算为证据句条数。
"""
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Document, Entity, EntityType, Evidence, Relation, RelationType
from app.services.extraction.base import ExtractionResult

logger = logging.getLogger(__name__)

FALLBACK_ENTITY_TYPE = "概念"
FALLBACK_RELATION_TYPE = "相关"


def _resolve_entity_type(db: Session, type_name: str) -> EntityType:
    et = db.scalar(select(EntityType).where(EntityType.name == type_name))
    if et is not None:
        return et
    if type_name:
        logger.warning("实体类型 %r 不存在，回退为 %r", type_name, FALLBACK_ENTITY_TYPE)
    return db.scalar(select(EntityType).where(EntityType.name == FALLBACK_ENTITY_TYPE))


def _resolve_relation_type(db: Session, type_name: str) -> RelationType:
    rt = db.scalar(select(RelationType).where(RelationType.name == type_name))
    if rt is not None:
        return rt
    if type_name:
        logger.warning("关系类型 %r 不存在，回退为 %r", type_name, FALLBACK_RELATION_TYPE)
    return db.scalar(select(RelationType).where(RelationType.name == FALLBACK_RELATION_TYPE))


def apply_extraction_result(db: Session, document_id: int, result: ExtractionResult) -> dict:
    """把引擎结果写入数据库（单一事务，由流水线统一 commit/rollback）。

    返回 {"entities": 新建实体数, "relations": 新建关系数, "evidences": 新增证据句数}
    """
    doc = db.get(Document, document_id)
    if doc is None:
        raise ValueError(f"文档 {document_id} 不存在")

    counts = {"entities": 0, "relations": 0, "evidences": 0}
    entity_by_name: dict[str, Entity] = {}
    touched_relations: list[Relation] = []

    def get_or_create_entity(name: str, type_name: str, frequency: int, attributes: dict) -> Entity:
        ent = entity_by_name.get(name)
        if ent is None:
            ent = db.scalar(
                select(Entity).where(Entity.user_id == doc.user_id, Entity.name == name)
            )
            if ent is None:
                et = _resolve_entity_type(db, type_name)
                ent = Entity(
                    user_id=doc.user_id,
                    name=name,
                    type_id=et.id,
                    frequency=0,
                    attributes=attributes or None,
                    document_id=document_id,  # 首个来源文档
                )
                db.add(ent)
                db.flush()
                counts["entities"] += 1
            else:
                # 跨文档合并：保留先见类型，附加属性浅合并
                if attributes:
                    ent.attributes = {**(ent.attributes or {}), **attributes}
            entity_by_name[name] = ent
        ent.frequency += frequency
        return ent

    def get_or_create_relation(head: Entity, tail: Entity, type_name: str, weight: float) -> Relation:
        rt = _resolve_relation_type(db, type_name)
        rel = db.scalar(
            select(Relation).where(
                Relation.head_id == head.id,
                Relation.tail_id == tail.id,
                Relation.relation_type_id == rt.id,
            )
        )
        if rel is None:
            rel = Relation(
                head_id=head.id,
                tail_id=tail.id,
                relation_type_id=rt.id,
                document_id=document_id,
                weight=0.0,
            )
            db.add(rel)
            db.flush()
            counts["relations"] += 1
        rel.weight += weight
        touched_relations.append(rel)
        return rel

    # 实体（关系端点若未出现在 entities 列表，也按默认类型补建）
    for ent in result.entities:
        get_or_create_entity(ent.name, ent.type_name, ent.frequency, ent.attributes)

    # 关系 + 证据句
    existing_keys: set[tuple[int, int, str]] = set()
    loaded_relation_ids: set[int] = set()
    for rel in result.relations:
        if not rel.head or not rel.tail:
            continue
        head = get_or_create_entity(rel.head, FALLBACK_ENTITY_TYPE, 0, {})
        tail = get_or_create_entity(rel.tail, FALLBACK_ENTITY_TYPE, 0, {})
        relation = get_or_create_relation(head, tail, rel.relation_type_name, rel.weight)
        # 证据句：segment_id 无效或句式为空的跳过；撞唯一约束去重
        if not rel.sentence or rel.segment_id <= 0:
            continue
        # 每个关系只加载一次已存在证据句（合并关系可能已有其他文档的证据句）
        if relation.id not in loaded_relation_ids:
            existing_keys |= set(
                db.execute(
                    select(Evidence.relation_id, Evidence.segment_id, Evidence.sentence)
                    .where(Evidence.relation_id == relation.id)
                ).all()
            )
            loaded_relation_ids.add(relation.id)
        key = (relation.id, rel.segment_id, rel.sentence)
        if key in existing_keys:
            continue
        db.add(
            Evidence(
                relation_id=relation.id,
                segment_id=rel.segment_id,
                document_id=document_id,
                sentence=rel.sentence,
            )
        )
        existing_keys.add(key)
        counts["evidences"] += 1

    db.flush()

    # weight 重算 = 证据句条数（保持语义自洽：边粗细即证据多寡）
    for rel in set(touched_relations):
        count = db.scalar(
            select(func.count()).select_from(Evidence).where(Evidence.relation_id == rel.id)
        )
        rel.weight = float(count or 0.0)

    return counts
