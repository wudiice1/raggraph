"""标准化建库初始化脚本（结题交付物 4：数据库初始文件/建表脚本，后端一负责）。

用法（在 backend/ 目录下）：
    .venv/bin/python scripts/init_db.py

完成：建全部表（同 Alembic 初始迁移 schema）+ 种子数据
（默认实体/关系类型 + 内置 admin 账号 + 解析状态崩溃恢复）。
与 `python run.py` 启动时的自动初始化完全等价（同一份 metadata 与 seed 逻辑）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: E402,F401 —— 保证 Base.metadata 完整
from app.config import settings  # noqa: E402
from app.core.seed import seed_database  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402


def main() -> None:
    Base.metadata.create_all(bind=engine)  # 表已存在时零操作
    with SessionLocal() as db:
        seed_database(db)

    tables = sorted(Base.metadata.tables)
    print("数据库初始化完成 ✓")
    print(f"  库文件: {settings.database_url}")
    print(f"  数据表 ({len(tables)}): {', '.join(tables)}")
    print(f"  内置管理员: {settings.default_admin_username} / {settings.default_admin_password}（请尽快修改）")


if __name__ == "__main__":
    main()
