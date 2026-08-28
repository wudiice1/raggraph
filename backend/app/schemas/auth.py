"""认证模块请求/响应模型。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32, description="用户名（3-32 字符）")
    email: EmailStr = Field(description="邮箱")
    password: str = Field(min_length=6, max_length=64, description="密码（6-64 字符）")

    @field_validator("password")
    @classmethod
    def _check_bcrypt_limit(cls, v: str) -> str:
        # bcrypt 只处理前 72 字节，超长（如多字节中文）必须拒绝而非静默截断
        if len(v.encode("utf-8")) > 72:
            raise ValueError("密码过长（最多 72 字节）")
        return v


class LoginIn(BaseModel):
    username: str = Field(description="用户名")
    password: str = Field(description="密码")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
    status: str
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # 秒
    user: UserOut
