"""认证与安全工具：密码加密、JWT 签发与校验"""
from datetime import datetime, timedelta, timezone
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
    # 用世界时（UTC）计算过期时间，避免 python-jose 校验时因本地时区偏移导致有效期错位
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
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
        # 关闭 python-jose 自带的过期校验（它按本地时区算，会错位 8 小时），改为下方自己校验
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False},
        )
    except JWTError:
        return None
    exp = payload.get("exp")
    if exp is None or datetime.now(timezone.utc).timestamp() > exp:
        return None
    return payload
