"""汇总导出全部模型，保证 Base.metadata 完整（create_all 与 alembic autogenerate 依赖）。"""
from app.models.document import Document
from app.models.knowledge import Entity, EntityType, Evidence, Relation, RelationType
from app.models.segment import Segment
from app.models.user import User

__all__ = [
    "User",
    "Document",
    "Segment",
    "EntityType",
    "RelationType",
    "Entity",
    "Relation",
    "Evidence",
]
