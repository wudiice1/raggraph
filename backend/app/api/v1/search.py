"""知识检索模块：全文检索（文档/分段，命中高亮）+ 实体检索。"""
import html

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.database import get_db
from app.models import Document, Entity, EntityType, Evidence, Relation, Segment, User
from app.schemas.common import Page
from app.schemas.search import EntityHitOut, FulltextHitOut

router = APIRouter()

_SNIPPET_LEN = 240  # 摘要窗口（字符）


def _escape_like(value: str) -> str:
    """转义 LIKE 通配符，配合 ESCAPE '\\' 使用（防 % _ 被解释为通配符）。"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _make_snippet(text: str, q: str) -> tuple[str, bool]:
    """服务端生成高亮摘要：先 HTML 转义再包 <mark>，杜绝注入；未命中返回开头无高亮摘要。"""
    escaped = html.escape(text)
    needle = html.escape(q)
    pos = escaped.casefold().find(needle.casefold())  # ASCII 大小写不敏感
    if pos == -1:
        pos = escaped.find(needle)
    if pos == -1:
        # 文件名命中的段：无高亮，返回开头摘要
        return (escaped[:_SNIPPET_LEN] + ("…" if len(escaped) > _SNIPPET_LEN else "")), False

    start = max(0, pos - _SNIPPET_LEN // 2)
    end = min(len(escaped), start + _SNIPPET_LEN)
    snippet = ("…" if start > 0 else "") + escaped[start:end] + ("…" if end < len(escaped) else "")

    rel = snippet.casefold().find(needle.casefold())
    if rel == -1:
        rel = snippet.find(needle)
    if rel != -1:
        snippet = (
            snippet[:rel] + "<mark>" + snippet[rel : rel + len(needle)] + "</mark>" + snippet[rel + len(needle) :]
        )
    return snippet, True


@router.get("/fulltext", response_model=Page[FulltextHitOut], summary="全文检索")
def search_fulltext(
    q: str = Query(..., min_length=1, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # LIKE 而非 FTS5：SQLite FTS5 默认 unicode61 分词器不切分中文，需编译 jieba tokenizer，
    # 违背"零配置部署"；毕设数据规模（万级分段）下 LIKE 足够（验收：列表接口 ≤1s）。
    pattern = f"%{_escape_like(q)}%"
    stmt = (
        select(Segment, Document.filename)
        .join(Document, Segment.document_id == Document.id)
        .where(
            Document.user_id == current_user.id,
            Segment.is_noise.is_(False),  # 噪音段（页码/页眉）不进检索
            or_(
                Segment.clean_text.like(pattern, escape="\\"),
                Document.filename.like(pattern, escape="\\"),
            ),
        )
        .order_by(Segment.id.desc())
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()

    items = []
    for seg, filename in rows:
        snippet, matched = _make_snippet(seg.clean_text, q)
        items.append(
            FulltextHitOut(
                document_id=seg.document_id,
                document_filename=filename,
                segment_id=seg.id,
                seq=seg.seq,
                snippet=snippet,
                matched=matched,
            )
        )
    return Page(total=total, page=page, page_size=page_size, items=items)


@router.get("/entities", response_model=Page[EntityHitOut], summary="实体检索")
def search_entities(
    q: str = Query(..., min_length=1, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pattern = f"%{_escape_like(q)}%"
    stmt = (
        select(Entity, EntityType)
        .join(EntityType, Entity.type_id == EntityType.id)
        .where(Entity.user_id == current_user.id, Entity.name.like(pattern, escape="\\"))
        .order_by(Entity.frequency.desc(), Entity.id.desc())
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()

    items = []
    for ent, et in rows:
        relation_count = (
            db.scalar(
                select(func.count())
                .select_from(Relation)
                .where(or_(Relation.head_id == ent.id, Relation.tail_id == ent.id))
            )
            or 0
        )
        document_count = (
            db.scalar(
                select(func.count(func.distinct(Evidence.document_id)))
                .select_from(Evidence)
                .join(Relation, Evidence.relation_id == Relation.id)
                .where(or_(Relation.head_id == ent.id, Relation.tail_id == ent.id))
            )
            or 0
        )
        items.append(
            EntityHitOut(
                id=ent.id,
                name=ent.name,
                type={"id": et.id, "name": et.name, "color": et.color},
                frequency=ent.frequency,
                relation_count=relation_count,
                document_count=document_count,
            )
        )
    return Page(total=total, page=page, page_size=page_size, items=items)
