"""文档模块响应模型。"""
from datetime import datetime

from pydantic import BaseModel


class DocumentStats(BaseModel):
    """解析结果概览计数。"""

    segments: int
    entities: int
    relations: int


class DocumentOut(BaseModel):
    id: int
    filename: str
    file_type: str
    size: int
    status: str  # pending / parsing / completed / failed
    parse_error: str | None
    created_at: datetime
    stats: DocumentStats


class ParseTriggerOut(BaseModel):
    id: int
    status: str
