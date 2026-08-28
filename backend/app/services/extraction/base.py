"""★ 抽取引擎接口契约 —— 后端与「知识抽取引擎同学」的协作分界点。

契约要点：
1. 引擎是**纯函数**：只接收内存对象（SegmentInfo 列表），只返回内存对象（ExtractionResult），
   禁止读取/写入数据库、禁止修改文档状态；
2. 落库（实体合并、关系去重、证据句写入）统一由流水线调用 `writers.apply_extraction_result`
   完成，引擎同学不需要理解 SQLAlchemy；
3. 引擎抛异常 → 流水线回滚本次全部写入 → 文档状态置 failed 并记录 parse_error；
4. `sentence`（证据句）必须逐字取自某个 SegmentInfo.text（可追溯性，EXT-06）；
5. `type_name` / `relation_type_name` 未命中种子类型时，writer 回退到"概念"/"相关"并记录警告日志。

引擎同学接入只需三步（详见 README「抽取引擎接入指南」）：
① 新建 app/services/extraction/engine.py，实现 BaseExtractionEngine.extract；
② 在 app/services/extraction/__init__.py 的 ENGINE_REGISTRY 注册；
③ 将 app/config.py 的 EXTRACTION_ENGINE 默认值改为注册名（或用环境变量覆盖）。
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SegmentInfo:
    """流水线喂给引擎的分段输入（纯内存对象）。"""

    id: int  # segments 表主键
    seq: int  # 文档内序号
    text: str  # 清洗后文本 clean_text
    is_noise: bool = False  # 页码/页眉等噪音段，引擎可自行决定是否跳过


@dataclass
class ExtractedEntity:
    """引擎产出的候选实体。同名实体由 writer 按 (user_id, name) 合并。"""

    name: str  # 实体名（合并键）
    type_name: str = "概念"  # 必须命中 entity_types 种子名称，否则回退"概念"
    frequency: int = 1  # 本文档内出现次数
    attributes: dict[str, Any] = field(default_factory=dict)  # 附加属性（JSON 存储）


@dataclass
class ExtractedRelation:
    """引擎产出的候选关系。证据句 sentence 必须逐字取自某分段的原文。"""

    head: str  # 头实体名（writer 内部解析为实体 id，不存在则自动创建）
    tail: str  # 尾实体名
    relation_type_name: str = "相关"
    sentence: str = ""  # 证据句（EXT-06：逐字取自 SegmentInfo.text）
    segment_id: int = 0  # 证据句所属分段的 SegmentInfo.id；0 表示未定位（writer 会跳过该证据句）
    weight: float = 1.0


@dataclass
class ExtractionResult:
    """引擎输出（纯内存对象）。"""

    entities: list[ExtractedEntity] = field(default_factory=list)
    relations: list[ExtractedRelation] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)  # 引擎自报统计（如 token 数），仅供日志，不落库


class BaseExtractionEngine:
    """抽取引擎抽象基类。实现 extract 即可接入。"""

    name: str = "base"

    def extract(self, document_id: int, segments: list[SegmentInfo]) -> ExtractionResult:
        raise NotImplementedError
