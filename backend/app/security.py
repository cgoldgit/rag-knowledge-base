"""认证与安全工具：密码加密、JWT 签发与校验"""
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

# bcrypt 密码加密器（存进数据库前先"打码"）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """密码加密：明文 → 密文（不可逆）"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验密码：登录时验证输入的密码是否正确"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: int, username: str, is_admin: bool) -> str:
    """签发登录凭证（JWT）：包含用户信息，24 小时内有效"""
    expire = datetime.now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "username": username,
        "is_admin": is_admin,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """解析登录凭证，无效或过期返回 None"""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
