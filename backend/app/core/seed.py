"""启动种子（幂等，可重复执行）：
1. 默认实体类型 / 关系类型（图谱着色与图例数据）；
2. 内置 admin 账号（AUTH-06，默认 admin/admin123，README 提示修改）；
3. 把进程被杀遗留的 parsing 状态文档重置为 pending（崩溃恢复）。
种子数据是"数据"而非 schema，因此不写入 Alembic 迁移。
"""
import logging

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import hash_password
from app.models import Document, EntityType, RelationType, User
from app.models.document import STATUS_PARSING, STATUS_PENDING

logger = logging.getLogger(__name__)

# (名称, 颜色, 说明)
DEFAULT_ENTITY_TYPES = [
    ("人物", "#5470c6", "人名、职位头衔等人物类实体"),
    ("组织", "#91cc75", "公司、学校、机构、团队等组织实体"),
    ("地点", "#fac858", "地名、地理位置类实体"),
    ("概念", "#ee6666", "抽象概念、术语、领域名词"),
    ("技术", "#73c0de", "技术、工具、方法、协议等技术类实体"),
]

# (名称, 说明)
DEFAULT_RELATION_TYPES = [
    ("包含", "整体包含部分 / 文档包含主题"),
    ("属于", "实体隶属于另一实体"),
    ("相关", "两个实体存在关联"),
    ("引用", "引用、提及另一实体"),
]


def seed_database(db: Session) -> None:
    for name, color, desc in DEFAULT_ENTITY_TYPES:
        if db.scalar(select(EntityType).where(EntityType.name == name)) is None:
            db.add(EntityType(name=name, color=color, description=desc))

    for name, desc in DEFAULT_RELATION_TYPES:
        if db.scalar(select(RelationType).where(RelationType.name == name)) is None:
            db.add(RelationType(name=name, description=desc))

    admin = db.scalar(select(User).where(User.username == settings.default_admin_username))
    if admin is None:
        db.add(
            User(
                username=settings.default_admin_username,
                email=settings.default_admin_email,
                password_hash=hash_password(settings.default_admin_password),
                role="admin",
            )
        )
        logger.info("已创建内置管理员账号 %s（请尽快修改默认密码）", settings.default_admin_username)

    # 崩溃恢复：上次进程退出时卡在 parsing 的文档重新排队
    db.execute(
        update(Document).where(Document.status == STATUS_PARSING).values(status=STATUS_PENDING)
    )

    db.commit()
