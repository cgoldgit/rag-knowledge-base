"""用户表"""
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)  # bcrypt 加密
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # 是否管理员
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 用户设置（JSON：检索片段数、显示引用等）
    settings: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
