"""本体管理模块：实体/关系类型（P0 只读——图谱图例与节点着色数据，GRA-03）。

类型 CRUD 属 P1，本期不做；默认类型由启动种子写入（core/seed.py）。
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.database import get_db
from app.models import EntityType, RelationType, User
from app.schemas.ontology import EntityTypesOut, RelationTypesOut

router = APIRouter()


@router.get("/entity-types", response_model=EntityTypesOut, summary="实体类型列表（图例数据）")
def list_entity_types(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    types = db.scalars(select(EntityType).order_by(EntityType.id)).all()
    return EntityTypesOut(items=types)


@router.get("/relation-types", response_model=RelationTypesOut, summary="关系类型列表")
def list_relation_types(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    types = db.scalars(select(RelationType).order_by(RelationType.id)).all()
    return RelationTypesOut(items=types)
