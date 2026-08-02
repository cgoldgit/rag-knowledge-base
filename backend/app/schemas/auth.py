"""认证相关数据格式"""
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, description="用户名（3-50位）")
    password: str = Field(min_length=6, max_length=100, description="密码（至少6位）")
    email: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=100)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    is_admin: bool


class UserInfo(BaseModel):
    id: int
    username: str
    email: str | None
    is_admin: bool
    created_at: str
