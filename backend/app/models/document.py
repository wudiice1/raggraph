"""文档表：上传文件元信息与解析状态。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# 解析状态机：pending(待解析) → parsing(解析中) → completed(已完成) / failed(失败)
STATUS_PENDING = "pending"
STATUS_PARSING = "parsing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)  # 原始文件名（已清洗路径成分）
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)  # 相对存储名 uploads/<user_id>/<uuid>.<ext>
    file_type: Mapped[str] = mapped_column(String(8), nullable=False)  # pdf/docx/txt/md
    size: Mapped[int] = mapped_column(Integer, nullable=False)  # 字节
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=STATUS_PENDING, server_default=STATUS_PENDING, index=True
    )
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)  # 解析失败原因（≤500 字符）
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
