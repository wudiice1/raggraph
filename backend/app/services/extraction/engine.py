"""jieba 知识抽取引擎（backend二职责）。

设计目标：**通用算法 + 领域数据分离**，引擎代码本身与任何具体词无关（普适）。

对照 README「抽取引擎接入指南」与「后端二验收要点」实现：
1. jieba 分词 + 词性标注，抽取名词/名词短语为候选实体，按频次过滤；
2. 复合词消歧：仅做**词典驱动**合并——从同目录 userdict.txt 读领域词表
   （团队编辑、非代码硬编码），让 jieba 优先整体切出；不再做文档内统计合并，
   因其会把"张三"与"北京大学"粘成一实体而破坏"属于"等实体间关系；
3. 关系抽取：动词锚点的句法模式匹配 + 同句共现补全；每条关系均带逐字证据句与 segment_id；
4. 所有参数与统计在 ExtractionResult.stats 中自报，便于撰写《核心算法说明》。

契约（见 extraction/base.py）：本引擎是纯函数，只接收内存对象、只返回内存对象，
不读写数据库、不改文档状态；落库由 writers.apply_extraction_result 统一完成。
"""
import logging
import re
from collections import Counter
from pathlib import Path

import jieba
import jieba.posseg as pseg

from app.services.extraction.base import (
    BaseExtractionEngine,
    ExtractionResult,
    ExtractedEntity,
    ExtractedRelation,
    SegmentInfo,
)

logger = logging.getLogger(__name__)

# ============ 实体类型（对照 app/core/seed.py DEFAULT_ENTITY_TYPES） ============
TYPE_PERSON = "人物"
TYPE_ORG = "组织"
TYPE_PLACE = "地点"
TYPE_CONCEPT = "概念"
TYPE_TECH = "技术"

# ============ 关系类型（对照 DEFAULT_RELATION_TYPES） ============
REL_CONTAINS = "包含"
REL_BELONGS = "属于"
REL_RELATED = "相关"
REL_REFERENCE = "引用"

# 词性 → 实体类型（jieba 词性标注的名词类；不含 vn/an 等动词名词，避免动词变实体）
_POS_TYPE = {
    "nr": TYPE_PERSON,   # 人名
    "ns": TYPE_PLACE,    # 地名
    "nt": TYPE_ORG,      # 机构名
    "nz": TYPE_CONCEPT,  # 其他专名
    "n": TYPE_CONCEPT,   # 普通名词
    "eng": TYPE_CONCEPT, # 英文/外来词
}

# 组织类后缀：命中则判为「组织」，覆盖 jieba 未能识别为 nt 的专名
_ORG_SUFFIXES = (
    "大学", "学院", "学校", "公司", "集团", "银行", "医院", "研究院",
    "研究所", "政府", "委员会", "协会", "基金会", "中心",
)

# 技术类后缀 / 词：命中判为「技术」（领域相关，可按需迁移）
_TECH_SUFFIXES = ("系统", "平台", "模型", "引擎", "技术", "算法", "框架", "数据库", "图谱")
_TECH_WORDS = {"python", "java", "c++", "人工智能", "机器学习", "深度学习", "大模型", "云计算", "区块链"}

# 常见噪声名词/虚词白名单（语义过于泛化，不宜作为实体）
_STOPWORDS = {
    "一个", "一些", "这个", "那个", "我们", "你们", "他们", "系统", "用户", "文档", "文件",
    "内容", "信息", "数据", "问题", "方法", "方式", "过程", "结果", "情况", "时候",
    "以及", "对于", "通过", "可以", "进行", "实现", "支持", "使用", "提供", "需要",
    "什么", "怎么", "如何", "当前", "整个", "相关",
    # 高频泛化名词（单文档上传默认 freq>=1，需显式剔除这类噪声）
    "方向", "毕业", "教授", "平台", "领域", "方面", "环节", "阶段", "工作", "能力",
    "水平", "优势", "部分", "地方", "人员", "设备", "项目", "成果", "课题", "功能",
}

# 动词锚点 → 关系类型（句法模式匹配）
_PATTERNS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("毕业于", "就读于", "任职于", "就职于", "属于", "来自", "隶属", "入职", "供职于"), REL_BELONGS),
    (("研发", "开发", "构建", "负责", "参与", "研究", "设计", "发布", "提出", "部署"), REL_RELATED),
    (("包含", "包括", "分为", "涵盖", "含有", "涉及", "组成", "构成"), REL_CONTAINS),
    (("引用", "参考", "借鉴", "依据"), REL_REFERENCE),
)

# ============ 通用算法 + 领域数据分离 ============

# 用户词典数据文件（与引擎同目录；团队编辑，缺失则该层为空）。
# 引擎代码与具体词无关；领域复合词由该文件提供，实现"换领域只改数据不改代码"。
_USERDICT_PATH = Path(__file__).with_name("userdict.txt")


def _load_user_dict() -> list[str]:
    """读取用户词典数据文件（每行一个词，# 注释/空行忽略）。文件缺失返回空。"""
    if not _USERDICT_PATH.exists():
        return []
    words: list[str] = []
    for line in _USERDICT_PATH.read_text(encoding="utf-8").splitlines():
        word = line.strip()
        if not word or word.startswith("#"):
            continue
        words.append(word)
    return words


def _ensure_user_dict(words: list[str]) -> None:
    """把领域词加进 jieba 词典（幂等），使其优先被当作一个整体专名。

    必须显式传 tag='nz'（其他专名），否则 add_word 默认标记为 'x'，
    会被引擎的名词过滤排除（正是此前专名抽不出的原因）。
    """
    for word in words:
        jieba.add_word(word, freq=20000, tag="nz")


def _infer_entity_type(word: str, flag: str) -> str:
    """按词性 + 后缀启发式推断实体类型，返回种子类型名之一。"""
    if any(word.endswith(s) for s in _ORG_SUFFIXES):
        return TYPE_ORG
    if flag in ("ns", "nr"):
        return _POS_TYPE[flag]
    if word in _TECH_WORDS or any(word.endswith(s) for s in _TECH_SUFFIXES):
        return TYPE_TECH
    return _POS_TYPE.get(flag, TYPE_CONCEPT)


def _compound_merge(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """相邻名词合并为**词典已知**的复合词（用户词典经 add_word 亦计入）。

    输入 [(word, flag), ...]；当"前一个词 + 当前词"拼接后是 jieba 词典已有的词
    （且长度适中），则合并，保留首个词性。只做词典驱动的合并，不做统计合并——
    统计合并会破坏"实体间的关系"（如把"张三"与"北京大学"粘成一个实体而失去"属于"关系）。
    """
    merged: list[tuple[str, str]] = []
    for word, flag in items:
        if merged and len(word) <= 3:
            prev, prev_flag = merged[-1]
            combined = prev + word
            if 2 <= len(combined) <= 8 and combined in jieba.dt.FREQ:
                merged[-1] = (combined, prev_flag)
                continue
        merged.append((word, flag))
    return [(w, f) for w, f in merged if len(w) >= 2]


def _split_sentences(text: str) -> list[str]:
    """把分段文本切成句子（保留标点；子串来自原文，满足"逐字"可追溯要求）。"""
    parts = re.split(r"(?<=[。！？!?；;])", text)
    return [p.strip() for p in parts if p.strip()]


class JiebaEngine(BaseExtractionEngine):
    """基于 jieba 的实体 / 关系抽取引擎（可插拔，注册名 `jieba`）。"""

    name = "jieba"

    # 可调参数（在 stats 中自报，便于撰写《核心算法说明》前后对比）
    MIN_ENTITY_FREQ = 1        # 实体在文档内最少出现次数（单文档上传默认 1，避免图谱过于稀疏）
    MIN_NAME_LEN = 2           # 实体名最少字符数（过滤单字噪声）
    SENTENCE_MIN_ENTITIES = 2  # 一个句子内至少几个实体才考虑产出关系

    def extract(self, document_id: int, segments: list[SegmentInfo]) -> ExtractionResult:
        user_dict = _load_user_dict()
        _ensure_user_dict(user_dict)

        # ① 逐段分词 → 候选实体名（含频次、首次词性）
        freq: Counter = Counter()
        first_flag: dict[str, str] = {}
        token_count = 0

        for seg in segments:
            if seg.is_noise:
                continue
            items: list[tuple[str, str]] = []
            for word, flag in pseg.cut(seg.text):
                token_count += 1
                if flag not in _POS_TYPE:
                    continue
                if len(word) < self.MIN_NAME_LEN or word in _STOPWORDS:
                    continue
                items.append((word, flag))
            for name, flag in _compound_merge(items):
                freq[name] += 1
                first_flag.setdefault(name, flag)

        # ② 过滤：频次下界 + 子串冗余消解（A 是 B 的子串且不更常见则丢弃 A）
        total_candidates = len(freq)
        names = [w for w, c in freq.items() if c >= self.MIN_ENTITY_FREQ]
        names = [
            w for w in names
            if not any(w != b and w in b and freq[w] <= freq[b] for b in names)
        ]

        entities = [
            ExtractedEntity(
                name=w,
                type_name=_infer_entity_type(w, first_flag.get(w, "n")),
                frequency=freq[w],
            )
            for w in names
        ]
        entity_names = {e.name for e in entities}

        # ④ 关系抽取：动词锚点（句法模式）+ 同句共现补全；证据句逐字取自分段
        relations: list[ExtractedRelation] = []
        seen: set[tuple[int, str, str, str]] = set()

        for seg in segments:
            if seg.is_noise:
                continue
            for sentence in _split_sentences(seg.text):
                present = [n for n in entity_names if n in sentence]
                if len(present) < self.SENTENCE_MIN_ENTITIES:
                    continue
                present.sort(key=lambda n: sentence.index(n))
                for i in range(len(present)):
                    for j in range(i + 1, len(present)):
                        head, tail = present[i], present[j]
                        rtype = self._match_relation_type(sentence, head, tail)
                        key = (seg.id, head, tail, rtype)
                        if key in seen:
                            continue
                        seen.add(key)
                        relations.append(
                            ExtractedRelation(
                                head=head, tail=tail, relation_type_name=rtype,
                                sentence=sentence, segment_id=seg.id, weight=1.0,
                            )
                        )

        params = {
            "min_entity_freq": self.MIN_ENTITY_FREQ,
            "min_name_len": self.MIN_NAME_LEN,
            "sentence_min_entities": self.SENTENCE_MIN_ENTITIES,
            "compound_merge": "dict_only",
            "user_dict_size": len(user_dict),
        }
        stats = {
            "engine": self.name,
            "document_id": document_id,
            "segment_count": len(segments),
            "token_count": token_count,
            "candidate_entities": total_candidates,
            "entities": len(entities),
            "relations": len(relations),
            "params": params,
        }
        logger.info(
            "jieba 引擎：文档 %s -> 实体 %d，关系 %d（候选 %d，用户词典 %d）",
            document_id, len(entities), len(relations), total_candidates, len(user_dict),
        )
        return ExtractionResult(entities=entities, relations=relations, stats=stats)

    @staticmethod
    def _match_relation_type(sentence: str, head: str, tail: str) -> str:
        """在句中找到 head 与 tail 之间的动词锚点，据此判定关系类型；无命中返回「相关」。"""
        hi, ti = sentence.index(head), sentence.index(tail)
        lo, hi_pos = (hi, ti) if hi < ti else (ti, hi)
        # 动词必须出现在两个实体之间
        for verbs, rtype in _PATTERNS:
            for verb in verbs:
                vi = sentence.find(verb)
                if lo < vi < hi_pos:
                    return rtype
        # 无锚点则退化为同句共现（相关）
        return REL_RELATED
