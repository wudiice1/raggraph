"""数据库基础设施：engine / SessionLocal / Base / get_db 依赖。

SQLite 多线程要点：
- check_same_thread=False + WAL 模式，允许后台解析线程与请求线程并发读写；
- busy_timeout=5000 缓解写锁竞争；
- 每个线程必须使用独立的 Session（get_db 与解析流水线各自建 session），
  ORM 对象绝不跨线程共享。
"""
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")  # 级联删除依赖外键开关
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI 依赖：每请求一个独立 session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
