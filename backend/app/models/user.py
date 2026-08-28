"""用户表。"""
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)  # bcrypt 输出 60 字符，留余量
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user", server_default="user")  # user / admin
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")  # P2 禁用账号预留
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
