"""知识图谱模块测试：总览点线数据 / 节点详情 / 多用户隔离。"""
from tests.conftest import auth_headers, get_user, register_and_login, seed_graph_data


def test_overview_returns_echarts_structure(client, db):
    token = register_and_login(client)
    user = get_user(db, "alice")
    seeded = seed_graph_data(db, user)

    r = client.get("/api/v1/graph/overview", headers=auth_headers(token))
    assert r.status_code == 200
    data = r.json()

    assert data["total_nodes"] == 3
    assert data["total_edges"] == 2
    assert len(data["nodes"]) == 3
    assert len(data["edges"]) == 2
    assert data["sampled"] is False

    # 图例数据（GRA-03 节点着色）：类型名 + 颜色
    by_name = {c["name"]: c for c in data["categories"]}
    assert by_name["人物"]["color"] == "#5470c6"
    assert by_name["组织"]["color"] == "#91cc75"
    assert any(rt["name"] == "属于" for rt in data["relation_types"])

    # 节点字段齐备：着色/类型/频次
    node = next(n for n in data["nodes"] if n["name"] == "张三")
    assert node["color"] == "#5470c6"
    assert node["type_name"] == "人物"
    assert node["value"] == 5
    # 边字段：两端点 id 存在且端点都在节点集合中
    node_ids = {n["id"] for n in data["nodes"]}
    for edge in data["edges"]:
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids
        assert edge["relation_type_name"] in {"属于", "相关"}
    assert seeded["zhangsan"].id in node_ids


def test_overview_isolated_by_user(client, db):
    alice_token = register_and_login(client, username="alice", email="alice@test.com")
    seed_graph_data(db, get_user(db, "alice"))

    bob_token = register_and_login(client, username="bob123", email="bob@test.com")
    r = client.get("/api/v1/graph/overview", headers=auth_headers(bob_token))
    data = r.json()
    assert data["total_nodes"] == 0
    assert data["total_edges"] == 0
    assert data["nodes"] == []

    # alice 自己的图正常
    r = client.get("/api/v1/graph/overview", headers=auth_headers(alice_token))
    assert r.json()["total_nodes"] == 3


def test_node_detail_with_neighbors_and_evidences(client, db):
    token = register_and_login(client)
    user = get_user(db, "alice")
    seeded = seed_graph_data(db, user)

    r = client.get(f"/api/v1/graph/node/{seeded['zhangsan'].id}", headers=auth_headers(token))
    assert r.status_code == 200
    data = r.json()

    assert data["entity"]["name"] == "张三"
    assert data["entity"]["type"] == {"id": seeded["zhangsan"].type_id, "name": "人物", "color": "#5470c6"}

    # 出边：张三 → 北京大学
    out = [rel for rel in data["relations"] if rel["direction"] == "out"]
    assert len(out) == 1
    assert out[0]["relation_type_name"] == "属于"
    assert out[0]["other"]["name"] == "北京大学"
    assert out[0]["other"]["color"] == "#91cc75"

    # 证据句 + 来源文档
    assert len(data["evidences"]) == 1
    ev = data["evidences"][0]
    assert "张三毕业于北京大学" in ev["sentence"]
    assert ev["document_filename"] == "来源文档.txt"
    assert ev["document_id"] == seeded["doc"].id


def test_node_detail_other_user_404(client, db):
    alice_token = register_and_login(client, username="alice", email="alice@test.com")
    seeded = seed_graph_data(db, get_user(db, "alice"))

    bob_token = register_and_login(client, username="bob123", email="bob@test.com")
    r = client.get(f"/api/v1/graph/node/{seeded['zhangsan'].id}", headers=auth_headers(bob_token))
    assert r.status_code == 404


def test_node_detail_unknown_404(client):
    token = register_and_login(client)
    r = client.get("/api/v1/graph/node/99999", headers=auth_headers(token))
    assert r.status_code == 404
