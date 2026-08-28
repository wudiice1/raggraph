"""pytest 全局配置：环境隔离（临时库/上传目录）+ 测试工具函数。

关键设计：环境变量必须在导入 app 之前设置（config.Settings 在导入时读取），
因此临时目录在模块顶层创建。
"""
import os
import tempfile
import time
import uuid
from pathlib import Path

# ---- 必须在导入 app 之前设置环境变量 ----
_base = Path(os.environ.get("CLAUDE_JOB_DIR", tempfile.gettempdir()))
_TEST_DIR = Path(tempfile.mkdtemp(prefix="knowledge_backend_test_", dir=_base))
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DIR / 'test.db'}"
os.environ["UPLOAD_DIR"] = str(_TEST_DIR / "uploads")
os.environ["EXTRACTION_ENGINE"] = "stub"
os.environ["SECRET_KEY"] = "test-secret-key-0123456789abcdef-0123456789abcdef"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Document,
    Entity,
    EntityType,
    Evidence,
    Relation,
    RelationType,
    Segment,
    User,
)
from app.services.pipeline import run_pipeline  # noqa: E402

TEXT_SAMPLE = (
    "认知知识库系统是一个面向个人的知识管理工具，支持文档上传与自动解析。\n\n"
    "系统能够自动抽取文档中的实体和关系，构建可视化的知识图谱。\n\n"
    "用户可以通过关键词搜索快速定位相关知识内容。\n\n"
    "知识图谱通过力导向布局展示实体之间的关联关系。\n\n"
    "每一条关系都保留证据句与来源文档，知识可信可查。"
)


@pytest.fixture(autouse=True)
def _clean_db():
    """每个测试从空库开始（SQLite 8 张表重建极快），保证测试相互隔离。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    """TestClient 上下文触发 lifespan：create_all + 种子（admin/类型）+ 崩溃恢复。"""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
        session.rollback()
    finally:
        session.close()


# ---- 工具函数 ----


def register_and_login(
    client: TestClient, username: str = "alice", email: str = "alice@test.com", password: str = "pass123456"
) -> str:
    """注册并登录，返回 access_token。"""
    r = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def upload_doc(
    client: TestClient, token: str, filename: str = "测试文档.txt", content: bytes | str | None = None
):
    """上传文档（默认文本内容为 TEXT_SAMPLE），返回响应。"""
    data = (content if isinstance(content, bytes) else (content or TEXT_SAMPLE).encode("utf-8"))
    return client.post(
        "/api/v1/documents/upload",
        headers=auth_headers(token),
        files={"file": (filename, data, "application/octet-stream")},
    )


def wait_status(client: TestClient, token: str, doc_id: int, target: str, timeout: float = 15.0) -> dict:
    """轮询文档状态直到达到目标（走真实后台线程路径）。"""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        r = client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers(token))
        assert r.status_code == 200
        last = r.json()
        if last["status"] == target:
            return last
        time.sleep(0.1)
    pytest.fail(f"等待状态 {target} 超时，最后状态: {last}")


def get_user(db, username: str) -> User:
    return db.scalar(select(User).where(User.username == username))


def create_document_direct(db, user: User, content: str, status: str = "parsing", file_type: str = "txt") -> Document:
    """绕过上传接口直接建文档（同步测试流水线用，避免与后台线程竞争）。"""
    user_dir = settings.upload_dir / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid.uuid4().hex}.{file_type}"
    (user_dir / stored_filename).write_bytes(content.encode("utf-8"))
    doc = Document(
        user_id=user.id,
        filename=f"直接创建.{file_type}",
        stored_name=f"{user.id}/{stored_filename}",
        file_type=file_type,
        size=len(content.encode("utf-8")),
        status=status,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def run_pipeline_sync(db, doc_id: int):
    """同步执行解析流水线（绕过线程，保证确定性）；调用前需确保文档状态为 parsing。"""
    run_pipeline(doc_id)
    db.expire_all()


def seed_graph_data(db, user: User) -> dict:
    """直插图谱测试数据：1 文档 + 1 分段 + 3 实体 + 2 关系 + 1 证据句。"""
    from app.core.seed import seed_database

    seed_database(db)  # 幂等：确保实体/关系类型存在

    types = {t.name: t for t in db.scalars(select(EntityType)).all()}
    rtypes = {t.name: t for t in db.scalars(select(RelationType)).all()}

    doc = Document(
        user_id=user.id,
        filename="来源文档.txt",
        stored_name=f"{user.id}/seed.txt",
        file_type="txt",
        size=10,
        status="completed",
    )
    db.add(doc)
    db.flush()
    seg = Segment(
        document_id=doc.id, seq=1, raw_text="张三毕业于北京大学，研究知识图谱方向。",
        clean_text="张三毕业于北京大学，研究知识图谱方向。", is_noise=False,
    )
    db.add(seg)
    db.flush()

    zhangsan = Entity(user_id=user.id, name="张三", type_id=types["人物"].id, frequency=5, document_id=doc.id)
    pku = Entity(user_id=user.id, name="北京大学", type_id=types["组织"].id, frequency=3, document_id=doc.id)
    concept = Entity(user_id=user.id, name="知识图谱", type_id=types["概念"].id, frequency=2, document_id=doc.id)
    db.add_all([zhangsan, pku, concept])
    db.flush()

    rel1 = Relation(
        head_id=zhangsan.id, tail_id=pku.id, relation_type_id=rtypes["属于"].id, document_id=doc.id, weight=1.0
    )
    rel2 = Relation(
        head_id=pku.id, tail_id=concept.id, relation_type_id=rtypes["相关"].id, document_id=doc.id, weight=1.0
    )
    db.add_all([rel1, rel2])
    db.flush()
    db.add(Evidence(relation_id=rel1.id, segment_id=seg.id, document_id=doc.id, sentence="张三毕业于北京大学，研究知识图谱方向。"))
    db.commit()
    return {
        "doc": doc,
        "seg": seg,
        "zhangsan": zhangsan,
        "pku": pku,
        "concept": concept,
        "rel1": rel1,
        "rel2": rel2,
    }
