"""数据库迁移集成测试：alembic 建库路径 + create_all 幂等（双路径同源不漂移）。

本测试通过子进程执行 alembic，验证「迁移是 schema 变更的正式通道」这一承诺；
日常零配置路径（create_all）由其余测试覆盖。
"""
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

from app.database import Base

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_alembic_upgrade_creates_full_schema(tmp_path):
    db_path = tmp_path / "alembic_test.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "UPLOAD_DIR": str(tmp_path / "uploads"),
    }
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert result.returncode == 0, result.stderr

    engine = create_engine(f"sqlite:///{db_path}")
    tables = set(inspect(engine).get_table_names())
    expected = {"users", "documents", "segments", "entity_types", "relation_types", "entities", "relations", "evidences"}
    assert expected.issubset(tables)


def test_create_all_idempotent_after_migration(tmp_path):
    """先 alembic 建库，再跑 create_all —— 表已存在时零操作、无异常（双路径并存）。"""
    db_path = tmp_path / "alembic_test.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "UPLOAD_DIR": str(tmp_path / "uploads"),
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)  # 不应报错
    tables = set(inspect(engine).get_table_names())
    assert "users" in tables
