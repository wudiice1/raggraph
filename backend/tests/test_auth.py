"""认证模块测试：注册/登录/JWT 鉴权/内置管理员。"""
from sqlalchemy import select

from app.core.security import create_access_token
from app.database import SessionLocal
from app.models import User

from tests.conftest import auth_headers, register_and_login

REGISTER = {"username": "alice", "email": "alice@test.com", "password": "pass123456"}


def test_register_success_and_password_hashed(client):
    r = client.post("/api/v1/auth/register", json=REGISTER)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["username"] == "alice"
    assert data["role"] == "user"
    # 验收 10.1：数据库密码字段为 bcrypt 哈希（非明文）
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "alice"))
        assert user.password_hash != REGISTER["password"]
        assert user.password_hash.startswith("$2")  # bcrypt 前缀 $2a/$2b/$2y


def test_register_duplicate_username_409(client):
    assert client.post("/api/v1/auth/register", json=REGISTER).status_code == 201
    r = client.post("/api/v1/auth/register", json={**REGISTER, "email": "other@test.com"})
    assert r.status_code == 409
    assert r.json()["detail"] == "用户名已存在"


def test_register_duplicate_email_409(client):
    assert client.post("/api/v1/auth/register", json=REGISTER).status_code == 201
    r = client.post("/api/v1/auth/register", json={**REGISTER, "username": "bob123"})
    assert r.status_code == 409
    assert r.json()["detail"] == "邮箱已被注册"


def test_register_validation(client):
    # 密码过短
    r = client.post("/api/v1/auth/register", json={**REGISTER, "password": "123"})
    assert r.status_code == 422
    # 密码超 72 字节（bcrypt 上限，30 个汉字 = 90 字节）
    r = client.post("/api/v1/auth/register", json={**REGISTER, "password": "密" * 30})
    assert r.status_code == 422
    # 邮箱格式非法
    r = client.post("/api/v1/auth/register", json={**REGISTER, "email": "not-an-email"})
    assert r.status_code == 422


def test_login_success(client):
    register_and_login(client)
    r = client.post("/api/v1/auth/login", json={"username": "alice", "password": "pass123456"})
    assert r.status_code == 200
    data = r.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["user"]["username"] == "alice"
    assert data["expires_in"] > 0


def test_login_wrong_password_401(client):
    register_and_login(client)
    r = client.post("/api/v1/auth/login", json={"username": "alice", "password": "wrong-pass"})
    assert r.status_code == 401
    assert r.json()["detail"] == "用户名或密码错误"  # 验收 10.1：明确提示


def test_login_unknown_user_401(client):
    r = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "whatever"})
    assert r.status_code == 401
    assert r.json()["detail"] == "用户名或密码错误"  # 统一提示，防用户名枚举


def test_me_without_token_401(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_invalid_token_401(client):
    r = client.get("/api/v1/auth/me", headers=auth_headers("garbage-token"))
    assert r.status_code == 401


def test_me_expired_token_401(client):
    token = create_access_token(1, expires_minutes=-1)
    r = client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert r.status_code == 401
    assert r.json()["detail"] == "登录已过期，请重新登录"


def test_me_ok(client):
    token = register_and_login(client)
    r = client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "alice"
    assert data["email"] == "alice@test.com"


def test_admin_seeded_and_can_login(client):
    """AUTH-06：初始化内置 admin 默认账号。"""
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "admin"
