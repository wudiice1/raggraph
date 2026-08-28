"""知识检索模块响应模型。"""
from typing import Any

from pydantic import BaseModel


class FulltextHitOut(BaseModel):
    document_id: int
    document_filename: str
    segment_id: int
    seq: int
    snippet: str  # 服务端已 HTML 转义 + <mark> 高亮，前端可 v-html 渲染
    matched: bool  # True = 正文命中；False = 仅文件名命中（无高亮）


class EntityHitOut(BaseModel):
    id: int
    name: str
    type: dict[str, Any]  # {id, name, color}
    frequency: int
    relation_count: int
    document_count: int
