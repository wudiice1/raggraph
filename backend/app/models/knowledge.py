"""知识层 5 张表：实体类型、关系类型、实体（节点）、关系（边）、证据句。

对 PRD §8 的两处修正（多用户系统必要）：
1. entities 增加 user_id，唯一约束 (user_id, name) —— 跨文档同名合并限定在同一用户内，
   防止 A 用户文档的证据句出现在 B 用户的图谱中；
2. entities/relations 增加 document_id（首个来源文档，PRD ER 要点本身写明
   "documents 1-N entities/relations（来源）"），用于重解析清理与将来级联删除。
"""
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EntityType(Base):
    """实体类型（本体，P0 只读）：节点着色与图例数据来源。"""

    __tablename__ = "entity_types"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    color: Mapped[str] = mapped_column(String(16), nullable=False, default="#5470c6", server_default="#5470c6")
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class RelationType(Base):
    """关系类型（本体，P0 只读）。"""

    __tablename__ = "relation_types"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class Entity(Base):
    """实体（图谱节点）：同名实体跨文档合并为同一节点（合并键 = user_id + name）。"""

    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_entities_user_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    type_id: Mapped[int] = mapped_column(
        ForeignKey("entity_types.id", ondelete="RESTRICT"), nullable=False
    )
    frequency: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")  # 累计频次
    attributes: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)  # 附加属性
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )  # 首个来源文档（重解析清理/级联删除用）
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class Relation(Base):
    """关系（图谱边）：相同实体对 + 关系类型全局去重，重复来源只累加证据句。"""

    __tablename__ = "relations"
    __table_args__ = (
        UniqueConstraint("head_id", "tail_id", "relation_type_id", name="uq_relations_head_tail_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    head_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tail_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relation_type_id: Mapped[int] = mapped_column(
        ForeignKey("relation_types.id", ondelete="RESTRICT"), nullable=False
    )
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )  # 首个建立该关系的文档
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1.0")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class Evidence(Base):
    """证据句：每条关系至少关联一条证据句与来源文档（可追溯性，EXT-06）。"""

    __tablename__ = "evidences"
    __table_args__ = (
        UniqueConstraint("relation_id", "segment_id", "sentence", name="uq_evidences_rel_seg_sentence"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    relation_id: Mapped[int] = mapped_column(
        ForeignKey("relations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    segment_id: Mapped[int] = mapped_column(
        ForeignKey("segments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sentence: Mapped[str] = mapped_column(Text, nullable=False)  # 原文证据句
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
