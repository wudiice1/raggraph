"""本体（实体/关系类型）响应模型。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EntityTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str
    description: str | None
    created_at: datetime


class RelationTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    created_at: datetime


class EntityTypesOut(BaseModel):
    items: list[EntityTypeOut]


class RelationTypesOut(BaseModel):
    items: list[RelationTypeOut]
