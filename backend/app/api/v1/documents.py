"""文档管理模块：上传 / 列表 / 详情（轮询用）/ 触发解析。"""
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Document, Entity, Relation, Segment, User
from app.schemas.common import Page
from app.schemas.document import DocumentOut, DocumentStats, ParseTriggerOut
from app.services import storage
from app.services.pipeline import start_parse

router = APIRouter()


def _doc_stats(db: Session, document_id: int) -> DocumentStats:
    """解析结果概览：分段数 / 本文档为首来源的实体数 / 本文档建立的关系数。"""
    return DocumentStats(
        segments=db.scalar(
            select(func.count()).select_from(Segment).where(Segment.document_id == document_id)
        )
        or 0,
        entities=db.scalar(
            select(func.count()).select_from(Entity).where(Entity.document_id == document_id)
        )
        or 0,
        relations=db.scalar(
            select(func.count()).select_from(Relation).where(Relation.document_id == document_id)
        )
        or 0,
    )


def _to_out(db: Session, doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        size=doc.size,
        status=doc.status,
        parse_error=doc.parse_error,
        created_at=doc.created_at,
        stats=_doc_stats(db, doc.id),
    )


def _get_owned_doc(db: Session, document_id: int, user: User) -> Document:
    """归属校验：不是自己的文档一律 404（不暴露资源存在性）。"""
    doc = db.get(Document, document_id)
    if doc is None or doc.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文档不存在")
    return doc


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED, summary="上传文档")
def upload_document(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ① 文件名清洗 + 扩展名白名单（大小写归一）
    filename = Path(file.filename or "").name  # 防路径穿越
    if not filename or "." not in filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="文件名缺少扩展名")
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in settings.allowed_file_types:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型 .{ext}（支持: {', '.join(sorted(settings.allowed_file_types))}）",
        )

    # ② Content-Length 前置预检（multipart 有少量边界开销，留 64KB 余量；
    #    权威校验是 storage 的分块累计限长）
    max_bytes = settings.max_upload_mb * 1024 * 1024
    content_length = request.headers.get("content-length", "")
    if content_length.isdigit() and int(content_length) > max_bytes + 64 * 1024:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件超过 {settings.max_upload_mb}MB 大小限制",
        )

    # ③ 落盘（分块限长）+ 建行（pending）
    try:
        stored_name, size = storage.save_upload(current_user.id, file, ext)
    except ValueError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc))

    doc = Document(
        user_id=current_user.id,
        filename=filename,
        stored_name=stored_name,
        file_type=ext,
        size=size,
        status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # ④ 触发后台解析（start_parse 同步置 parsing 后起线程）
    start_parse(doc.id)
    doc.status = "parsing"  # 响应对象同步状态（无需再查库）
    return _to_out(db, doc)


@router.get("", response_model=Page[DocumentOut], summary="文档列表（分页/状态筛选）")
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Document).where(Document.user_id == current_user.id)
    if status_filter:
        stmt = stmt.where(Document.status == status_filter)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    docs = db.scalars(
        stmt.order_by(Document.created_at.desc(), Document.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return Page(
        total=total,
        page=page,
        page_size=page_size,
        items=[_to_out(db, d) for d in docs],
    )


@router.get("/{document_id}", response_model=DocumentOut, summary="文档详情（前端轮询解析状态）")
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _to_out(db, _get_owned_doc(db, document_id, current_user))


@router.post("/{document_id}/parse", response_model=ParseTriggerOut, status_code=status.HTTP_202_ACCEPTED, summary="触发/重新解析")
def trigger_parse(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = _get_owned_doc(db, document_id, current_user)
    if doc.status == "parsing":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="文档正在解析中，请稍候")
    start_parse(doc.id)
    return ParseTriggerOut(id=doc.id, status="parsing")
