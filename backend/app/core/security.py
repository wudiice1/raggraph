"""安全基础能力：bcrypt 密码哈希（直接使用 bcrypt 库，不用已停止维护的 passlib）与 PyJWT 令牌。"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings

# bcrypt 只处理前 72 字节，超出部分被截断甚至抛异常——schema 层已限制密码 ≤72 字节
BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False  # 超长/畸形输入一律视为不匹配


def create_access_token(user_id: int, expires_minutes: int | None = None) -> str:
    """签发 JWT：payload 为 {sub: 用户ID, iat, exp}（UTC）。"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes or settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int:
    """解析 JWT 返回 user_id；无效/过期时抛出 jwt.InvalidTokenError 子类。"""
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    return int(payload["sub"])
