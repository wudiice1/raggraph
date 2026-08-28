"""文档模块测试：四格式上传 / 校验 / 解析流水线 / 重解析 / 归属隔离。"""
import io
import uuid

import pymupdf
import pytest
from docx import Document as DocxDocument
from sqlalchemy import select, update

from app.config import settings
from app.database import SessionLocal
from app.models import Document, Entity, Evidence, Relation, Segment
from app.models.document import STATUS_PARSING
from app.services.extraction import ENGINE_REGISTRY
from app.services.extraction.base import BaseExtractionEngine
from app.services.pipeline import run_pipeline

from tests.conftest import (
    TEXT_SAMPLE,
    auth_headers,
    create_document_direct,
    get_user,
    register_and_login,
    upload_doc,
    wait_status,
)


def _make_pdf_bytes(text: str) -> bytes:
    """用 PyMuPDF 生成一页 PDF（英文文本，内置字体不支持中文渲染）。"""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), text)
    return doc.tobytes()


def _make_docx_bytes(text: str) -> bytes:
    buf = io.BytesIO()
    d = DocxDocument()
    d.add_paragraph(text)
    d.save(buf)
    return buf.getvalue()


# ---- 上传与格式 ----


@pytest.mark.parametrize(
    "filename,builder",
    [
        ("测试文档.txt", lambda: TEXT_SAMPLE.encode("utf-8")),
        ("笔记.md", lambda: ("# 知识库笔记\n\n" + TEXT_SAMPLE).encode("utf-8")),
        ("report.pdf", lambda: _make_pdf_bytes("Knowledge base system for entity extraction.")),
        ("论文.docx", lambda: _make_docx_bytes(TEXT_SAMPLE)),
    ],
)
def test_upload_all_formats_and_parse_completed(client, filename, builder):
    token = register_and_login(client)
    r = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers(token),
        files={"file": (filename, builder(), "application/octet-stream")},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["file_type"] == filename.rsplit(".", 1)[-1]
    assert data["status"] == "parsing"

    detail = wait_status(client, token, data["id"], "completed")
    assert detail["parse_error"] is None
    assert detail["stats"]["segments"] > 0
    # Stub 引擎：实体/关系为 0，但状态流转正常
    assert detail["stats"]["entities"] == 0
    assert detail["stats"]["relations"] == 0


def test_upload_rejects_bad_extension(client):
    token = register_and_login(client)
    r = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers(token),
        files={"file": ("evil.exe", b"MZ...", "application/octet-stream")},
    )
    assert r.status_code == 400
    assert "不支持的文件类型" in r.json()["detail"]


def test_upload_rejects_oversize_413(client):
    token = register_and_login(client)
    big = b"x" * (21 * 1024 * 1024)  # 21MB > 20MB 限制
    r = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers(token),
        files={"file": ("big.txt", big, "text/plain")},
    )
    assert r.status_code == 413


def test_upload_sanitizes_path_traversal_filename(client, db):
    token = register_and_login(client)
    r = upload_doc(client, token, filename="../../etc/passwd.txt")
    assert r.status_code == 201, r.text
    assert r.json()["filename"] == "passwd.txt"  # 路径成分已清洗

    user = get_user(db, "alice")
    doc = db.get(Document, r.json()["id"])
    stored = (settings.upload_dir / doc.stored_name).resolve()
    assert stored.is_file()
    assert str(stored).startswith(str(settings.upload_dir.resolve()))  # 文件落在 uploads 内


def test_upload_empty_file_fails_with_clear_error(client):
    token = register_and_login(client)
    r = upload_doc(client, token, content=b"")
    assert r.status_code == 201
    detail = wait_status(client, token, r.json()["id"], "failed")
    assert "未能从文档中提取到文本" in detail["parse_error"]


def test_upload_requires_auth(client):
    r = client.post(
        "/api/v1/documents/upload",
        files={"file": ("x.txt", TEXT_SAMPLE.encode("utf-8"), "text/plain")},
    )
    assert r.status_code == 401


# ---- 解析流水线（同步确定性路径） ----


def test_pipeline_sync_completes(client, db):
    token = register_and_login(client)
    user = get_user(db, "alice")
    doc = create_document_direct(db, user, TEXT_SAMPLE, status=STATUS_PARSING)

    run_pipeline(doc.id)

    db.expire_all()
    doc = db.get(Document, doc.id)
    assert doc.status == "completed"
    assert doc.parse_error is None
    segs = db.scalars(select(Segment).where(Segment.document_id == doc.id)).all()
    assert len(segs) >= 2
    assert [s.seq for s in segs] == sorted(s.seq for s in segs)

    detail = client.get(f"/api/v1/documents/{doc.id}", headers=auth_headers(token)).json()
    assert detail["stats"]["segments"] == len(segs)


def test_engine_failure_marks_document_failed(client, db, monkeypatch):
    class FailingEngine(BaseExtractionEngine):
        name = "failing"

        def extract(self, document_id, segments):
            raise RuntimeError("模拟引擎崩溃")

    monkeypatch.setitem(ENGINE_REGISTRY, "failing", FailingEngine)
    monkeypatch.setattr(settings, "extraction_engine", "failing")

    token = register_and_login(client)
    user = get_user(db, "alice")
    doc = create_document_direct(db, user, TEXT_SAMPLE, status=STATUS_PARSING)

    run_pipeline(doc.id)

    db.expire_all()
    doc = db.get(Document, doc.id)
    assert doc.status == "failed"
    assert "模拟引擎崩溃" in doc.parse_error


def test_reparse_cleans_old_data(client, db):
    """重解析：旧分段/证据句/零证据关系/孤儿实体全部清理（防级联误删他人数据）。"""
    token = register_and_login(client)
    user = get_user(db, "alice")
    doc = create_document_direct(db, user, TEXT_SAMPLE, status=STATUS_PARSING)
    run_pipeline(doc.id)
    db.expire_all()
    doc = db.get(Document, doc.id)
    assert doc.status == "completed"

    # 模拟上一轮引擎写入：实体对 + 关系 + 证据句（挂在旧分段上）
    from tests.conftest import seed_graph_data

    seeded = seed_graph_data(db, user)  # 提供类型
    old_seg_id = db.scalar(select(Segment.id).where(Segment.document_id == doc.id).order_by(Segment.id))
    ent_a = Entity(user_id=user.id, name="重解析实体A", type_id=seeded["zhangsan"].type_id, frequency=1, document_id=doc.id)
    ent_b = Entity(user_id=user.id, name="重解析实体B", type_id=seeded["zhangsan"].type_id, frequency=1, document_id=doc.id)
    db.add_all([ent_a, ent_b])
    db.flush()
    rel = Relation(
        head_id=ent_a.id, tail_id=ent_b.id,
        relation_type_id=seeded["rel1"].relation_type_id, document_id=doc.id, weight=1.0,
    )
    db.add(rel)
    db.flush()
    db.add(Evidence(relation_id=rel.id, segment_id=old_seg_id, document_id=doc.id, sentence="旧证据句"))
    db.commit()
    rel_id, ent_a_id = rel.id, ent_a.id

    # 触发重解析
    db.execute(update(Document).where(Document.id == doc.id).values(status=STATUS_PARSING, parse_error=None))
    db.commit()
    run_pipeline(doc.id)
    db.expire_all()

    doc = db.get(Document, doc.id)
    assert doc.status == "completed"
    assert db.scalar(select(Segment.id).where(Segment.id == old_seg_id)) is None  # 旧分段已删
    assert db.scalar(select(Evidence.id).where(Evidence.sentence == "旧证据句")) is None  # 旧证据句级联删除
    assert db.get(Relation, rel_id) is None  # 零证据关系已删
    assert db.get(Entity, ent_a_id) is None  # 孤儿实体已删
    # seed_graph_data 的数据（属于另一文档）不受影响
    assert db.get(Relation, seeded["rel1"].id) is not None
    assert db.get(Entity, seeded["zhangsan"].id) is not None


# ---- 触发/重新解析接口 ----


def test_parse_trigger_reparse_failed(client, db):
    token = register_and_login(client)
    user = get_user(db, "alice")
    doc = create_document_direct(db, user, TEXT_SAMPLE, status="failed")
    db.execute(update(Document).where(Document.id == doc.id).values(parse_error="之前失败"))
    db.commit()

    r = client.post(f"/api/v1/documents/{doc.id}/parse", headers=auth_headers(token))
    assert r.status_code == 202
    assert r.json()["status"] == "parsing"

    detail = wait_status(client, token, doc.id, "completed")
    assert detail["parse_error"] is None


def test_parse_while_parsing_409(client, db):
    token = register_and_login(client)
    user = get_user(db, "alice")
    doc = create_document_direct(db, user, TEXT_SAMPLE, status=STATUS_PARSING)

    r = client.post(f"/api/v1/documents/{doc.id}/parse", headers=auth_headers(token))
    assert r.status_code == 409
    assert "正在解析" in r.json()["detail"]


# ---- 列表与归属隔离 ----


def test_list_documents_pagination_and_filter(client, db):
    token = register_and_login(client)
    for i in range(3):
        r = upload_doc(client, token, filename=f"文档{i}.txt")
        assert r.status_code == 201
        wait_status(client, token, r.json()["id"], "completed")

    r = client.get("/api/v1/documents?page=1&page_size=2", headers=auth_headers(token))
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert all("stats" in item for item in data["items"])

    r = client.get("/api/v1/documents?status=completed", headers=auth_headers(token))
    assert r.json()["total"] == 3
    r = client.get("/api/v1/documents?status=failed", headers=auth_headers(token))
    assert r.json()["total"] == 0


def test_other_user_cannot_access_document(client, db):
    alice_token = register_and_login(client, username="alice", email="alice@test.com")
    r = upload_doc(client, alice_token)
    doc_id = r.json()["id"]
    wait_status(client, alice_token, doc_id, "completed")

    bob_token = register_and_login(client, username="bob123", email="bob@test.com")
    # 越权访问一律 404（不暴露资源存在性）
    assert client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers(bob_token)).status_code == 404
    assert client.post(f"/api/v1/documents/{doc_id}/parse", headers=auth_headers(bob_token)).status_code == 404
    # bob 的列表里也看不到
    r = client.get("/api/v1/documents", headers=auth_headers(bob_token))
    assert r.json()["total"] == 0
