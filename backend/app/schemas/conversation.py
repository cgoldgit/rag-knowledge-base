"""会话相关数据格式"""
from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str = Field(default="新对话", max_length=200)


class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    role: str  # user / assistant
    content: str
    sources: str | None = None  # 引用来源（JSON）
    rating: str | None = None  # 回答评价
    created_at: str

    class Config:
        from_attributes = True


class RatingRequest(BaseModel):
    rating: str  # up / down / None


class ChatRequest(BaseModel):
    conversation_id: int  # 在哪个会话提问
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    message_id: int  # 助手回答的消息ID
    content: str  # 回答内容
    sources: list[dict]  # 引用来源列表
