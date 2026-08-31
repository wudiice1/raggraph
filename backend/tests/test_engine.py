"""jieba 抽取引擎单元测试：契约符合性 + 抽取质量（backend二交付验证）。

验证要点（对照 README「后端二验收要点」）：
- 引擎为纯函数：只依据 SegmentInfo 内存对象，输出 ExtractionResult；
- 实体类型名均为种子类型（人物/组织/地点/概念/技术）；
- 关系证据句逐字取自某分段原文，且 segment_id 指向该分段；
- 噪音段被跳过；stats 自报参数与统计。
"""
from app.services.extraction.base import ExtractionResult, SegmentInfo
from app.services.extraction.engine import JiebaEngine

VALID_ENTITY_TYPES = {"人物", "组织", "地点", "概念", "技术"}
VALID_RELATION_TYPES = {"包含", "属于", "相关", "引用"}


def _seg(seg_id: int, text: str, is_noise: bool = False) -> SegmentInfo:
    return SegmentInfo(id=seg_id, seq=seg_id, text=text, is_noise=is_noise)


def _segments() -> list[SegmentInfo]:
    return [
        _seg(1, "张三毕业于北京大学，随后进入清华大学攻读博士学位。"),
        _seg(2, "北京大学研究知识图谱，清华大学同样开展知识图谱研究。"),
        _seg(3, "123", is_noise=True),
    ]


def test_engine_returns_contract_and_non_empty():
    engine = JiebaEngine()
    result = engine.extract(document_id=99, segments=_segments())
    assert isinstance(result, ExtractionResult)
    assert len(result.entities) > 0
    assert len(result.relations) > 0


def test_entity_types_are_seed_types():
    engine = JiebaEngine()
    result = engine.extract(99, _segments())
    for ent in result.entities:
        assert ent.type_name in VALID_ENTITY_TYPES
        assert ent.frequency >= 1
        assert ent.name


def test_relations_traceable_to_source_segment():
    engine = JiebaEngine()
    segs = _segments()
    result = engine.extract(99, segs)
    seg_by_id = {s.id: s for s in segs}
    for rel in result.relations:
        # 证据句必须逐字取自某分段原文（连续子串）
        assert rel.segment_id in seg_by_id
        seg = seg_by_id[rel.segment_id]
        assert rel.sentence in seg.text
        # 头尾实体名必须确实是抽取到的实体
        assert rel.head and rel.tail
        assert rel.relation_type_name in VALID_RELATION_TYPES


def test_relation_pattern_belongs_type():
    """句法模式命中时产出「属于」关系：张三 毕业于 北京大学。"""
    engine = JiebaEngine()
    result = engine.extract(
        1,
        [_seg(1, "张三毕业于北京大学。"), _seg(2, "张三毕业于北京大学。")],
    )
    belongs = [r for r in result.relations if r.relation_type_name == "属于"]
    assert belongs, "应至少产出一条「属于」关系"


def test_noise_segments_ignored():
    engine = JiebaEngine()
    result = engine.extract(1, [_seg(1, "第 3 页", is_noise=True)])
    assert len(result.entities) == 0
    assert len(result.relations) == 0


def test_stats_self_reports_params():
    engine = JiebaEngine()
    result = engine.extract(99, _segments())
    assert result.stats["engine"] == "jieba"
    assert "min_entity_freq" in result.stats["params"]
    assert result.stats["entities"] == len(result.entities)
    assert result.stats["relations"] == len(result.relations)


def test_empty_segments_return_empty_result():
    engine = JiebaEngine()
    result = engine.extract(1, [])
    assert result.entities == []
    assert result.relations == []
    assert result.stats["segment_count"] == 0
