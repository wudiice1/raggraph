"""抽取引擎共享写库层测试：实体合并 / 关系去重 / 证据句写入 / 类型回退。

本文件同时是「引擎同学接入指南」的可执行示例：按契约产出 ExtractionResult 后，
无需关心任何落库细节。
"""
from sqlalchemy import select

from app.models import Entity, Evidence, Relation, Segment
from app.services.extraction.base import ExtractionResult, ExtractedEntity, ExtractedRelation
from app.services.extraction.writers import apply_extraction_result

from tests.conftest import TEXT_SAMPLE, create_document_direct, get_user, register_and_login


def _setup_doc_with_segments(db, user, client):
    """建文档 + 两分段（走 create_all 种子保证类型存在；client 仅用于触发种子）。"""
    doc = create_document_direct(db, user, TEXT_SAMPLE, status="parsing")
    seg1 = Segment(document_id=doc.id, seq=1, raw_text="张三毕业于北京大学。", clean_text="张三毕业于北京大学。", is_noise=False)
    seg2 = Segment(document_id=doc.id, seq=2, raw_text="北京大学研究知识图谱。", clean_text="北京大学研究知识图谱。", is_noise=False)
    db.add_all([seg1, seg2])
    db.commit()
    return doc, seg1, seg2


def test_apply_result_merge_and_dedupe(client, db):
    token = register_and_login(client)
    user = get_user(db, "alice")
    doc, seg1, seg2 = _setup_doc_with_segments(db, user, client)

    # 第一轮：2 实体 + 1 关系 + 1 证据句
    result1 = ExtractionResult(
        entities=[
            ExtractedEntity(name="张三", type_name="人物", frequency=2),
            ExtractedEntity(name="北京大学", type_name="组织", frequency=1),
        ],
        relations=[
            ExtractedRelation(
                head="张三", tail="北京大学", relation_type_name="属于",
                sentence="张三毕业于北京大学。", segment_id=seg1.id,
            )
        ],
    )
    stats1 = apply_extraction_result(db, doc.id, result1)
    db.commit()
    assert stats1 == {"entities": 2, "relations": 1, "evidences": 1}

    # 第二轮（模拟另一文档再次抽取到相同知识）：实体合并、关系去重、新证据句追加
    result2 = ExtractionResult(
        entities=[ExtractedEntity(name="张三", type_name="人物", frequency=3)],
        relations=[
            ExtractedRelation(
                head="张三", tail="北京大学", relation_type_name="属于",
                sentence="北京大学研究知识图谱。", segment_id=seg2.id,
            )
        ],
    )
    stats2 = apply_extraction_result(db, doc.id, result2)
    db.commit()
    assert stats2 == {"entities": 0, "relations": 0, "evidences": 1}

    db.expire_all()
    # 同名实体合并为同一节点，频次累加（EXT-05 跨文档合并）
    zhangsan = db.scalar(select(Entity).where(Entity.user_id == user.id, Entity.name == "张三"))
    assert zhangsan.frequency == 5
    assert db.scalar(select(Entity).where(Entity.user_id == user.id, Entity.name == "北京大学")).frequency == 1
    # 相同实体对+关系类型只保留一条关系，证据句两条，weight 重算为证据句条数
    rel = db.scalar(
        select(Relation).where(Relation.head_id == zhangsan.id, Relation.tail_id == db.scalar(select(Entity).where(Entity.user_id == user.id, Entity.name == "北京大学")).id)
    )
    assert rel.weight == 2.0
    ev_count = len(db.scalars(select(Evidence).where(Evidence.relation_id == rel.id)).all())
    assert ev_count == 2


def test_unknown_type_falls_back_to_concept(client, db):
    token = register_and_login(client)
    user = get_user(db, "alice")
    doc, seg1, _ = _setup_doc_with_segments(db, user, client)

    result = ExtractionResult(
        entities=[ExtractedEntity(name="神秘实体", type_name="不存在的类型", frequency=1)]
    )
    apply_extraction_result(db, doc.id, result)
    db.commit()

    from app.models import EntityType

    ent = db.scalar(select(Entity).where(Entity.user_id == user.id, Entity.name == "神秘实体"))
    assert ent is not None
    assert ent.type_id == db.scalar(select(EntityType).where(EntityType.name == "概念")).id  # 回退"概念"


def test_relation_endpoint_auto_created(client, db):
    """关系端点未出现在 entities 列表时按默认类型补建。"""
    token = register_and_login(client)
    user = get_user(db, "alice")
    doc, seg1, _ = _setup_doc_with_segments(db, user, client)

    result = ExtractionResult(
        relations=[
            ExtractedRelation(head="甲", tail="乙", relation_type_name="相关", sentence="甲和乙相关。", segment_id=seg1.id)
        ]
    )
    stats = apply_extraction_result(db, doc.id, result)
    db.commit()
    assert stats == {"entities": 2, "relations": 1, "evidences": 1}
    for name in ("甲", "乙"):
        assert db.scalar(select(Entity).where(Entity.user_id == user.id, Entity.name == name)) is not None


def test_evidence_with_invalid_segment_skipped(client, db):
    token = register_and_login(client)
    user = get_user(db, "alice")
    doc, _, _ = _setup_doc_with_segments(db, user, client)

    result = ExtractionResult(
        relations=[ExtractedRelation(head="甲", tail="乙", sentence="无分段定位", segment_id=0)]
    )
    stats = apply_extraction_result(db, doc.id, result)
    db.commit()
    assert stats["evidences"] == 0  # segment_id 无效的证据句被跳过，不影响关系创建
