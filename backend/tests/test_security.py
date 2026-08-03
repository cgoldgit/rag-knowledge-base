"""考题：安全模块（密码加密、登录凭证签发/校验）"""
import time

from jose import jwt

from app.config import settings
from app.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPassword:
    def test_hash_password_与明文不同(self):
        hashed = hash_password("secret123")
        assert hashed != "secret123"

    def test_hash_password_两次加密结果不同(self):
        # bcrypt 每次加密都加随机盐，两次结果必须不同（防撞库）
        assert hash_password("secret123") != hash_password("secret123")

    def test_verify_password_正确密码通过(self):
        hashed = hash_password("secret123")
        assert verify_password("secret123", hashed) is True

    def test_verify_password_错误密码失败(self):
        hashed = hash_password("secret123")
        assert verify_password("wrong-pass", hashed) is False


class TestJWT:
    def test_create_token_能解析回用户信息(self):
        token = create_access_token(user_id=1, username="admin", is_admin=True)
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "1"
        assert payload["username"] == "admin"
        assert payload["is_admin"] is True

    def test_create_token_普通用户is_admin为False(self):
        token = create_access_token(user_id=2, username="bob", is_admin=False)
        payload = decode_token(token)
        assert payload["is_admin"] is False

    def test_decode_token_无效凭证返回None(self):
        assert decode_token("not-a-valid-token") is None

    def test_decode_token_过期凭证返回None(self, monkeypatch):
        monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", -1)
        token = create_access_token(user_id=1, username="admin", is_admin=True)
        assert decode_token(token) is None

    def test_decode_token_伪造签名返回None(self):
        token = jwt.encode(
            {"sub": "1", "username": "admin", "is_admin": True, "exp": int(time.time()) + 3600},
            "wrong-secret-key",
            algorithm=settings.ALGORITHM,
        )
        assert decode_token(token) is None
