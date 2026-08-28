"""文本分段表：解析流水线的中间产物，也是抽取引擎的输入。"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = (
        UniqueConstraint("document_id", "seq", name="uq_segments_document_seq"),  # 防重解析重复插入
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)  # 文档内序号
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    clean_text: Mapped[str] = mapped_column(Text, nullable=False)  # 清洗后文本（搜索目标字段）
    is_noise: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )  # 页码/页眉等噪音段标记
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
