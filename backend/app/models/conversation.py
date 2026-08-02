"""会话与消息表"""
from datetime import datetime
from sqlalchemy import String, Text, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base


class Conversation(Base):
    """会话表：每个用户有多个独立会话"""
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), default="新对话")  # 会话标题
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.id"
    )


class Message(Base):
    """消息表：会话中的每条问答"""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user / assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 引用来源（JSON 字符串：文档名、片段、相似度等）
    sources: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 回答评价：up（有用）/ down（没用）/ None（未评价）
    rating: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
