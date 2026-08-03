"""认证接口：注册、登录、修改密码、个人信息"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas.auth import (
    RegisterRequest, LoginRequest, ChangePasswordRequest,
    TokenResponse, UserInfo, UserSettings,
)
from ..security import hash_password, verify_password, create_access_token
from ..deps import get_current_user
from ..services import cache

router = APIRouter(prefix="/api/auth", tags=["认证"])

# 登录限流：同 IP 每分钟最多 10 次尝试（防密码爆破）
LOGIN_RATE_LIMIT_PER_MINUTE = 10


def _to_user_info(user: User) -> UserInfo:
    return UserInfo(
        id=user.id, username=user.username, email=user.email,
        is_admin=user.is_admin, created_at=user.created_at.isoformat(),
    )


@router.post("/register", response_model=TokenResponse, summary="用户注册")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """注册新用户（非管理员），成功后直接返回登录凭证"""
    exists = db.query(User).filter(User.username == data.username).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已被占用")

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        email=data.email,
        is_admin=False,  # 注册的都是普通用户，管理员是预置的
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.username, user.is_admin)
    return TokenResponse(access_token=token, username=user.username, is_admin=user.is_admin)


@router.post("/login", response_model=TokenResponse, summary="用户登录")
def login(request: Request, data: LoginRequest, db: Session = Depends(get_db)):
    """用户名 + 密码登录，成功后返回登录凭证"""
    # 限流：防密码爆破
    client_ip = request.client.host if request.client else "unknown"
    if not cache.rate_limit(f"rl:login:{client_ip}", LOGIN_RATE_LIMIT_PER_MINUTE):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="尝试次数过多，请稍后再试")

    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    token = create_access_token(user.id, user.username, user.is_admin)
    return TokenResponse(access_token=token, username=user.username, is_admin=user.is_admin)


@router.get("/me", response_model=UserInfo, summary="获取当前用户信息")
def me(user: User = Depends(get_current_user)):
    return _to_user_info(user)


@router.put("/password", summary="修改密码")
def change_password(
    data: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """验证旧密码后修改为新密码"""
    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")

    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": "密码修改成功"}


@router.get("/settings", response_model=UserSettings, summary="获取我的设置")
def get_settings(
    user: User = Depends(get_current_user),
):
    """获取用户个性化设置（检索片段数、是否显示引用）"""
    import json

    if user.settings:
        try:
            return UserSettings(**json.loads(user.settings))
        except Exception:
            pass
    return UserSettings()


@router.put("/settings", response_model=UserSettings, summary="保存我的设置")
def save_settings(
    data: UserSettings,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """保存用户个性化设置"""
    import json

    user.settings = json.dumps(data.model_dump(), ensure_ascii=False)
    db.commit()
    return data
