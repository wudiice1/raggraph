"""本体管理模块测试：默认类型种子与只读接口（图例数据来源）。"""
from tests.conftest import auth_headers, register_and_login


def test_entity_types_seeded_and_readable(client):
    token = register_and_login(client)
    r = client.get("/api/v1/ontology/entity-types", headers=auth_headers(token))
    assert r.status_code == 200
    items = r.json()["items"]
    by_name = {t["name"]: t for t in items}
    assert set(by_name) == {"人物", "组织", "地点", "概念", "技术"}
    assert by_name["人物"]["color"] == "#5470c6"
    assert all(t["color"].startswith("#") for t in items)  # 颜色均为十六进制（ECharts 着色）


def test_relation_types_seeded_and_readable(client):
    token = register_and_login(client)
    r = client.get("/api/v1/ontology/relation-types", headers=auth_headers(token))
    assert r.status_code == 200
    names = {t["name"] for t in r.json()["items"]}
    assert names == {"包含", "属于", "相关", "引用"}


def test_ontology_requires_auth(client):
    assert client.get("/api/v1/ontology/entity-types").status_code == 401
    assert client.get("/api/v1/ontology/relation-types").status_code == 401
