"""知识检索模块测试：全文检索（高亮/通配符转义/隔离）+ 实体检索。"""
from tests.conftest import auth_headers, get_user, register_and_login, seed_graph_data


def test_fulltext_hit_with_highlight(client, db):
    token = register_and_login(client)
    user = get_user(db, "alice")
    seed_graph_data(db, user)

    r = client.get("/api/v1/search/fulltext", params={"q": "张三"}, headers=auth_headers(token))
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    hit = data["items"][0]
    assert hit["matched"] is True
    assert "<mark>张三</mark>" in hit["snippet"]
    assert hit["document_filename"] == "来源文档.txt"


def test_fulltext_matches_filename_without_highlight(client, db):
    token = register_and_login(client)
    user = get_user(db, "alice")
    seed_graph_data(db, user)

    r = client.get("/api/v1/search/fulltext", params={"q": "来源文档"}, headers=auth_headers(token))
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    hit = data["items"][0]
    assert hit["matched"] is False  # 仅文件名命中
    assert "<mark>" not in hit["snippet"]


def test_fulltext_escapes_like_wildcards(client, db):
    """% / _ 必须按字面匹配而非通配符（防全表匹配）。"""
    token = register_and_login(client)
    user = get_user(db, "alice")
    seed_graph_data(db, user)

    for q in ("%", "_", "%_%"):
        r = client.get("/api/v1/search/fulltext", params={"q": q}, headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["total"] == 0  # 数据中无字面 %/_，证明未被解释为通配符


def test_fulltext_isolated_by_user(client, db):
    alice_token = register_and_login(client, username="alice", email="alice@test.com")
    seed_graph_data(db, get_user(db, "alice"))

    bob_token = register_and_login(client, username="bob123", email="bob@test.com")
    r = client.get("/api/v1/search/fulltext", params={"q": "张三"}, headers=auth_headers(bob_token))
    assert r.json()["total"] == 0


def test_fulltext_pagination(client, db):
    token = register_and_login(client)
    user = get_user(db, "alice")
    seeded = seed_graph_data(db, user)

    # 追加两条含"知识"的分段（不同文档）
    from app.models import Document, Segment

    for i in range(2):
        doc = Document(
            user_id=user.id, filename=f"文档{i}.txt", stored_name=f"{user.id}/s{i}.txt",
            file_type="txt", size=10, status="completed",
        )
        db.add(doc)
        db.flush()
        db.add(Segment(document_id=doc.id, seq=1, raw_text="知识管理", clean_text=f"知识管理第{i}篇", is_noise=False))
    db.commit()

    r = client.get("/api/v1/search/fulltext", params={"q": "知识", "page": 1, "page_size": 2}, headers=auth_headers(token))
    data = r.json()
    assert data["total"] >= 2
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert seeded["seg"].id  # 原始分段也在命中范围内


def test_entities_search(client, db):
    token = register_and_login(client)
    user = get_user(db, "alice")
    seed_graph_data(db, user)

    r = client.get("/api/v1/search/entities", params={"q": "北京"}, headers=auth_headers(token))
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    hit = data["items"][0]
    assert hit["name"] == "北京大学"
    assert hit["type"]["name"] == "组织"
    assert hit["type"]["color"] == "#91cc75"
    assert hit["relation_count"] == 2  # 属于(张三→北大) + 相关(北大→知识图谱)
    assert hit["document_count"] == 1
    assert hit["frequency"] == 3


def test_entities_search_isolated_by_user(client, db):
    alice_token = register_and_login(client, username="alice", email="alice@test.com")
    seed_graph_data(db, get_user(db, "alice"))

    bob_token = register_and_login(client, username="bob123", email="bob@test.com")
    r = client.get("/api/v1/search/entities", params={"q": "北京"}, headers=auth_headers(bob_token))
    assert r.json()["total"] == 0
