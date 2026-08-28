"""文档解析流水线：状态机 + 后台线程 + 重解析清理。

状态机：pending(待解析) → parsing(解析中) → completed(已完成) / failed(失败)

线程模型：自管 daemon 线程（不用 FastAPI BackgroundTasks——CPU 密集的解析任务
会阻塞请求线程）。per-doc Lock + API 层状态守卫防并发解析；进程被杀后遗留的
parsing 状态由启动种子重置为 pending（崩溃恢复）。仅支持单进程单 worker 部署。

引擎协作：抽取引擎是纯函数（见 extraction/base.py 契约），写库唯一入口是本模块
调用的 apply_extraction_result，单一事务由本模块掌控。
"""
import logging
import threading

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Document, Entity, Evidence, Relation, Segment
from app.models.document import STATUS_COMPLETED, STATUS_FAILED, STATUS_PARSING
from app.services import storage
from app.services.extraction import get_engine
from app.services.extraction.base import SegmentInfo
from app.services.extraction.segment import clean_text, split_segments
from app.services.extraction.writers import apply_extraction_result
from app.services.parser import parse_document

logger = logging.getLogger(__name__)

_locks: dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()


def _get_lock(document_id: int) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(document_id, threading.Lock())


def start_parse(document_id: int) -> str:
    """把文档置为 parsing 并启动后台解析线程（状态切换在请求线程内同步完成）。"""
    db = SessionLocal()
    try:
        doc = db.get(Document, document_id)
        if doc is None:
            return "missing"
        if doc.status == STATUS_PARSING:
            return STATUS_PARSING  # 已在解析中
        doc.status = STATUS_PARSING
        doc.parse_error = None
        db.commit()
    finally:
        db.close()

    threading.Thread(
        target=run_pipeline, args=(document_id,), daemon=True, name=f"parse-{document_id}"
    ).start()
    return STATUS_PARSING


def run_pipeline(document_id: int) -> None:
    """解析单个文档（后台线程入口；测试可直接同步调用保证确定性）。"""
    lock = _get_lock(document_id)
    if not lock.acquire(blocking=False):
        logger.info("文档 %s 已有解析线程在运行，跳过", document_id)
        return

    db = SessionLocal()
    try:
        doc = db.get(Document, document_id)
        if doc is None or doc.status != STATUS_PARSING:
            return  # 状态已被外部改动（如崩溃重置），不再处理

        # ① 文件 → 全文
        path = storage.resolve_path(doc.user_id, doc.stored_name)
        raw_text = parse_document(path, doc.file_type)
        if not raw_text.strip():
            raise ValueError("未能从文档中提取到文本（可能为扫描版 PDF 或纯图片文件）")

        # ② 重解析清理（首次解析时无残留数据，天然幂等）
        _cleanup_previous(db, doc)

        # ③ 清洗 + 分段入库（flush 后获得 SegmentInfo 供引擎使用）
        cleaned = clean_text(raw_text)
        segments: list[Segment] = []
        for seq, (seg_text, is_noise) in enumerate(split_segments(cleaned), start=1):
            seg = Segment(
                document_id=doc.id, seq=seq, raw_text=seg_text, clean_text=seg_text, is_noise=is_noise
            )
            db.add(seg)
            segments.append(seg)
        db.flush()
        seg_infos = [SegmentInfo(id=s.id, seq=s.seq, text=s.clean_text, is_noise=s.is_noise) for s in segments]

        # ④ 抽取（引擎纯函数，替换点见 extraction/base.py）
        engine = get_engine(settings.extraction_engine)
        result = engine.extract(doc.id, seg_infos)

        # ⑤ 落库（实体合并/关系去重/证据句，单事务）
        stats = apply_extraction_result(db, doc.id, result)

        doc.status = STATUS_COMPLETED
        doc.parse_error = None
        db.commit()
        logger.info("文档 %s 解析完成：分段 %d，%s", doc.id, len(segments), stats)
    except Exception as exc:  # noqa: BLE001 —— 失败必须可见，供前端提示与手动重解析
        db.rollback()
        try:
            doc = db.get(Document, document_id)
            if doc is not None:
                doc.status = STATUS_FAILED
                doc.parse_error = str(exc)[:500]
                db.commit()
        except Exception:
            db.rollback()
        logger.exception("文档 %s 解析失败", document_id)
    finally:
        lock.release()
        db.close()


def _cleanup_previous(db: Session, doc: Document) -> None:
    """删除本文档上一轮解析的产物。

    顺序防级联误删（关键）：只按 document_id 删除"本文档自己的"分段与证据句，
    绝不能直接按 document_id 删关系/实体——合并关系可能同时挂着其他文档的证据句，
    直接删会级联误删他人数据。正确顺序：
    ① 删本文档分段 → 数据库级联删除其证据句；
    ② 删证据句清零的关系；
    ③ 删不再被任何关系引用的孤儿实体（本文档为首个来源且已无边的）。
    """
    db.execute(delete(Segment).where(Segment.document_id == doc.id))
    db.flush()  # 触发 SQLite 外键级联删除 evidences

    zero_evidence_rel_ids = [
        rid
        for (rid,) in db.execute(
            select(Relation.id).where(Relation.id.not_in(select(Evidence.relation_id)))
        ).all()
    ]
    if zero_evidence_rel_ids:
        db.execute(delete(Relation).where(Relation.id.in_(zero_evidence_rel_ids)))
        db.flush()

    referenced_ids = select(Relation.head_id).union(select(Relation.tail_id))
    orphan_entity_ids = [
        eid
        for (eid,) in db.execute(
            select(Entity.id).where(
                Entity.document_id == doc.id, Entity.id.not_in(referenced_ids)
            )
        ).all()
    ]
    if orphan_entity_ids:
        db.execute(delete(Entity).where(Entity.id.in_(orphan_entity_ids)))
        db.flush()
